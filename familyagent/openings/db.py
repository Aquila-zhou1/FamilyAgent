"""Openings database: an in-memory SQLite built from the bundled CSV.

The CSV (3.7k rows) is the source of truth and is committed to the repository,
so there is no database file to ship or migrate. `id` is the row's position in
the original dataset and is the stable identifier used by evaluation cases.
"""

import csv
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "openings.csv"
CSV_COLUMNS = ["id", "eco_volume", "eco", "name", "pgn", "uci", "epd"]

_MOVE_NUMBER = re.compile(r"\d+\.(\.\.)?")


def pgn_to_san(pgn: str) -> str:
    """'1. e4 c5 2. Nf3' -> 'e4 c5 Nf3'."""
    return " ".join(_MOVE_NUMBER.sub(" ", pgn).split())


def build(csv_path: Path | str = DEFAULT_CSV) -> sqlite3.Connection:
    """Load the CSV into a new in-memory database and return the connection."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Create it with scripts/build_openings_csv.py."
        )

    # check_same_thread=False: the data is read-only after build, and FastAPI
    # serves sync endpoints from a thread pool.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE openings (
            id         INTEGER PRIMARY KEY,
            eco_volume TEXT NOT NULL,
            eco        TEXT NOT NULL,
            name       TEXT NOT NULL,
            pgn        TEXT NOT NULL,
            uci        TEXT NOT NULL,
            epd        TEXT NOT NULL,
            san        TEXT NOT NULL,   -- pgn without move numbers
            ply        INTEGER NOT NULL -- number of half-moves
        );
        CREATE INDEX idx_openings_uci ON openings(uci);
        CREATE INDEX idx_openings_san ON openings(san);
        CREATE VIRTUAL TABLE openings_fts USING fts5(name);
        """
    )

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path} is missing columns: {sorted(missing)}")
        rows = [
            (
                int(r["id"]), r["eco_volume"], r["eco"], r["name"], r["pgn"],
                r["uci"], r["epd"], pgn_to_san(r["pgn"]), len(r["uci"].split()),
            )
            for r in reader
        ]

    conn.executemany("INSERT INTO openings VALUES (?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO openings_fts(rowid, name) SELECT id, name FROM openings")
    conn.commit()
    return conn


@lru_cache(maxsize=1)
def get_connection() -> sqlite3.Connection:
    """Shared connection for the application, built on first use."""
    return build()
