"""Lichess puzzle API client with live and replay modes.

- live:   call https://lichess.org/api/puzzle/...
- replay: read a previously recorded response from the fixtures directory, so
          evaluation runs are repeatable and do not load the public API.

Every failure is raised as a `LichessError` subclass with a message that says
plainly that no puzzle data was retrieved.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path

BASE_URL = "https://lichess.org/api/puzzle"
USER_AGENT = "familyagent-chess/0.2 (personal evaluation project)"
_PUZZLE_ID = re.compile(r"^[A-Za-z0-9]{3,12}$")
_UCI_MOVE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")

# (url, timeout_seconds) -> (status_code, body_text)
Fetch = Callable[[str, float], tuple[int, str]]


class LichessError(Exception):
    """Base class. `code` is a short machine-readable reason."""

    code = "error"


class LichessTimeout(LichessError):
    code = "timeout"


class LichessRateLimited(LichessError):
    code = "rate_limited"


class LichessNotFound(LichessError):
    code = "not_found"


class LichessUnavailable(LichessError):
    code = "unavailable"


class LichessMalformed(LichessError):
    code = "malformed"


def http_fetch(url: str, timeout: float) -> tuple[int, str]:
    import httpx

    try:
        response = httpx.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            follow_redirects=True,
        )
    except httpx.TimeoutException as exc:
        raise LichessTimeout(
            f"Lichess did not answer within {timeout:g} seconds. No puzzle data was retrieved."
        ) from exc
    except httpx.HTTPError as exc:
        raise LichessUnavailable(
            f"Could not reach Lichess ({type(exc).__name__}). No puzzle data was retrieved."
        ) from exc
    return response.status_code, response.text


def solution_in_san(fen: object, game_moves: str, solution: list[str]) -> dict:
    """Convert the UCI solution to SAN with python-chess (never by the model).

    Uses the puzzle position (FEN) when Lichess provides it, otherwise replays
    the source game. Returns {} if the conversion is not possible, so a puzzle
    is still served with its UCI solution.
    """
    try:
        import chess

        if isinstance(fen, str) and fen:
            board = chess.Board(fen)
        else:
            board = chess.Board()
            for san in game_moves.split():
                board.push_san(san)
        side = "white" if board.turn == chess.WHITE else "black"
        moves = []
        for uci in solution:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                return {}
            moves.append(board.san(move))
            board.push(move)
    except Exception:  # noqa: BLE001 - optional enrichment must never break the tool
        return {}
    return {"solution_san": moves, "side_to_move": side}


def summarize(data: object) -> dict:
    """Keep the fields the agent needs; reject anything that is not a puzzle."""
    try:
        puzzle, game = data["puzzle"], data["game"]  # type: ignore[index]
        puzzle_id = puzzle["id"]
        solution = puzzle["solution"]
        game_moves = game["pgn"]
        game_id = game["id"]
    except (KeyError, TypeError) as exc:
        raise LichessMalformed(
            "Lichess returned an unexpected response format. No puzzle data was retrieved."
        ) from exc
    if (
        not isinstance(puzzle_id, str)
        or not isinstance(game_moves, str)
        or not isinstance(solution, list)
        or not solution
        or not all(isinstance(m, str) and _UCI_MOVE.match(m) for m in solution)
    ):
        raise LichessMalformed(
            "Lichess returned an unexpected response format. No puzzle data was retrieved."
        )
    return {
        "puzzle_id": puzzle_id,
        "rating": puzzle.get("rating"),
        "themes": puzzle.get("themes", []),
        "solution_uci": solution,
        **solution_in_san(puzzle.get("fen"), game_moves, solution),
        "solution_note": (
            "solution_uci and solution_san are the same moves in two notations, in order, "
            "alternating sides and starting with the side to move in the puzzle position."
        ),
        "puzzle_url": f"https://lichess.org/training/{puzzle_id}",
        "game_id": game_id,
        "game_moves_san": game_moves,
        "game_moves_note": "Moves of the source game up to the puzzle position.",
    }


class LichessClient:
    def __init__(
        self,
        mode: str = "live",
        fixtures_dir: str | Path = "eval/fixtures/lichess",
        timeout: float = 5.0,
        record: bool = False,
        fetch: Fetch = http_fetch,
    ) -> None:
        if mode not in ("live", "replay"):
            raise ValueError(f"mode must be 'live' or 'replay', got {mode!r}")
        self.mode = mode
        self.fixtures_dir = Path(fixtures_dir)
        self.timeout = timeout
        self.record = record
        self.fetch = fetch

    def daily(self) -> dict:
        return self._get("daily", f"{BASE_URL}/daily", "daily.json")

    def puzzle(self, puzzle_id: str) -> dict:
        puzzle_id = puzzle_id.strip()
        if not _PUZZLE_ID.match(puzzle_id):
            raise LichessNotFound(
                f"{puzzle_id!r} is not a valid Lichess puzzle ID. No puzzle data was retrieved."
            )
        return self._get(puzzle_id, f"{BASE_URL}/{puzzle_id}", f"puzzle_{puzzle_id}.json")

    def _get(self, label: str, url: str, fixture_name: str) -> dict:
        fixture = self.fixtures_dir / fixture_name
        if self.mode == "replay":
            if not fixture.exists():
                if label == "daily":
                    raise LichessUnavailable(
                        "No recorded daily puzzle is available in replay mode. "
                        "No puzzle data was retrieved."
                    )
                raise LichessNotFound(
                    f"Lichess has no puzzle with ID {label!r}. No puzzle data was retrieved."
                )
            body = fixture.read_text(encoding="utf-8")
        else:
            status, body = self.fetch(url, self.timeout)
            if status == 404:
                raise LichessNotFound(
                    f"Lichess has no puzzle with ID {label!r}. No puzzle data was retrieved."
                )
            if status == 429:
                raise LichessRateLimited(
                    "Lichess rate limit reached (HTTP 429). Wait a minute before retrying. "
                    "No puzzle data was retrieved."
                )
            if status != 200:
                raise LichessUnavailable(
                    f"Lichess answered with HTTP {status}. No puzzle data was retrieved."
                )

        try:
            data = json.loads(body)
        except ValueError as exc:
            raise LichessMalformed(
                "Lichess returned a response that is not valid JSON. "
                "No puzzle data was retrieved."
            ) from exc
        summary = summarize(data)

        if self.mode == "live" and self.record:
            self.fixtures_dir.mkdir(parents=True, exist_ok=True)
            fixture.write_text(
                json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        return {**summary, "source": self.mode}
