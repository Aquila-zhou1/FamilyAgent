"""FastAPI entry point. Start with `python -m familyagent`."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from familyagent.config import config
from familyagent.route.chess_route import router as chess_router

app = FastAPI(
    title="Chess Agent",
    version="0.2.0",
    description="Chess assistant: Lichess puzzles and opening lookup through MCP tools.",
)
app.include_router(chess_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/agent/chess")


@app.get("/healthz", summary="Liveness check (does not call the model)")
def healthz() -> dict:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run(
        "familyagent.__main__:app",
        host=config.FASTAPI_HOST,
        port=config.FASTAPI_PORT,
        reload=config.FASTAPI_RELOAD,
    )


if __name__ == "__main__":
    main()
