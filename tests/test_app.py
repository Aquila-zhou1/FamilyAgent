"""Startup checks that need no network and no real API key."""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault("DASHSCOPE_BASE_URL", "http://localhost:9/v1")

from fastapi.testclient import TestClient  # noqa: E402

from familyagent.__main__ import app  # noqa: E402
from familyagent.agent import chess_agent  # noqa: E402

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


def test_stream_returns_model_text(monkeypatch):
    class FakeChunk:
        def __init__(self, content):
            self.content = content

    class FakeLLM:
        def stream(self, messages):
            assert "Answer in English." in messages[0].content
            yield FakeChunk("Hello")
            yield FakeChunk(" there")

    monkeypatch.setattr(chess_agent, "get_llm", lambda: FakeLLM())
    response = client.post("/agent/chess/stream", json={"question": "hi"})
    assert response.status_code == 200
    assert response.text == "Hello there"


def test_stream_reports_failure_in_requested_language(monkeypatch):
    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(chess_agent, "get_llm", broken)
    response = client.post(
        "/agent/chess/stream", json={"question": "你好", "lang": "zh"}
    )
    assert response.text == chess_agent.ERROR_MESSAGE["zh"]


def test_empty_question_is_rejected():
    assert client.post("/agent/chess/stream", json={"question": ""}).status_code == 422
