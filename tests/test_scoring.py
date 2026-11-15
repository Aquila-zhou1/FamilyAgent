from eval.scoring import norm_moves, p95, score, score_failure, score_tool


def call(name, args=None, ok=True, result="{}"):
    return {"name": name, "args": args or {}, "ok": ok, "result": result}


def test_p95_nearest_rank():
    assert p95(list(range(1, 101))) == 95
    assert p95([5]) == 5
    assert p95([]) is None


def test_norm_moves():
    assert norm_moves("1. e4 c5 2.Nf3 d6") == ["e4", "c5", "Nf3", "d6"]
    assert norm_moves("e2e4 c7c5") == ["e2e4", "c7c5"]


def test_tool_case_needs_exact_tool_set_and_args():
    case = {"category": "tool", "expected_tools": ["get_puzzle"],
            "arg": {"tool": "get_puzzle", "key": "puzzle_id", "equals": "f9Xve"}}
    good = {"answer": "x", "tool_calls": [call("get_puzzle", {"puzzle_id": "f9Xve"})]}
    wrong_arg = {"answer": "x", "tool_calls": [call("get_puzzle", {"puzzle_id": "f9xve"})]}
    extra = {"answer": "x", "tool_calls": [call("get_puzzle", {"puzzle_id": "f9Xve"}), call("search_openings")]}
    assert score_tool(case, good)["pass"]
    assert not score_tool(case, wrong_arg)["pass"]
    assert not score_tool(case, extra)["pass"]


def test_no_tool_case():
    case = {"category": "tool", "expected_tools": []}
    assert score_tool(case, {"answer": "x", "tool_calls": []})["pass"]
    assert not score_tool(case, {"answer": "x", "tool_calls": [call("search_openings")]})["pass"]


def test_failure_case_rules():
    case = {"category": "failure", "forbidden": ["Qxf8"]}
    honest = {"answer": "Sorry, the puzzle service failed.", "tool_calls": [call("get_puzzle", ok=False)]}
    invented = {"answer": "The puzzle failed, but I recall Qxf8#.", "tool_calls": [call("get_puzzle", ok=False)]}
    silent = {"answer": "Here is a puzzle.", "tool_calls": [call("get_puzzle", ok=False)]}
    unreached = {"answer": "Sorry, it failed.", "tool_calls": []}
    assert score_failure(case, honest)["pass"]
    assert not score_failure(case, invented)["pass"]
    assert not score_failure(case, silent)["pass"]
    assert not score_failure(case, unreached)["pass"]
    down = {"answer": "The service is unavailable.", "tool_calls": [], "unavailable_servers": ["lichess"]}
    assert score_failure(case, down)["pass"]


def test_retrieval_hit_uses_tool_results():
    case = {"category": "retrieval", "answerable": True, "gold_name": "Ruy Lopez"}
    res = {"answer": "x", "tool_calls": [call("search_openings", result='{"results":[{"name":"Ruy Lopez"}]}')]}
    assert score(case, res)["pass"]
    miss = {"answer": "x", "tool_calls": [call("search_openings", result='{"results":[{"name":"Other"}]}')]}
    assert not score(case, miss)["pass"]
    assert not score(case, {"answer": "x", "tool_calls": [], "error": "boom"})["pass"]
