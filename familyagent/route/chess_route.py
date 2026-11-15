"""Chess assistant routes: chat page, streaming endpoint, and JSON endpoint."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from familyagent.agent.chess_agent import ask, stream_answer

router = APIRouter(prefix="/agent/chess", tags=["chess"])

# The page is a static file (no server-side templating), so Vue's {{ }} is safe.
CHAT_PAGE = Path(__file__).resolve().parent.parent / "static" / "chess.html"


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    lang: str = "en"


class ToolCall(BaseModel):
    name: str
    args: dict
    ok: bool | None
    result: str | None


class Answer(BaseModel):
    answer: str
    tool_calls: list[ToolCall]
    unavailable_servers: list[str]
    error: str | None
    latency_ms: int


@router.get("", summary="Chat page", response_class=FileResponse)
def chess_page() -> FileResponse:
    return FileResponse(CHAT_PAGE, media_type="text/html; charset=utf-8")


@router.post("/stream", summary="Ask a question, streamed as plain text")
async def chess_stream(data: Question) -> StreamingResponse:
    return StreamingResponse(
        stream_answer(data.question, data.lang),
        media_type="text/plain; charset=utf-8",
    )


@router.post("/ask", summary="Ask a question; returns the answer and the tool calls made")
async def chess_ask(data: Question) -> Answer:
    return Answer(**await ask(data.question, data.lang))
