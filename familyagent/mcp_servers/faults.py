"""Fault injection for the evaluation (off unless EVAL_FAULTS=true).

The lichess server calls `apply()` before every tool call. The evaluation
runner switches the mode with POST /_fault {"mode": "..."}; "none" restores
normal behaviour. The errors raised are the same typed errors the real client
raises, so the agent sees exactly what a real upstream failure would produce.
(The timeout is simulated: it raises at once instead of waiting.)
"""

from familyagent.lichess.client import (
    LichessMalformed,
    LichessRateLimited,
    LichessTimeout,
    LichessUnavailable,
)

MODES = ("none", "timeout", "rate_limited", "http_500", "malformed")

_state = {"mode": "none"}


def set_mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(f"unknown fault mode {mode!r}; expected one of {MODES}")
    _state["mode"] = mode


def get_mode() -> str:
    return _state["mode"]


def apply() -> None:
    mode = _state["mode"]
    if mode == "timeout":
        raise LichessTimeout("Lichess did not answer within 5 seconds. No puzzle data was retrieved.")
    if mode == "rate_limited":
        raise LichessRateLimited(
            "Lichess rate limit reached (HTTP 429). Wait a minute before retrying. "
            "No puzzle data was retrieved."
        )
    if mode == "http_500":
        raise LichessUnavailable("Lichess answered with HTTP 500. No puzzle data was retrieved.")
    if mode == "malformed":
        raise LichessMalformed(
            "Lichess returned an unexpected response format. No puzzle data was retrieved."
        )
