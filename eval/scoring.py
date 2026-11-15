"""Pass/fail rules for the end-to-end evaluation. Pure functions, unit-tested.

Inputs are one case (a dict from eval/cases/*.jsonl) and one answer from
POST /agent/chess/ask: {answer, tool_calls[{name, args, ok, result}],
unavailable_servers, error, latency_ms}.
"""

import json
import math
import re

ACK_WORDS = (
    "unable", "couldn't", "could not", "can't", "cannot", "unavailable", "not available",
    "failed", "error", "didn't", "did not", "isn't", "is not", "not able", "unreachable",
    "timed out", "rate limit", "try again", "no puzzle data", "not found", "wasn't",
    "not a valid", "invalid", "no data", "no opening", "not in",
)
_MOVE_NUMBER = re.compile(r"\d+\.(\.\.)?")


def p95(values: list[float]) -> float | None:
    """The ceil(0.95 * N)-th smallest value (nearest-rank method)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def norm_moves(text: str) -> list[str]:
    """'1. e4 c5 2.Nf3' -> ['e4', 'c5', 'Nf3'] (move numbers removed)."""
    return _MOVE_NUMBER.sub(" ", text).split()


def called(result: dict) -> list[str]:
    return [c["name"] for c in result.get("tool_calls", [])]


def acknowledges_failure(answer: str) -> bool:
    low = answer.lower()
    return any(w in low for w in ACK_WORDS)


def result_names(result: dict, tools: tuple[str, ...]) -> list[str]:
    """Every opening name returned by the given tools (any 'name' field, any depth)."""
    names: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("name"), str):
                names.append(node["name"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for call in result.get("tool_calls", []):
        if call["name"] in tools and call.get("ok"):
            try:
                walk(json.loads(call["result"]))
            except (ValueError, TypeError):
                pass
    return names


def score_retrieval(case: dict, result: dict) -> dict:
    """Answerable case: hit if the gold name is among the opening names the tools returned
    (search_openings returns at most 3, so this is Recall@3 measured through the agent).
    No-answer case: pass if the agent says it found nothing instead of inventing an opening."""
    tools = ("search_openings", "find_opening_by_moves")
    used = [n for n in called(result) if n in tools]
    if case["answerable"]:
        hit = case["gold_name"] in result_names(result, tools)
        return {"pass": hit, "tool_used": bool(used)}
    ok = acknowledges_failure(result["answer"]) and case["gold_name"] is None
    return {"pass": ok, "tool_used": bool(used)}


def score_tool(case: dict, result: dict) -> dict:
    names = called(result)
    tools_ok = set(names) == set(case["expected_tools"])
    arg_ok = True
    check = case.get("arg")
    if check:
        calls = [c for c in result.get("tool_calls", []) if c["name"] == check["tool"]]
        arg_ok = False
        for c in calls:
            value = str(c["args"].get(check["key"], ""))
            if "equals" in check:
                arg_ok |= value == check["equals"]
            elif "contains" in check:
                arg_ok |= check["contains"].lower() in value.lower()
            elif "moves" in check:
                arg_ok |= norm_moves(value) == check["moves"].split()
    return {"pass": tools_ok and arg_ok, "tools_ok": tools_ok, "args_ok": arg_ok, "called": names}


def score_failure(case: dict, result: dict) -> dict:
    """Pass if (1) the failure really reached the agent, (2) the answer admits it,
    (3) the answer contains none of the data that could only have been invented."""
    reached = bool(result.get("unavailable_servers")) or any(
        not c.get("ok") for c in result.get("tool_calls", [])
    )
    admits = acknowledges_failure(result["answer"])
    invented = [w for w in case["forbidden"] if w.lower() in result["answer"].lower()]
    return {
        "pass": reached and admits and not invented,
        "reached": reached,
        "admits": admits,
        "invented": invented,
    }


def score(case: dict, result: dict) -> dict:
    if result.get("error"):
        return {"pass": False, "run_error": result["error"]}
    fn = {"retrieval": score_retrieval, "tool": score_tool, "failure": score_failure}[case["category"]]
    return fn(case, result)
