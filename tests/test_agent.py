"""Agent pieces that can be checked without a model or MCP servers."""

import asyncio
import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault("DASHSCOPE_BASE_URL", "http://localhost:9/v1")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402

from familyagent.agent import chess_agent, tools  # noqa: E402


def test_extract_tool_calls_orders_and_marks_outcome():
    messages = [
        HumanMessage(content="q"),
        AIMessage(content="", tool_calls=[
            {"name": "get_daily_puzzle", "args": {}, "id": "a"},
            {"name": "find_opening_by_moves", "args": {"moves": "e4 e5"}, "id": "b"},
        ]),
        ToolMessage(content='{"puzzle_id": "x"}', tool_call_id="a"),
        ToolMessage(content="TOOL_ERROR: find_opening_by_moves failed.", tool_call_id="b"),
        AIMessage(content="done"),
    ]
    calls = chess_agent.extract_tool_calls(messages)
    assert [c["name"] for c in calls] == ["get_daily_puzzle", "find_opening_by_moves"]
    assert [c["ok"] for c in calls] == [True, False]
    assert calls[1]["args"] == {"moves": "e4 e5"}


def test_extract_tool_calls_handles_no_tools():
    assert chess_agent.extract_tool_calls([HumanMessage(content="q"), AIMessage(content="a")]) == []


def test_system_prompt_mentions_unavailable_servers_and_language():
    prompt = chess_agent.build_system_prompt("zh", ["lichess"])
    assert "lichess" in prompt.split("Currently unavailable tool servers:")[1]
    assert "简体中文" in prompt
    assert "Currently unavailable" not in chess_agent.build_system_prompt("en", [])


def test_to_text_accepts_strings_and_blocks():
    assert tools.to_text("abc") == "abc"
    assert tools.to_text([{"type": "text", "text": "a"}, {"type": "image"}, "b"]) == "ab"
    assert tools.to_text(None) == ""


def test_guard_turns_failures_into_tool_error_text():
    async def boom(query: str) -> str:
        raise ConnectionError("server gone")

    async def fine(query: str) -> str:
        return f"ok {query}"

    def make(fn):
        return StructuredTool.from_function(coroutine=fn, name="search_openings", description="d")

    failed = asyncio.run(tools.guard(make(boom)).ainvoke({"query": "x"}))
    assert failed.startswith("TOOL_ERROR: search_openings failed (ConnectionError: server gone)")
    assert "No data was retrieved" in failed
    assert asyncio.run(tools.guard(make(fine)).ainvoke({"query": "x"})) == "ok x"


def test_load_tools_reports_unreachable_servers(monkeypatch):
    monkeypatch.setattr(tools, "server_urls", lambda: {
        "openings": "http://127.0.0.1:9/mcp", "lichess": "http://127.0.0.1:9/mcp",
    })
    monkeypatch.setattr(tools.config, "MCP_CONNECT_TIMEOUT_SECONDS", 1.0)
    loaded, unavailable = asyncio.run(tools.load_tools())
    assert loaded == []
    assert unavailable == ["openings", "lichess"]


def test_ask_reports_failure_without_raising(monkeypatch):
    async def broken(question, lang):
        raise RuntimeError("model down")

    monkeypatch.setattr(chess_agent, "_prepare", broken)
    result = asyncio.run(chess_agent.ask("hi", "zh"))
    assert result["answer"] == chess_agent.ERROR_MESSAGE["zh"]
    assert result["error"] == "RuntimeError: model down"
    assert result["tool_calls"] == [] and isinstance(result["latency_ms"], int)
