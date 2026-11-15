"""MCP server: Lichess puzzles.

Run:  python -m familyagent.mcp_servers.lichess_server
Endpoint: http://<MCP_HOST>:<MCP_LICHESS_PORT>/mcp  (Streamable HTTP)

LICHESS_MODE=live calls the public API; LICHESS_MODE=replay serves recorded
responses from LICHESS_FIXTURES_DIR.
"""

import json
import logging

from mcp.server.fastmcp import FastMCP

from familyagent.config import config
from familyagent.lichess.client import LichessClient
from familyagent.mcp_servers.common import add_health_route, audit

logger = logging.getLogger("familyagent.mcp.lichess")

server = FastMCP(
    "lichess-puzzles",
    host=config.MCP_HOST,
    port=config.MCP_LICHESS_PORT,
    stateless_http=True,
    json_response=True,
)
add_health_route(server, "lichess-puzzles")

client = LichessClient(
    mode=config.LICHESS_MODE,
    fixtures_dir=config.LICHESS_FIXTURES_DIR,
    timeout=config.LICHESS_TIMEOUT_SECONDS,
    record=config.LICHESS_RECORD,
)


@server.tool()
def get_daily_puzzle() -> str:
    """Get today's Lichess daily puzzle.

    Returns JSON with puzzle_id, rating, themes, solution_uci (the solution
    moves), and game_moves_san (the moves of the source game up to the puzzle
    position). Takes no arguments.
    """
    with audit(logger, "get_daily_puzzle"):
        return json.dumps(client.daily(), ensure_ascii=False)


@server.tool()
def get_puzzle(puzzle_id: str) -> str:
    """Get one Lichess puzzle by its ID.

    Use this when the user gives a puzzle ID (for example "PSjmf").
    Returns the same JSON fields as get_daily_puzzle.

    Args:
        puzzle_id: The Lichess puzzle ID, exactly as given (case-sensitive).
    """
    with audit(logger, "get_puzzle", puzzle_id=puzzle_id):
        return json.dumps(client.puzzle(puzzle_id), ensure_ascii=False)


def main() -> None:
    logger.info("lichess mode: %s", config.LICHESS_MODE)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
