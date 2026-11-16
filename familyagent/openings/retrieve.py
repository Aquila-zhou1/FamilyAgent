"""Question -> ranked openings. One entry point, several implementations.

Evaluation calls `retrieve(conn, question, impl)` with the raw user question,
so implementations can be compared on identical cases.

- "substring": iteration-1 lookup. The whole question must be an opening name
  fragment or an exact move sequence.
- "bm25": keyword search over opening names (SQLite FTS5), plus the exact
  move-sequence match. A reasonable first implementation; no typo handling and
  no move extraction from sentences.
- "v2": what bm25 lacks, one fix per failure class found in the evaluation:
  moves are extracted from the sentence and matched by longest prefix;
  filler words are dropped; misspelled words are corrected against the
  vocabulary of opening names; all remaining words must match (AND); a word
  that is neither filler nor close to any known word means the opening is not
  in the database, so nothing is returned instead of a wrong near-match.
"""

import difflib
import unicodedata
from functools import lru_cache

import re
import sqlite3
from collections.abc import Callable

from familyagent.openings.search import (
    RESULT_COLUMNS,
    find_deepest_opening,
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


# ---- v2 -------------------------------------------------------------------

_SAN_LIKE = re.compile(
    r"^(?:O-O(?:-O)?|0-0(?:-0)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=?[QRBN])?)[+#]?$"
)
_MOVE_NUMBER = re.compile(r"\b\d+\.+")
_TRIM = ".,;:!?\"()[]"
MIN_RUN = 3  # fewer consecutive moves than this is more likely a name fragment ("with e3")
TYPO_CUTOFF = 0.84
MIN_TYPO_LEN = 5

# Articles and prepositions are dropped from the match (users add "the ... of" freely);
# "with", "opening" and "variation" stay because they separate real names ("..., with e3").
_FILLER = frozenset(
    "the of a an and or in on at to for from by is are was were be do does did what which who how "
    "can could would you your me my i we this that these it its show tell give find name "
    "called call about moves move start starts started eco code played play after please "
    "ok okay line lines".split()
)
_SPELLING = {"defence": "defense", "defences": "defenses"}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _words(text: str) -> list[str]:
    return [_SPELLING.get(w, w) for w in _WORD.findall(_fold(text))]


@lru_cache(maxsize=4)
def _vocabulary(conn: sqlite3.Connection) -> frozenset[str]:
    vocab: set[str] = set()
    for (name,) in conn.execute("SELECT DISTINCT name FROM openings"):
        vocab.update(_words(name))
    return frozenset(vocab)


def extract_moves(question: str) -> str | None:
    """The longest run of consecutive move-looking tokens (SAN or UCI), if long enough."""
    tokens = _MOVE_NUMBER.sub(" ", question).split()
    best: list[str] = []
    run: list[str] = []
    for raw in tokens + [""]:
        token = raw.strip(_TRIM) if raw else ""
        if token and _SAN_LIKE.match(token):
            run.append(token)
            continue
        if len(run) > len(best):
            best = run
        run = []
    return " ".join(best) if len(best) >= MIN_RUN else None


def _name_terms(conn: sqlite3.Connection, question: str) -> list[str] | None:
    """Content words of the question, spelling-corrected; None if one is unknown."""
    vocab = _vocabulary(conn)
    terms: list[str] = []
    for word in _words(question):
        if word in _FILLER or (len(word) < 2 and not word.isdigit()):
            continue
        if word in vocab:
            terms.append(word)
            continue
        close = (
            difflib.get_close_matches(word, vocab, n=1, cutoff=TYPO_CUTOFF)
            if len(word) >= MIN_TYPO_LEN
            else []
        )
        if not close:
            return None
        terms.append(close[0])
    return terms


def _distinct_by_name(rows: list[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    out = []
    for row in rows:
        if row["name"] not in seen:
            seen.add(row["name"])
            out.append(row)
    return out[:limit]


def _v2(conn: sqlite3.Connection, question: str, limit: int) -> list[dict]:
    moves = extract_moves(question)
    if moves:
        found = find_deepest_opening(conn, moves)
        if found:
            return [found]
    terms = _name_terms(conn, question)
    if not terms:
        return []
    match = " ".join(f'"{t}"' for t in terms)  # FTS5: space = AND
    columns = ", ".join(f"o.{c.strip()}" for c in RESULT_COLUMNS.split(","))
    cursor = conn.execute(
        f"SELECT {columns} FROM openings_fts f JOIN openings o ON o.id = f.rowid "
        "WHERE openings_fts MATCH ? ORDER BY bm25(openings_fts), o.ply, o.id LIMIT ?",
        (match, limit * 20),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    # bm25 rewards repeated words ("..., Immediate Fianchetto"); the user asked for the name
    # with the fewest words they did not ask for, so that goes first (stable: bm25 breaks ties).
    wanted = set(terms)
    rows.sort(key=lambda r: len(set(_words(r["name"])) - wanted))
    return _distinct_by_name(rows, limit)


IMPLEMENTATIONS: dict[str, Callable[[sqlite3.Connection, str, int], list[dict]]] = {
    "substring": _substring,
    "bm25": _bm25,
    "v2": _v2,
}


def retrieve(
    conn: sqlite3.Connection, question: str, impl: str = "bm25", limit: int = 3
) -> list[dict]:
    if impl not in IMPLEMENTATIONS:
        raise ValueError(f"unknown impl {impl!r}; choose from {sorted(IMPLEMENTATIONS)}")
    return IMPLEMENTATIONS[impl](conn, question, limit)
