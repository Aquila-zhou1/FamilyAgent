"""Shared pieces of the two MCP servers: audit log line and health route."""

import json
import logging
import time
from contextlib import contextmanager

from starlette.requests import Request
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")


@contextmanager
def audit(logger: logging.Logger, tool: str, **arguments):
    """Log one JSON line per tool call: name, arguments, outcome, duration."""
    started = time.perf_counter()
    record = {"tool": tool, "args": arguments, "ok": True}
    try:
        yield record
    except Exception as exc:
        record["ok"] = False
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["ms"] = round((time.perf_counter() - started) * 1000, 1)
        logger.info("tool_call %s", json.dumps(record, ensure_ascii=False))


def add_health_route(server, name: str) -> None:
    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request: Request) -> JSONResponse:  # noqa: ARG001
        return JSONResponse({"status": "ok", "server": name})
