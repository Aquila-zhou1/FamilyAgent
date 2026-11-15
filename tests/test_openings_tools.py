"""JSON payloads returned by the openings tools."""

import json

import pytest

from familyagent.openings import db
from familyagent.openings.tools import find_opening_by_moves_tool, search_openings_tool


@pytest.fixture(scope="module")
def conn():
    return db.build()


def test_search_tool_returns_matches(conn):
    payload = json.loads(search_openings_tool(conn, " Sicilian Defense ", "bm25"))
    assert payload["query"] == "Sicilian Defense"
    assert payload["count"] == 3
    assert set(payload["results"][0]) == {"name", "eco", "moves"}


def test_search_tool_reports_no_match(conn):
    payload = json.loads(search_openings_tool(conn, "Flying Hippo", "substring"))
    assert payload["count"] == 0 and payload["results"] == []
    assert "No opening" in payload["note"]


def test_moves_tool_found_and_not_found(conn):
    found = json.loads(find_opening_by_moves_tool(conn, "e4 e5 Nf3 Nc6 Bb5 h5 h4"))
    assert found["found"] is True
    assert found["name"].startswith("Ruy Lopez")
    assert (found["matched_half_moves"], found["given_half_moves"]) == (5, 7)

    missing = json.loads(find_opening_by_moves_tool(conn, "h7h5"))
    assert missing == {"found": False, "note": "No opening in the database starts with these moves."}


@pytest.mark.parametrize("call", [
    lambda c: search_openings_tool(c, "  ", "bm25"),
    lambda c: find_opening_by_moves_tool(c, ""),
])
def test_empty_input_is_an_error(conn, call):
    with pytest.raises(ValueError):
        call(conn)
