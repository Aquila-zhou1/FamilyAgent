"""Load the agent's tools from the MCP servers.

Tools are discovered over MCP on every request, one server at a time, so that
- a server that is down does not take the other server's tools with it, and
- a server that comes back is picked up without restarting the web app.

Every tool is wrapped so that a failure (server unreachable, timeout, upstream
error) is returned to the model as a `TOOL_ERROR:` text instead of crashing
the run. The model is told to report such errors and never to fill the gap.
"""

import asyncio
import logging

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from familyagent.config import config

logger = logging.getLogger(__name__)

TOOL_ERROR_PREFIX = "TOOL_ERROR:"


def server_urls() -> dict[str, str]:
    return {"openings": config.MCP_OPENINGS_URL, "lichess": config.MCP_LICHESS_URL}


def describe_error(exc: BaseException) -> str:
    """One line for the model and the trace; unwraps task-group wrappers."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    text = " ".join(str(exc).split()) or "no details"
    return f"{type(exc).__name__}: {text}"[:300]


def to_text(content: object) -> str:
    """Tool and model content can be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return "" if content is None else str(content)


def guard(tool: BaseTool) -> BaseTool:
    """Wrap an MCP tool so that any failure becomes a TOOL_ERROR text."""

    async def call(**arguments) -> str:
        try:
            result = await asyncio.wait_for(
                tool.ainvoke(arguments), timeout=config.MCP_CALL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            return (
                f"{TOOL_ERROR_PREFIX} {tool.name} did not answer within "
                f"{config.MCP_CALL_TIMEOUT_SECONDS:g} seconds. No data was retrieved."
            )
        except Exception as exc:  # noqa: BLE001 - every failure must reach the model as text
            logger.warning("tool %s failed: %s", tool.name, describe_error(exc))
            return (
                f"{TOOL_ERROR_PREFIX} {tool.name} failed ({describe_error(exc)}). "
                "No data was retrieved."
            )
        return to_text(result)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema,
        coroutine=call,
    )


async def load_tools() -> tuple[list[BaseTool], list[str]]:
    """Return (tools from reachable servers, names of unreachable servers)."""
    tools: list[BaseTool] = []
    unavailable: list[str] = []
    for name, url in server_urls().items():
        client = MultiServerMCPClient(
            {
                name: {
                    "transport": "streamable_http",
                    "url": url,
                    "timeout": config.MCP_CONNECT_TIMEOUT_SECONDS,
                    "sse_read_timeout": config.MCP_CALL_TIMEOUT_SECONDS,
                }
            },
            handle_tool_errors=False,  # errors are raised and handled by guard()
        )
        try:
            server_tools = await asyncio.wait_for(
                client.get_tools(server_name=name),
                timeout=config.MCP_CONNECT_TIMEOUT_SECONDS + 1,
            )
        except (Exception, asyncio.TimeoutError) as exc:  # noqa: BLE001
            logger.warning("MCP server %s unavailable: %s", name, describe_error(exc))
            unavailable.append(name)
            continue
        tools.extend(guard(t) for t in server_tools)
    return tools, unavailable
