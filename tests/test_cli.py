"""CLI tests -- no real network.

The CLI is a thin shell over YahooClient, so the client is faked and its canned
result is rendered; the tests pin the text/JSON output, the error contract (a domain
failure becomes `pyyahoo: ...` on stderr and exit 1), and argparse's own guards.
"""

import json
from datetime import date

import pytest

from pyyahoo import YahooRequestError
from pyyahoo.cli import main
from pyyahoo.price import Dividend, PriceBar, PriceHistory, Split
from pyyahoo.profile import Profile

_HISTORY = PriceHistory(
    symbol="AAPL",
    bars=(
        PriceBar(date(2024, 1, 2), 185.0, 186.9, 184.0, 185.60, 185.60, 50_000_000),
        PriceBar(date(2024, 1, 3), 184.2, 185.0, 183.0, 184.30, 184.30, None),
    ),
    splits=(Split(date(2020, 8, 31), 4, 1),),
    dividends=(Dividend(date(2024, 2, 9), 0.24),),
)

_EMPTY_HISTORY = PriceHistory(symbol="MU", bars=(), splits=(), dividends=())

_PROFILE = Profile(
    symbol="AAPL", name="Apple Inc.", sector="Technology",
    industry="Consumer Electronics", currency="USD", market_cap=3_000_000_000_000,
    shares_outstanding=None, trailing_pe=29.1, forward_pe=None, price_to_book=None,
    trailing_eps=None, revenue_growth=None, earnings_growth=None, profit_margin=None,
    operating_margin=None, return_on_equity=None, fifty_two_week_high=None,
    fifty_two_week_low=None, beta=None,
)


class _FakeYahoo:
    """Stands in for YahooClient: a context manager returning canned results, or
    raising a scripted error from the fetch methods."""

    def __init__(self, *, history=None, profile=None, error=None):
        self._history = history
        self._profile = profile
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def fetch_history(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._history

    def fetch_profile(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._profile


def _install(monkeypatch, **kwargs):
    monkeypatch.setattr("pyyahoo.cli.YahooClient", lambda *a, **k: _FakeYahoo(**kwargs))


def test_history_text_shows_the_summary_and_recent_bars(monkeypatch, capsys):
    _install(monkeypatch, history=_HISTORY)
    assert main(["history", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "AAPL  2 bars  (1 splits, 1 dividends)" in out
    assert "2024-01-03" in out
    assert "vol -" in out                       # a None volume renders as a dash, not 0


def test_history_json_is_valid_and_carries_the_bars(monkeypatch, capsys):
    _install(monkeypatch, history=_HISTORY)
    assert main(["history", "AAPL", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "AAPL"
    assert len(payload["bars"]) == 2
    assert payload["bars"][0]["trade_date"] == "2024-01-02"   # date rendered as ISO string


def test_history_with_no_bars_says_so(monkeypatch, capsys):
    _install(monkeypatch, history=_EMPTY_HISTORY)
    assert main(["history", "MU"]) == 0
    assert "no bars in range" in capsys.readouterr().out


def test_profile_text_skips_none_fields(monkeypatch, capsys):
    _install(monkeypatch, profile=_PROFILE)
    assert main(["profile", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "sector" in out and "Technology" in out
    assert "beta" not in out                    # a None field is not printed


def test_profile_json_carries_every_field(monkeypatch, capsys):
    _install(monkeypatch, profile=_PROFILE)
    assert main(["profile", "AAPL", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "Apple Inc."
    assert payload["beta"] is None              # JSON keeps the full shape, Nones included


def test_a_domain_error_is_one_line_on_stderr_and_exit_1(monkeypatch, capsys):
    _install(monkeypatch, error=YahooRequestError("Not Found"))
    assert main(["history", "NOSUCH"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "pyyahoo: Not Found"


def test_timeframe_word_maps_to_the_enum(monkeypatch, capsys):
    seen = {}

    class _Recorder(_FakeYahoo):
        def fetch_history(self, symbol, **kwargs):
            seen.update(kwargs)
            return _HISTORY

    monkeypatch.setattr("pyyahoo.cli.YahooClient", lambda *a, **k: _Recorder(history=_HISTORY))
    from pyyahoo import Timeframe
    assert main(["history", "AAPL", "--timeframe", "week"]) == 0
    assert seen["timeframe"] is Timeframe.WEEK


def test_a_bad_start_date_is_rejected_by_argparse(capsys):
    with pytest.raises(SystemExit):
        main(["history", "AAPL", "--start", "not-a-date"])


def test_no_subcommand_exits_nonzero():
    with pytest.raises(SystemExit):
        main([])
