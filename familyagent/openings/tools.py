"""Tool logic for the openings MCP server (no MCP imports, so it is unit-testable).

Each function returns a JSON string: that is what the model reads.
"""

import json
import sqlite3

from familyagent.openings.retrieve import retrieve
from familyagent.openings.search import find_deepest_opening


def _public(row: dict) -> dict:
    return {"name": row["name"], "eco": row["eco"], "moves": row["pgn"]}


def search_openings_tool(conn: sqlite3.Connection, query: str, impl: str) -> str:
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")
    results = [_public(r) for r in retrieve(conn, query, impl=impl, limit=3)]
    payload: dict = {"query": query, "count": len(results), "results": results}
    if results:
        payload["note"] = (
            "These are the closest matches by name and may not be what the user meant. "
            "Only use a result whose name matches the request."
        )
    else:
        payload["note"] = "No opening in the database matched this query."
    return json.dumps(payload, ensure_ascii=False)


def find_opening_by_moves_tool(conn: sqlite3.Connection, moves: str) -> str:
    moves = (moves or "").strip()
    if not moves:
        raise ValueError("moves must not be empty")
    found = find_deepest_opening(conn, moves)
    if found is None:
        return json.dumps({
            "found": False,
            "note": "No opening in the database starts with these moves.",
        })
    return json.dumps({
        "found": True,
        **_public(found),
        "matched_half_moves": found["matched_plies"],
        "given_half_moves": found["given_plies"],
        "note": (
            "This is the deepest known opening along the given moves; "
            "later moves, if any, are outside the opening database."
        ),
    }, ensure_ascii=False)
