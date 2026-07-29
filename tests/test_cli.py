"""CLI tests -- no real network.

The CLI is a thin shell over YahooClient, so the client is faked and its canned
result is rendered; the tests pin the text/JSON output, the error contract (a domain
failure becomes `finyahoo: ...` on stderr and exit 1), and argparse's own guards.
"""

import json
import subprocess
import sys
from datetime import date

import pytest

from finyahoo import Timeframe, YahooRequestError
from finyahoo.cli import main
from finyahoo.price import Dividend, PriceBar, PriceHistory, Split
from finyahoo.profile import Profile

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


def _install_fake_yahoo_client(monkeypatch, **kwargs):
    monkeypatch.setattr("finyahoo.cli.YahooClient", lambda *a, **k: _FakeYahoo(**kwargs))


def test_history_text_shows_the_summary_and_recent_bars(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, history=_HISTORY)
    assert main(["history", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "AAPL  2 bars  (1 splits, 1 dividends)" in out
    assert "2024-01-03" in out
    assert "vol -" in out                       # a None volume renders as a dash, not 0


def test_history_json_is_valid_and_carries_the_bars(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, history=_HISTORY)
    assert main(["history", "AAPL", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "AAPL"
    assert len(payload["bars"]) == 2
    assert payload["bars"][0]["trade_date"] == "2024-01-02"   # date rendered as ISO string


def test_history_with_no_bars_says_so(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, history=_EMPTY_HISTORY)
    assert main(["history", "MU"]) == 0
    assert "no bars in range" in capsys.readouterr().out


def test_profile_text_skips_none_fields(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, profile=_PROFILE)
    assert main(["profile", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "sector" in out and "Technology" in out
    assert "beta" not in out                    # a None field is not printed


def test_profile_json_carries_every_field(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, profile=_PROFILE)
    assert main(["profile", "AAPL", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "Apple Inc."
    assert payload["beta"] is None              # JSON keeps the full shape, Nones included


def test_a_domain_error_is_one_line_on_stderr_and_exit_1(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, error=YahooRequestError("Not Found"))
    assert main(["history", "NOSUCH"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "finyahoo: Not Found"


def test_history_forwards_symbol_start_end_and_timeframe(monkeypatch):
    """Every argument reaches fetch_history, not just the timeframe -- a dropped or
    swapped symbol/start/end would otherwise ship green."""
    calls = []

    class _Recorder(_FakeYahoo):
        def fetch_history(self, symbol, **kwargs):
            calls.append((symbol, kwargs))
            return _HISTORY

    monkeypatch.setattr("finyahoo.cli.YahooClient", lambda *a, **k: _Recorder(history=_HISTORY))
    exit_code = main(["history", "AAPL", "--start", "2024-01-01",
                      "--end", "2024-01-31", "--timeframe", "week"])
    assert exit_code == 0
    assert calls == [("AAPL", {"start": date(2024, 1, 1), "end": date(2024, 1, 31),
                               "timeframe": Timeframe.WEEK})]


def test_history_text_prints_the_five_most_recent_bars_oldest_first(monkeypatch, capsys):
    """The tail is the last five bars in ascending date order; the sixth-from-last is
    dropped from the text view (the full series is only in --json)."""
    bars = tuple(
        PriceBar(date(2024, 1, day), 1.0, 1.0, 1.0, 1.0, 1.0, 1) for day in range(1, 7)
    )
    history = PriceHistory(symbol="AAPL", bars=bars, splits=(), dividends=())
    monkeypatch.setattr("finyahoo.cli.YahooClient", lambda *a, **k: _FakeYahoo(history=history))
    assert main(["history", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "2024-01-01" not in out                       # the oldest bar is dropped
    shown = [line for line in out.splitlines() if line.startswith("  2024-")]
    assert [line.split()[0] for line in shown] == ["2024-01-02", "2024-01-03",
                                                    "2024-01-04", "2024-01-05", "2024-01-06"]


def test_profile_text_with_all_fields_missing_prints_only_the_symbol(monkeypatch, capsys):
    """An index carries almost no fundamentals; with every optional field None the
    render must still succeed (no empty-max crash) and print just the symbol."""
    bare = Profile(
        symbol="^GSPC", name=None, sector=None, industry=None, currency=None,
        market_cap=None, shares_outstanding=None, trailing_pe=None, forward_pe=None,
        price_to_book=None, trailing_eps=None, revenue_growth=None, earnings_growth=None,
        profit_margin=None, operating_margin=None, return_on_equity=None,
        fifty_two_week_high=None, fifty_two_week_low=None, beta=None,
    )
    monkeypatch.setattr("finyahoo.cli.YahooClient", lambda *a, **k: _FakeYahoo(profile=bare))
    assert main(["profile", "^GSPC"]) == 0
    assert capsys.readouterr().out.strip() == "symbol  ^GSPC"


def test_a_bad_start_date_is_rejected_by_argparse():
    with pytest.raises(SystemExit):
        main(["history", "AAPL", "--start", "not-a-date"])


def test_an_invalid_timeframe_is_rejected_by_argparse():
    """The choices= guard rejects a word outside day/week/month before any network."""
    with pytest.raises(SystemExit):
        main(["history", "AAPL", "--timeframe", "year"])


def test_no_subcommand_exits_nonzero():
    with pytest.raises(SystemExit):
        main([])


def test_python_m_finyahoo_propagates_the_exit_code():
    """`python -m finyahoo` runs the CLI and returns its exit code; a missing subcommand
    is argparse's exit 2. End-to-end (subprocess), so the __main__ alias is exercised."""
    result = subprocess.run([sys.executable, "-m", "finyahoo"], capture_output=True)
    assert result.returncode == 2


def test_version_flag_prints_the_version(capsys):
    # `finyahoo --version` is a standard CLI expectation: argparse prints to stdout and
    # exits 0. It is wired at the top level, before the required subcommand.
    import finyahoo

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert finyahoo.__version__ in capsys.readouterr().out
