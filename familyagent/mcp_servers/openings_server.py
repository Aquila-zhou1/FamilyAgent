"""MCP server: chess openings database.

Run:  python -m familyagent.mcp_servers.openings_server
Endpoint: http://<MCP_HOST>:<MCP_OPENINGS_PORT>/mcp  (Streamable HTTP)
"""

import logging

from mcp.server.fastmcp import FastMCP

from familyagent.config import config
from familyagent.mcp_servers.common import add_health_route, audit
from familyagent.openings import db
from familyagent.openings.tools import find_opening_by_moves_tool, search_openings_tool

logger = logging.getLogger("familyagent.mcp.openings")

server = FastMCP(
    "chess-openings",
    host=config.MCP_HOST,
    port=config.MCP_OPENINGS_PORT,
    stateless_http=True,
    json_response=True,
)
add_health_route(server, "chess-openings")


@server.tool()
def search_openings(query: str) -> str:
    """Search the chess openings database by opening NAME.

    Use this when the user names an opening (for example "Najdorf Sicilian" or
    "Queen's Gambit Declined") and wants its moves or ECO code.
    Returns up to 3 candidates as JSON, each with name, eco and moves.

    Args:
        query: The opening name, as the user wrote it.
    """
    with audit(logger, "search_openings", query=query):
        return search_openings_tool(db.get_connection(), query, config.SEARCH_IMPL)


@server.tool()
def find_opening_by_moves(moves: str) -> str:
    """Identify the opening reached by a sequence of MOVES.

    Use this when the user gives moves and wants the opening's name, or to
    find the opening of a game. Accepts SAN ("1. e4 c5 2. Nf3" or "e4 c5 Nf3")
    or UCI ("e2e4 c7c5 g1f3"). Returns the deepest known opening along the
    moves as JSON; extra moves after the opening are fine.

    Args:
        moves: The moves from the start of the game, in order.
    """
    with audit(logger, "find_opening_by_moves", moves=moves):
        return find_opening_by_moves_tool(db.get_connection(), moves)


def main() -> None:
    db.get_connection()  # fail at startup, not on the first call, if the data is missing
    logger.info("search implementation: %s", config.SEARCH_IMPL)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
