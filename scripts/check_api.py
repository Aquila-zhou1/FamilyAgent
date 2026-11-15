"""Check the model API configured in .env. Prints no secrets.

Usage (from the repository root):
    python scripts/check_api.py            # all checks
    python scripts/check_api.py --quick    # only the first call

Checks, in order:
  1. basic      one plain completion
  2. tools      the model returns a tool call when a tool is clearly needed
  3. tool loop  the model answers after it is given the tool result
  4. streaming  chunks arrive incrementally
  5. burst      5 calls in a row, to expose rate limits and quota errors

The agent needs 1-3 to work. A failure in 5 means evaluation runs (100+ calls)
will hit limits with this model or plan.
"""

import argparse
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from familyagent.agent.llm import get_llm  # noqa: E402
from familyagent.config import config  # noqa: E402

HINTS = {
    401: "authentication failed: check DASHSCOPE_API_KEY",
    402: "quota or billing: the plan/free tier for this model is exhausted; "
         "switch LLM_MODEL or top up",
    403: "forbidden: the key has no access to this model",
    404: "not found: check LLM_MODEL and that DASHSCOPE_BASE_URL ends with the "
         "OpenAI-compatible path (usually /v1)",
    429: "rate limited: too many requests; slow down or use another model",
}


def explain(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    text = " ".join(str(exc).split())[:300]
    if status in HINTS:
        hint = HINTS[status]
    elif status and status >= 500:
        hint = "provider-side error; retry later"
    elif "Connection" in name or "Timeout" in name:
        hint = "network problem: DNS, proxy, firewall or the provider is down"
    else:
        hint = "see the message above"
    return f"{name} (HTTP {status}): {text}\n      -> {hint}"


@tool
def get_puzzle(puzzle_id: str) -> str:
    """Get a Lichess puzzle by its ID."""
    return '{"puzzle_id": "abc12", "solution_uci": ["e2e4"]}'


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the model API configured in .env")
    parser.add_argument("--quick", action="store_true", help="only run the basic call")
    args = parser.parse_args()

    print(f"model:    {config.LLM_MODEL}")
    print(f"host:     {urlparse(config.DASHSCOPE_BASE_URL).netloc or '(not set)'}")
    print(f"key set:  {bool(config.DASHSCOPE_API_KEY)}\n")

    try:
        llm = get_llm()
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] configuration: {exc}")
        return 1

    failures = 0

    def run(label: str, fn) -> object:
        nonlocal failures
        started = time.perf_counter()
        try:
            detail = fn()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[FAIL] {label}\n      {explain(exc)}")
            return None
        ms = (time.perf_counter() - started) * 1000
        print(f"[PASS] {label}  ({ms:.0f} ms)  {detail}")
        return detail

    # 1. basic
    def basic():
        reply = llm.invoke("Reply with exactly: pong")
        return f"reply={reply.content!r}"

    if run("1. basic completion", basic) is None or args.quick:
        print("\nFAILED" if failures else "\nOK")
        return 1 if failures else 0

    # 2 + 3. tool calling and the follow-up turn
    bound = llm.bind_tools([get_puzzle])
    question = HumanMessage(content="Use the tool to get Lichess puzzle abc12, then tell me its solution.")
    state = {}

    def tools():
        ai = bound.invoke([question])
        if not ai.tool_calls:
            raise RuntimeError(
                "the model answered in text instead of calling the tool; "
                f"this model/provider may not support tool calling. text={str(ai.content)[:120]!r}"
            )
        state["ai"] = ai
        call = ai.tool_calls[0]
        return f"tool_call={call['name']}({call['args']})"

    if run("2. tool calling", tools) is not None:
        def loop():
            ai = state["ai"]
            messages = [question, ai] + [
                ToolMessage(content=get_puzzle.invoke(c["args"]), tool_call_id=c["id"])
                for c in ai.tool_calls
            ]
            final = bound.invoke(messages)
            text = str(final.content)
            if "e2e4" not in text:
                raise RuntimeError(f"the answer does not use the tool result: {text[:160]!r}")
            return "answer uses the tool result"

        run("3. tool result follow-up", loop)

    # 4. streaming
    def streaming():
        chunks = [c.content for c in llm.stream("Count from 1 to 5, one number per line.") if c.content]
        if not chunks:
            raise RuntimeError("no content chunks were received")
        return f"{len(chunks)} chunks"

    run("4. streaming", streaming)

    # 5. burst
    def burst():
        times = []
        for i in range(5):
            started = time.perf_counter()
            try:
                llm.invoke("Reply with exactly: ok")
            except Exception as exc:
                raise RuntimeError(f"call {i + 1} of 5 failed: {explain(exc)}") from exc
            times.append((time.perf_counter() - started) * 1000)
        return f"median {statistics.median(times):.0f} ms, slowest {max(times):.0f} ms"

    run("5. five calls in a row", burst)

    print(f"\n{'ALL PASSED' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
