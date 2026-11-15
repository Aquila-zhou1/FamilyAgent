"""Lichess client: parsing, replay, recording and every failure mode.

No network: the HTTP call is replaced by a function.
"""

import json

import pytest

from familyagent.lichess import client as lichess
from familyagent.lichess.client import LichessClient

SAMPLE = {
    "game": {
        "id": "AHGPFfP2",
        "perf": {"key": "rapid", "name": "Rapid"},
        "rated": True,
        "players": [],
        "pgn": "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6",
        "clock": "10+0",
    },
    "puzzle": {
        "id": "PSjmf",
        "rating": 2705,
        "plays": 97,
        "solution": ["e8e7", "c3d5", "e7e8q"],
        "themes": ["endgame", "short"],
        "initialPly": 52,
    },
}


def fake_fetch(status=200, body=None, calls=None):
    def fetch(url, timeout):
        if calls is not None:
            calls.append((url, timeout))
        return status, json.dumps(SAMPLE) if body is None else body

    return fetch


def test_daily_live_returns_summary():
    calls = []
    result = LichessClient(fetch=fake_fetch(calls=calls), timeout=3).daily()
    assert calls == [("https://lichess.org/api/puzzle/daily", 3)]
    assert result["puzzle_id"] == "PSjmf"
    assert result["solution_uci"] == ["e8e7", "c3d5", "e7e8q"]
    assert result["game_moves_san"].startswith("e4 e5")
    assert result["source"] == "live"


def test_puzzle_by_id_uses_id_in_url():
    calls = []
    LichessClient(fetch=fake_fetch(calls=calls)).puzzle(" PSjmf ")
    assert calls[0][0] == "https://lichess.org/api/puzzle/PSjmf"


@pytest.mark.parametrize(
    "status, body, error",
    [
        (404, "{}", lichess.LichessNotFound),
        (429, "{}", lichess.LichessRateLimited),
        (500, "oops", lichess.LichessUnavailable),
        (200, "<html>not json</html>", lichess.LichessMalformed),
        (200, '{"puzzle": {"id": "x"}}', lichess.LichessMalformed),
        (200, '{"game": {"id": "g", "pgn": "e4"}, "puzzle": {"id": "abc", "solution": []}}',
         lichess.LichessMalformed),
        (200, '{"game": {"id": "g", "pgn": "e4"}, "puzzle": {"id": "abc", "solution": ["Nf3"]}}',
         lichess.LichessMalformed),
        (200, "[1, 2]", lichess.LichessMalformed),
    ],
)
def test_failures_are_typed_and_say_nothing_was_retrieved(status, body, error):
    with pytest.raises(error) as info:
        LichessClient(fetch=fake_fetch(status, body)).puzzle("abc12")
    assert "No puzzle data was retrieved" in str(info.value)
    assert isinstance(info.value, lichess.LichessError)


def test_invalid_id_is_rejected_without_a_request():
    calls = []
    with pytest.raises(lichess.LichessNotFound):
        LichessClient(fetch=fake_fetch(calls=calls)).puzzle("../etc/passwd")
    assert calls == []


def test_fetch_errors_propagate():
    def fetch(url, timeout):
        raise lichess.LichessTimeout("Lichess did not answer. No puzzle data was retrieved.")

    with pytest.raises(lichess.LichessTimeout):
        LichessClient(fetch=fetch).daily()


def test_record_then_replay(tmp_path):
    live = LichessClient(fetch=fake_fetch(), fixtures_dir=tmp_path, record=True)
    live.daily()
    live.puzzle("PSjmf")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["daily.json", "puzzle_PSjmf.json"]

    def no_network(url, timeout):
        raise AssertionError("replay mode must not call the network")

    replay = LichessClient(mode="replay", fixtures_dir=tmp_path, fetch=no_network)
    assert replay.daily()["solution_uci"] == ["e8e7", "c3d5", "e7e8q"]
    assert replay.puzzle("PSjmf")["source"] == "replay"


def test_replay_missing_fixtures(tmp_path):
    replay = LichessClient(mode="replay", fixtures_dir=tmp_path)
    with pytest.raises(lichess.LichessNotFound):
        replay.puzzle("zzzzz")
    with pytest.raises(lichess.LichessUnavailable):
        replay.daily()


def test_failed_response_is_not_recorded(tmp_path):
    client = LichessClient(fetch=fake_fetch(500, "x"), fixtures_dir=tmp_path, record=True)
    with pytest.raises(lichess.LichessUnavailable):
        client.daily()
    assert list(tmp_path.iterdir()) == []


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        LichessClient(mode="offline")


def test_solution_is_converted_to_san_from_the_real_recording():
    """Uses the recorded daily puzzle f9Xve; needs python-chess."""
    pytest.importorskip("chess")
    from pathlib import Path

    fixtures = Path(__file__).resolve().parent.parent / "eval" / "fixtures" / "lichess"
    if not (fixtures / "puzzle_f9Xve.json").exists():
        pytest.skip("recording not present")
    result = LichessClient(mode="replay", fixtures_dir=fixtures).puzzle("f9Xve")
    assert result["solution_uci"] == ["g6h6", "f7h7", "h6f8"]
    assert result["solution_san"] == ["Qxh6+", "Rh7", "Qxf8#"]
    assert result["side_to_move"] == "white"


def test_solution_san_falls_back_to_replaying_the_game():
    pytest.importorskip("chess")
    # No FEN: the position is rebuilt from the game moves (Scholar's mate).
    converted = lichess.solution_in_san(None, "e4 e5 Bc4 Nc6 Qh5 Nf6", ["h5f7"])
    assert converted == {"solution_san": ["Qxf7#"], "side_to_move": "white"}


def test_solution_san_is_omitted_when_moves_do_not_fit_the_position():
    assert lichess.solution_in_san(None, "e4 e5", ["a1a8"]) == {}
    assert lichess.solution_in_san("not a fen", "", ["e2e4"]) == {}
