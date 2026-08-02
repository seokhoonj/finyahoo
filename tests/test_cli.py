"""CLI tests -- no real network.

The CLI is a thin shell over YahooClient, so the client is faked and its canned
result is rendered; the tests pin the text/JSON output, the error contract (a domain
failure becomes `finyahoo: ...` on stderr and exit 1), and argparse's own guards.
"""

import dataclasses
import json
import subprocess
import sys
from datetime import UTC, date, datetime

import pytest

from finyahoo import (
    Consensus,
    Quote,
    RatingTrend,
    Search,
    SearchMatch,
    SearchNews,
    Timeframe,
    YahooRequestError,
)
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

_CONSENSUS = Consensus(
    symbol="AAPL", target_high_price=400.0, target_low_price=215.0,
    target_mean_price=323.28, target_median_price=330.0, recommendation_mean=2.04,
    recommendation="buy", analyst_count=41,
    trend=(
        RatingTrend("0m", strong_buy=6, buy=22, hold=14, sell=2, strong_sell=2),
        RatingTrend("-1m", strong_buy=6, buy=22, hold=16, sell=1, strong_sell=2),
    ),
)


def _quote(symbol, price, change_percent, *, name=None, currency="USD",
           market_state="REGULAR"):
    """A Quote with the display fields set and the rest None -- enough to pin the
    renderers without hand-writing all 27 fields per case."""
    return Quote(
        symbol=symbol, name=name, quote_type="EQUITY", currency=currency,
        exchange="NasdaqGS", market_state=market_state, price=price,
        previous_close=None, change=None, change_percent=change_percent,
        day_open=None, day_high=None, day_low=None, volume=None, market_cap=None,
        shares_outstanding=None, fifty_two_week_high=None, fifty_two_week_low=None,
        fifty_day_average=None, two_hundred_day_average=None, trailing_pe=None,
        forward_pe=None, price_to_book=None, trailing_eps=None, forward_eps=None,
        dividend_yield=None,
        market_time=datetime(2026, 7, 29, 17, 13, 27, tzinfo=UTC),
    )


_QUOTES = (
    _quote("MU", 783.0, -4.57, name="Micron Technology, Inc."),
    _quote("005930.KS", 208_500.0, -5.23, name="Samsung Electronics Co., Ltd.",
           currency="KRW", market_state="PREPRE"),
)

_SEARCH = Search(
    query="MU",
    matches=(
        SearchMatch("MU", "Micron Technology, Inc.", "NasdaqGS", "EQUITY",
                    "Equity", "Technology", "Semiconductors", 25_000.0),
        SearchMatch("MUSA", "Murphy USA Inc.", "NYSE", "EQUITY",
                    "Equity", "Consumer Cyclical", "Specialty Retail", 12_000.0),
    ),
    news=(
        SearchNews("news-1", "Micron announces results", "Reuters",
                   "https://example.com/news-1",
                   datetime(2026, 7, 30, 12, 30, tzinfo=UTC), ("MU",)),
        SearchNews("news-2", "Memory market update", "Bloomberg",
                   "https://example.com/news-2", None, ("MU", "005930.KS")),
    ),
)

_EMPTY_SEARCH = Search(query="missing", matches=(), news=())


class _FakeYahoo:
    """Stands in for YahooClient: a context manager returning canned results, or
    raising a scripted error from the fetch methods."""

    def __init__(self, *, history=None, profile=None, consensus=None, quotes=None,
                 search=None, error=None):
        self._history = history
        self._profile = profile
        self._consensus = consensus
        self._quotes = quotes
        self._search = search
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

    def fetch_consensus(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._consensus

    def fetch_quotes(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._quotes

    def fetch_search(self, *args, **kwargs):
        if self._error is not None:
            raise self._error
        return self._search


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


def test_consensus_text_renders_the_scalars_and_the_rating_trend(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, consensus=_CONSENSUS)
    assert main(["consensus", "AAPL"]) == 0
    out = capsys.readouterr().out
    assert "target_mean_price" in out and "323.28" in out
    assert "analyst_count" in out and "41" in out
    assert "0m" in out and "strong_buy 6" in out       # a rating-trend bucket line


def test_consensus_json_carries_the_full_record_including_the_trend(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, consensus=_CONSENSUS)
    assert main(["consensus", "AAPL", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "AAPL"
    assert payload["target_high_price"] == 400.0
    assert len(payload["trend"]) == 2                  # nested RatingTrend list kept
    assert payload["trend"][0]["period"] == "0m"


def test_quote_single_symbol_shows_the_live_snapshot_and_omits_valuation(monkeypatch, capsys):
    quote = dataclasses.replace(_QUOTES[0], trailing_pe=18.55, market_cap=834_000_000)
    _install_fake_yahoo_client(monkeypatch, quotes=(quote,))
    assert main(["quote", "MU"]) == 0
    out = capsys.readouterr().out
    assert "symbol" in out and "MU" in out
    assert "price" in out and "783" in out
    assert "market_state" in out and "REGULAR" in out
    assert "previous_close" not in out           # a None live field is skipped
    assert "trailing_pe" not in out              # valuation is the profile's view, not the quote's
    assert "market_cap" not in out


def test_quote_json_is_the_full_record(monkeypatch, capsys):
    quote = dataclasses.replace(_QUOTES[0], trailing_pe=18.55)
    _install_fake_yahoo_client(monkeypatch, quotes=(quote,))
    assert main(["quote", "MU", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, dict)                             # one object, not a list
    assert payload["symbol"] == "MU"
    assert payload["trailing_pe"] == 18.55                       # --json keeps what the text view omits
    assert payload["previous_close"] is None                     # Nones kept in JSON
    assert payload["market_time"] == "2026-07-29T17:13:27+00:00"  # datetime as ISO


def test_quote_forwards_the_symbol_as_a_one_element_list(monkeypatch):
    """The symbol reaches fetch_quotes -- a lost ticker would ship green."""
    calls = []

    class _Recorder(_FakeYahoo):
        def fetch_quotes(self, symbols):
            calls.append(symbols)
            return (_QUOTES[0],)

    monkeypatch.setattr("finyahoo.cli.YahooClient",
                        lambda *a, **k: _Recorder(quotes=(_QUOTES[0],)))
    assert main(["quote", "MU"]) == 0
    assert calls == [["MU"]]


def test_quote_unknown_symbol_is_a_one_line_error(monkeypatch, capsys):
    """/v7 answers an unknown symbol with an empty list, not an error; the CLI reports
    it on stderr and exits 1 rather than crashing on the empty result."""
    _install_fake_yahoo_client(monkeypatch, quotes=())
    assert main(["quote", "NOSUCH"]) == 1
    assert "no quote for NOSUCH" in capsys.readouterr().err


def test_news_text_shows_headlines_publishers_and_missing_timestamp(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, search=_SEARCH)
    assert main(["news", "MU"]) == 0
    out = capsys.readouterr().out
    assert "Micron announces results" in out and "(Reuters)" in out
    assert "?  (Bloomberg) Memory market update" in out    # a None timestamp renders as ?


def test_news_json_is_a_list_with_iso_timestamp(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, search=_SEARCH)
    assert main(["news", "MU", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)                        # the news items, not one object
    assert payload[0]["published_at"] == "2026-07-30T12:30:00+00:00"   # datetime as ISO


def test_match_text_shows_symbol_and_sector(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, search=_SEARCH)
    assert main(["match", "MU"]) == 0
    out = capsys.readouterr().out
    assert "MU" in out and "Technology" in out


def test_match_json_is_a_list_of_the_matches(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, search=_SEARCH)
    assert main(["match", "MU", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 2      # the matches, not one object
    assert payload[0]["symbol"] == "MU" and payload[0]["sector"] == "Technology"


def test_empty_search_has_clear_text_messages(monkeypatch, capsys):
    _install_fake_yahoo_client(monkeypatch, search=_EMPTY_SEARCH)
    assert main(["news", "missing"]) == 0
    assert capsys.readouterr().out.strip() == "(no news)"
    assert main(["match", "missing"]) == 0
    assert capsys.readouterr().out.strip() == "(no matches)"


def test_match_text_tolerates_missing_optional_fields(monkeypatch, capsys):
    """A match can carry None for exchange/sector/name (an ETF or a thin listing); the
    render must not crash on the None and still shows the symbol."""
    sparse = Search(query="X", news=(), matches=(
        SearchMatch("XYZ", None, None, "ETF", None, None, None, None),))
    _install_fake_yahoo_client(monkeypatch, search=sparse)
    assert main(["match", "X"]) == 0
    out = capsys.readouterr().out
    assert "XYZ" in out and "ETF" in out


@pytest.mark.parametrize("command", ["news", "match"])
def test_a_search_command_reports_a_yahoo_error(monkeypatch, capsys, command):
    """A fetch_search failure travels the same one-line-stderr / exit-1 contract as the
    other commands -- the new commands must not leak a traceback."""
    _install_fake_yahoo_client(monkeypatch, error=YahooRequestError("Not Found"))
    assert main([command, "MU"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "finyahoo: Not Found"


@pytest.mark.parametrize("command", ["news", "match"])
def test_a_count_below_one_is_rejected_by_argparse(command):
    """--count is a boundary: 0 or a negative is rejected before any network call."""
    with pytest.raises(SystemExit):
        main([command, "MU", "-n", "0"])


def test_search_commands_forward_symbol_and_counts(monkeypatch):
    """The symbol and the count reach fetch_search -- news drives news_count, match
    drives quotes_count -- a dropped or swapped argument would otherwise ship green."""
    calls = []

    class _Recorder(_FakeYahoo):
        def fetch_search(self, query, **kwargs):
            calls.append((query, kwargs))
            return _SEARCH

    monkeypatch.setattr("finyahoo.cli.YahooClient",
                        lambda *a, **k: _Recorder(search=_SEARCH))
    assert main(["news", "MU", "--count", "9"]) == 0
    assert main(["match", "SK hynix", "-n", "11"]) == 0
    assert calls == [
        ("MU", {"quotes_count": 1, "news_count": 9}),
        ("SK hynix", {"quotes_count": 11, "news_count": 0}),
    ]


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
