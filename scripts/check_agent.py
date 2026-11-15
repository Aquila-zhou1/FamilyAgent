"""Iteration 3 acceptance: the agent answers through real MCP tool calls.

Start the two MCP servers first, then from the repository root:
    python scripts/check_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from familyagent.agent.chess_agent import ask  # noqa: E402


def show(result: dict) -> None:
    for call in result["tool_calls"]:
        print(f"    tool: {call['name']}({json.dumps(call['args'], ensure_ascii=False)}) ok={call['ok']}")
    answer = " ".join(result["answer"].split())
    print(f"    answer: {answer[:400]}{'...' if len(answer) > 400 else ''}")
    print(f"    latency: {result['latency_ms']} ms   error: {result['error']}   "
          f"unavailable: {result['unavailable_servers']}")


def in_order(moves: list[str], text: str) -> bool:
    """Every move appears in the text, each one after the previous one."""
    position = 0
    for move in moves:
        found = text.find(move, position)
        if found < 0:
            return False
        position = found + len(move)
    return True


def names(result: dict) -> list[str]:
    return [c["name"] for c in result["tool_calls"]]


async def main() -> int:
    failures = 0

    def check(label: str, passed: bool) -> None:
        nonlocal failures
        failures += not passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")

    print("1. Daily puzzle solution")
    r = await ask("What is the solution to today's Lichess daily puzzle?")
    show(r)
    daily = next((c for c in r["tool_calls"] if c["name"] == "get_daily_puzzle" and c["ok"]), None)
    check("get_daily_puzzle was called and succeeded", daily is not None)
    if daily:
        data = json.loads(daily["result"])
        # Either notation is a correct answer, as long as it is the tool's own
        # moves, complete and in order.
        notations = [data["solution_uci"]] + ([data["solution_san"]] if data.get("solution_san") else [])
        check(f"answer contains the full solution in order, as {' or '.join(map(str, notations))}",
              any(in_order(moves, r["answer"]) for moves in notations))

    print("\n2. Opening of today's puzzle (two steps)")
    r = await ask("Which opening does the game of today's Lichess daily puzzle come from?")
    show(r)
    check("get_daily_puzzle then find_opening_by_moves",
          "get_daily_puzzle" in names(r) and "find_opening_by_moves" in names(r)
          and names(r).index("get_daily_puzzle") < names(r).index("find_opening_by_moves"))
    found = next((c for c in r["tool_calls"] if c["name"] == "find_opening_by_moves" and c["ok"]), None)
    if found and json.loads(found["result"]).get("found"):
        opening = json.loads(found["result"])["name"]
        check(f"answer names the opening returned by the tool ({opening})",
              opening.split(":")[0] in r["answer"])

    print("\n3. Opening by name")
    r = await ask("What are the moves of the Sicilian Defense: Najdorf Variation?")
    show(r)
    check("search_openings was called", "search_openings" in names(r))

    print("\n4. General knowledge needs no tool")
    r = await ask("How does the knight move?")
    show(r)
    check("no tool was called", r["tool_calls"] == [] and r["error"] is None)

    print(f"\n{'ALL PASSED' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
