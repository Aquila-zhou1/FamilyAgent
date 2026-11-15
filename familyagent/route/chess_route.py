"""Chess assistant routes: chat page and streaming endpoint."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from familyagent.agent.chess_agent import stream_answer

router = APIRouter(prefix="/agent/chess", tags=["chess"])

# The page is a static file (no server-side templating), so Vue's {{ }} is safe.
CHAT_PAGE = Path(__file__).resolve().parent.parent / "static" / "chess.html"


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    lang: str = "en"


@router.get("", summary="Chat page", response_class=FileResponse)
def chess_page() -> FileResponse:
    return FileResponse(CHAT_PAGE, media_type="text/html; charset=utf-8")


@router.post("/stream", summary="Ask a question, streamed as plain text")
def chess_stream(data: Question) -> StreamingResponse:
    # A sync generator: Starlette iterates it in a worker thread, so the
    # blocking model call does not stall the event loop.
    return StreamingResponse(
        stream_answer(data.question, data.lang),
        media_type="text/plain; charset=utf-8",
    )
