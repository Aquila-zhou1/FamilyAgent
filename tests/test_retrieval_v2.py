import pytest

from familyagent.openings import db
from familyagent.openings.retrieve import extract_moves, retrieve


@pytest.fixture(scope="module")
def conn():
    return db.build()


def names(conn, question):
    return [r["name"] for r in retrieve(conn, question, impl="v2", limit=3)]


def test_extract_moves_from_sentence():
    assert extract_moves("Which opening is 1. e4 e5 2. f4 exf4?") == "e4 e5 f4 exf4"
    assert extract_moves("played g1f3 d7d5 c2c4 - what opening") == "g1f3 d7d5 c2c4"
    assert extract_moves("Can you show me the Queen's Indian Defense, with e3") is None


def test_longest_prefix_for_moves_beyond_the_book(conn):
    got = names(conn, "Which opening is 1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Nc3 Nxe4?")
    assert got == ["Four Knights Game: Italian Variation"]


def test_exact_name_inside_a_sentence(conn):
    assert names(conn, "What are the moves of the Scotch Game: Scotch Gambit?")[0] == "Scotch Game: Scotch Gambit"


def test_typo_and_british_spelling(conn):
    assert "Vienna Game" in names(conn, "viena game frankenstein dracula")[0]
    assert names(conn, "Pirc Defence Austrian Attack")[0] == "Pirc Defense: Austrian Attack"


def test_unknown_opening_returns_nothing(conn):
    assert names(conn, "Tell me about the Lunar Pawn Storm.") == []
    assert names(conn, "") == []


def test_fewest_extra_words_first(conn):
    assert names(conn, "King's Indian Defense: Fianchetto Variation")[0] == "King's Indian Defense: Fianchetto Variation"
