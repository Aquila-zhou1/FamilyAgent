import pytest

from familyagent.lichess.client import LichessMalformed, LichessRateLimited, LichessTimeout, LichessUnavailable
from familyagent.mcp_servers import faults


@pytest.fixture(autouse=True)
def reset():
    faults.set_mode("none")
    yield
    faults.set_mode("none")


def test_none_does_nothing():
    faults.apply()


@pytest.mark.parametrize("mode,error", [
    ("timeout", LichessTimeout), ("rate_limited", LichessRateLimited),
    ("http_500", LichessUnavailable), ("malformed", LichessMalformed),
])
def test_each_mode_raises_the_matching_error(mode, error):
    faults.set_mode(mode)
    with pytest.raises(error, match="No puzzle data was retrieved"):
        faults.apply()


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        faults.set_mode("explode")
