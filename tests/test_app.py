"""Web app checks that need no network, no MCP servers and no real API key."""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault("DASHSCOPE_BASE_URL", "http://localhost:9/v1")

from fastapi.testclient import TestClient  # noqa: E402

from familyagent.__main__ import app  # noqa: E402
from familyagent.route import chess_route  # noqa: E402

client = TestClient(app)


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_root_redirects_to_chat_page():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/agent/chess"


def test_chat_page_defaults_to_english_and_has_toggle():
    response = client.get("/agent/chess")
    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    assert "toggleLang" in response.text


def test_stream_passes_question_and_language(monkeypatch):
    seen = {}

    async def fake_stream(question, lang):
        seen.update(question=question, lang=lang)
        yield "Hello"
        yield " there"

    monkeypatch.setattr(chess_route, "stream_answer", fake_stream)
    response = client.post("/agent/chess/stream", json={"question": "你好", "lang": "zh"})
    assert response.status_code == 200
    assert response.text == "Hello there"
    assert seen == {"question": "你好", "lang": "zh"}


def test_ask_returns_answer_and_trace(monkeypatch):
    async def fake_ask(question, lang):
        return {
            "answer": "The solution is e8e7.",
            "tool_calls": [
                {"name": "get_daily_puzzle", "args": {}, "ok": True, "result": "{}"}
            ],
            "unavailable_servers": [],
            "error": None,
            "latency_ms": 12,
        }

    monkeypatch.setattr(chess_route, "ask", fake_ask)
    body = client.post("/agent/chess/ask", json={"question": "daily puzzle?"}).json()
    assert body["answer"] == "The solution is e8e7."
    assert body["tool_calls"][0]["name"] == "get_daily_puzzle"
    assert set(body) == {"answer", "tool_calls", "unavailable_servers", "error", "latency_ms"}


def test_empty_question_is_rejected():
    assert client.post("/agent/chess/stream", json={"question": ""}).status_code == 422
    assert client.post("/agent/chess/ask", json={"question": ""}).status_code == 422
