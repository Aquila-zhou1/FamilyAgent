"""Question -> ranked openings. One entry point, several implementations.

Evaluation calls `retrieve(conn, question, impl)` with the raw user question,
so implementations can be compared on identical cases.

- "substring": iteration-1 lookup. The whole question must be an opening name
  fragment or an exact move sequence.
- "bm25": keyword search over opening names (SQLite FTS5), plus the exact
  move-sequence match. A reasonable first implementation; no typo handling and
  no move extraction from sentences.
"""

import re
import sqlite3
from collections.abc import Callable

from familyagent.openings.search import (
    RESULT_COLUMNS,
    find_opening_by_moves,
    search_openings,
)

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _substring(conn: sqlite3.Connection, question: str, limit: int) -> list[dict]:
    return search_openings(conn, question, limit) or find_opening_by_moves(
        conn, question, limit
    )


def _bm25(conn: sqlite3.Connection, question: str, limit: int) -> list[dict]:
    by_moves = find_opening_by_moves(conn, question, limit)
    if by_moves:
        return by_moves
    words = _WORD.findall(question)
    if not words:
        return []
    match = " OR ".join(f'"{w}"' for w in words)
    columns = ", ".join(f"o.{c.strip()}" for c in RESULT_COLUMNS.split(","))
    cursor = conn.execute(
        f"SELECT {columns} FROM openings_fts f JOIN openings o ON o.id = f.rowid "
        "WHERE openings_fts MATCH ? ORDER BY bm25(openings_fts), o.ply, o.id LIMIT ?",
        (match, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


IMPLEMENTATIONS: dict[str, Callable[[sqlite3.Connection, str, int], list[dict]]] = {
    "substring": _substring,
    "bm25": _bm25,
}


def retrieve(
    conn: sqlite3.Connection, question: str, impl: str = "bm25", limit: int = 3
) -> list[dict]:
    if impl not in IMPLEMENTATIONS:
        raise ValueError(f"unknown impl {impl!r}; choose from {sorted(IMPLEMENTATIONS)}")
    return IMPLEMENTATIONS[impl](conn, question, limit)
