"""Talk to both MCP servers directly (no model): list tools, call each one.

Start the two servers first, then from the repository root:
    python scripts/check_mcp.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402

from familyagent.agent.tools import describe_error, server_urls  # noqa: E402

EXPECTED = {
    "openings": {"search_openings", "find_opening_by_moves"},
    "lichess": {"get_daily_puzzle", "get_puzzle"},
}


def text_of(result) -> str:
    return "".join(getattr(block, "text", "") for block in result.content)


async def call(session, name: str, arguments: dict) -> tuple[bool, str]:
    result = await session.call_tool(name, arguments)
    return (not result.isError), text_of(result)


async def main() -> int:
    client = MultiServerMCPClient(
        {name: {"transport": "streamable_http", "url": url} for name, url in server_urls().items()}
    )
    failures = 0

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        failures += not passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))

    for server, url in server_urls().items():
        print(f"\n== {server}  {url}")
        try:
            async with client.session(server) as session:
                names = {tool.name for tool in (await session.list_tools()).tools}
                check(f"tools/list -> {sorted(names)}", names == EXPECTED[server])

                if server == "openings":
                    ok, text = await call(session, "search_openings", {"query": "Sicilian Defense"})
                    check("search_openings('Sicilian Defense')", ok and json.loads(text)["count"] == 3)
                    ok, text = await call(session, "find_opening_by_moves", {"moves": "1. e4 c5 2. Nf3 d6 3. a4"})
                    data = json.loads(text) if ok else {}
                    check("find_opening_by_moves(...)", ok and data.get("found") is True, data.get("name", text))
                    ok, text = await call(session, "search_openings", {"query": ""})
                    check("empty query is reported as a tool error", not ok, text[:80])
                else:
                    ok, text = await call(session, "get_daily_puzzle", {})
                    data = json.loads(text) if ok else {}
                    check("get_daily_puzzle()", ok and bool(data.get("solution_uci")),
                          f"id={data.get('puzzle_id')} solution={data.get('solution_uci')} source={data.get('source')}"
                          if ok else text[:200])
                    if ok:
                        ok2, text2 = await call(session, "get_puzzle", {"puzzle_id": data["puzzle_id"]})
                        same = ok2 and json.loads(text2)["solution_uci"] == data["solution_uci"]
                        check(f"get_puzzle('{data['puzzle_id']}') matches the daily puzzle", same,
                              "" if same else text2[:200])
                    ok, text = await call(session, "get_puzzle", {"puzzle_id": "not a puzzle id"})
                    check("invalid puzzle id is reported as a tool error", not ok, text[:80])
        except Exception as exc:  # noqa: BLE001
            check(f"connect to {server}", False, describe_error(exc))

    print(f"\n{'ALL PASSED' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
