"""Opening lookup.

This file holds the *baseline* implementation: deliberately simple, so that
later improvements can be measured against it on the same cases.

- By name: case-insensitive substring match of the raw query against `name`.
- By moves: exact match of the whole move sequence (UCI or SAN).

`find_deepest_opening` is separate from that comparison: it is the structured
lookup behind the `find_opening_by_moves` tool, where the caller passes moves
only (for example the moves of a real game) and wants the opening they reach.
"""

import re
import sqlite3

from familyagent.openings.db import pgn_to_san

RESULT_COLUMNS = "id, eco, name, pgn, uci"
_UCI_MOVE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")


def _rows(cursor: sqlite3.Cursor) -> list[dict]:
    return [dict(row) for row in cursor.fetchall()]


def search_openings(conn: sqlite3.Connection, query: str, limit: int = 3) -> list[dict]:
    """Openings whose name contains `query`. Shortest (most general) line first."""
    query = query.strip()
    if not query:
        return []
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    cursor = conn.execute(
        f"SELECT {RESULT_COLUMNS} FROM openings "
        "WHERE name LIKE ? ESCAPE '\\' ORDER BY ply, id LIMIT ?",
        (f"%{escaped}%", limit),
    )
    return _rows(cursor)


def normalize_moves(moves: str) -> tuple[str, str]:
    """Return (column, value): 'uci' for coordinate moves, otherwise 'san'."""
    tokens = moves.strip().split()
    if tokens and all(_UCI_MOVE.match(t.lower()) for t in tokens):
        return "uci", " ".join(t.lower() for t in tokens)
    return "san", pgn_to_san(moves)


def find_opening_by_moves(
    conn: sqlite3.Connection, moves: str, limit: int = 3
) -> list[dict]:
    """Openings whose full move sequence equals `moves`.

    Accepts UCI ('e2e4 c7c5') or SAN with or without move numbers
    ('1. e4 c5' or 'e4 c5').
    """
    column, value = normalize_moves(moves)
    if not value:
        return []
    cursor = conn.execute(
        f"SELECT {RESULT_COLUMNS} FROM openings WHERE {column} = ? ORDER BY id LIMIT ?",
        (value, limit),
    )
    return _rows(cursor)


MAX_BOOK_PLY = 36  # the longest line in the dataset


def find_deepest_opening(conn: sqlite3.Connection, moves: str) -> dict | None:
    """The deepest known opening that the given moves start with.

    A game continues past its opening, so the full move list rarely equals a
    book line. This tries the longest prefix first and shortens it one
    half-move at a time. Returns the row plus `matched_plies` and
    `given_plies`, or None when not even the first move is a book line.
    """
    column, value = normalize_moves(moves)
    tokens = value.split()
    for length in range(min(len(tokens), MAX_BOOK_PLY), 0, -1):
        row = conn.execute(
            f"SELECT {RESULT_COLUMNS} FROM openings WHERE {column} = ?",
            (" ".join(tokens[:length]),),
        ).fetchone()
        if row:
            return {**dict(row), "matched_plies": length, "given_plies": len(tokens)}
    return None
