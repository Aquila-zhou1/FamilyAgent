"""Openings database and baseline lookup, run against the bundled dataset."""

import pytest

from familyagent.openings import db
from familyagent.openings.search import (
    find_opening_by_moves,
    normalize_moves,
    search_openings,
)


@pytest.fixture(scope="module")
def conn():
    return db.build()


def test_dataset_is_complete(conn):
    assert conn.execute("SELECT COUNT(*) FROM openings").fetchone()[0] == 3704
    assert conn.execute("SELECT COUNT(*) FROM openings_fts").fetchone()[0] == 3704
    assert db.DEFAULT_CSV.stat().st_size < 2 * 1024 * 1024


def test_pgn_to_san():
    assert db.pgn_to_san("1. e4 c5 2. Nf3 Nc6") == "e4 c5 Nf3 Nc6"
    assert db.pgn_to_san("1.e4 c5 2.Nf3") == "e4 c5 Nf3"


def test_search_by_name(conn):
    results = search_openings(conn, "Sicilian Defense")
    assert len(results) == 3
    assert results[0]["name"] == "Sicilian Defense"
    assert results[0]["uci"] == "e2e4 c7c5"
    assert set(results[0]) == {"id", "eco", "name", "pgn", "uci"}


def test_search_by_name_is_case_insensitive(conn):
    assert search_openings(conn, "sicilian defense")[0]["name"] == "Sicilian Defense"


def test_search_by_name_no_result(conn):
    assert search_openings(conn, "Flying Hippo Countergambit") == []
    assert search_openings(conn, "   ") == []
    assert search_openings(conn, "%") == []


def test_find_by_moves_uci_and_san_agree(conn):
    by_uci = find_opening_by_moves(conn, "e2e4 c7c5")
    assert by_uci[0]["name"] == "Sicilian Defense"
    assert find_opening_by_moves(conn, "1. e4 c5") == by_uci
    assert find_opening_by_moves(conn, "e4 c5") == by_uci


def test_find_by_moves_known_row(conn):
    results = find_opening_by_moves(
        conn, "1. e4 c5 2. Nf3 Nc6 3. Bb5 g6 4. O-O Bg7 5. c3 Nf6 6. Qa4"
    )
    assert [r["eco"] for r in results] == ["B31"]
    assert "Totsky Attack" in results[0]["name"]


def test_find_by_moves_no_result(conn):
    assert find_opening_by_moves(conn, "a2a4 h7h5 a4a5 h5h4") == []
    assert find_opening_by_moves(conn, "") == []


def test_normalize_moves():
    assert normalize_moves("E2E4  c7c5") == ("uci", "e2e4 c7c5")
    assert normalize_moves("1. e4 c5 2. Nf3") == ("san", "e4 c5 Nf3")
