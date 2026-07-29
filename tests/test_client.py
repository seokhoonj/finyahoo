"""YahooClient network-shell tests with a fake session -- no real network.

The pure parsers are tested elsewhere; this covers the shell's own logic, which is
where a broken client would otherwise ship green: URL and parameter routing, the
crumb mint-and-retry, the 429 block that must not be retried, transient retries,
and the session close. The HTTP session -- the one external boundary -- is faked
and the sleep is captured so nothing waits.
"""

from datetime import date
from typing import Any

import pytest
from curl_cffi import requests as cffi_requests

from finyahoo import YahooBlockedError, YahooClient, YahooRequestError

# A minimal but valid quoteSummary payload the profile parser accepts.
_PROFILE_JSON = """
{"quoteSummary": {"error": null, "result": [{
  "quoteType": {"longName": "Samsung Electronics Co., Ltd."},
  "summaryDetail": {"currency": "KRW"}
}]}}
"""

# Minimal but valid payloads for the endpoints these tests drive.
_CHART_EMPTY = '{"chart": {"error": null, "result": [{"meta": {"gmtoffset": 0, "symbol": "MU"}}]}}'
_QUOTE_JSON = '{"quoteResponse": {"error": null, "result": [{"symbol": "AAPL", "regularMarketPrice": 1.0}]}}'
_OPTIONS_JSON = '{"optionChain": {"error": null, "result": [{"underlyingSymbol": "AAPL", "options": []}]}}'
_TIMESERIES_JSON = """
{"timeseries": {"error": null, "result": [{
  "meta": {"symbol": ["AAPL"], "type": ["annualTotalRevenue"]},
  "timestamp": [1664496000],
  "annualTotalRevenue": [{"asOfDate": "2022-09-30", "reportedValue": {"raw": 1.0}}]
}]}}
"""

# Minimal but valid payloads for the remaining endpoints, so each fetch route's URL
# and parameter wiring is covered, not only its parser.
_SEARCH_JSON = '{"quotes": [{"symbol": "AAPL"}], "news": []}'
_SPARK_JSON = '{"AAPL": {"timestamp": [1700000000], "close": [1.0], "chartPreviousClose": 0.9}}'
_RECOMMEND_JSON = ('{"finance": {"error": null, "result": [{"symbol": "AAPL", '
                   '"recommendedSymbols": [{"symbol": "MSFT", "score": 0.3}]}]}}')
_INSIGHTS_JSON = '{"finance": {"error": null, "result": {"symbol": "AAPL", "instrumentInfo": {}}}}'
_SCREENER_JSON = ('{"finance": {"error": null, "result": [{"canonicalName": "MOST_ACTIVES", '
                  '"total": 10, "quotes": [{"symbol": "AAPL"}]}]}}')


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text


class _FakeSession:
    """Serves canned responses in order and records each call's params.

    A queued item that is an ``Exception`` is raised instead of returned, so a
    transport error (a timeout) can be scripted alongside status responses.
    """

    def __init__(self, *responses: _FakeResponse | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Capture backoff sleeps so a retry never actually waits."""
    slept: list[float] = []
    monkeypatch.setattr("finyahoo.client.time.sleep", slept.append)
    return slept


def _client(session: _FakeSession) -> YahooClient:
    client = YahooClient(delay_seconds=0)
    client._session = session  # type: ignore[assignment]  # a fake stands in for the HTTP session
    return client


def test_fetch_profile_mints_a_crumb_then_re_mints_once_when_it_is_stale(_no_sleep):
    """cookie(404) -> crumb "old" -> summary 401 -> cookie(404) -> crumb "new" ->
    summary 200: the first crumb is used, the 401 forces a re-mint, the second
    crumb carries the retry."""
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "old"),
        _FakeResponse(401, ""),
        _FakeResponse(404, ""), _FakeResponse(200, "new"),
        _FakeResponse(200, _PROFILE_JSON),
    )
    profile = _client(session).fetch_profile("005930.KS")
    assert profile.name == "Samsung Electronics Co., Ltd."
    crumbs = [call["params"]["crumb"] for call in session.calls if call["params"]]
    assert crumbs == ["old", "new"]
    assert _no_sleep == []


def test_a_second_stale_crumb_is_not_retried_again_but_raises():
    """The retry does not tolerate a 401; a crumb that is stale twice is a real
    failure, not an infinite re-mint loop."""
    from finyahoo import YahooRequestError
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "old"),
        _FakeResponse(401, ""),
        _FakeResponse(404, ""), _FakeResponse(200, "new"),
        _FakeResponse(401, ""),
    )
    with pytest.raises(YahooRequestError):
        _client(session).fetch_profile("005930.KS")


def test_a_429_is_a_block_and_is_not_retried():
    session = _FakeSession(_FakeResponse(429, "blocked"))
    with pytest.raises(YahooBlockedError):
        _client(session).fetch_history("MU")
    assert len(session.calls) == 1          # not retried


def test_a_chart_401_is_a_request_error_not_swallowed():
    """The chart endpoint carries no crumb, so a 401 there is a real failure and
    must not be handed to the parser as a normal response."""
    from finyahoo import YahooRequestError
    session = _FakeSession(_FakeResponse(401, "{}"))
    with pytest.raises(YahooRequestError):
        _client(session).fetch_history("MU")


def test_close_closes_the_underlying_session():
    session = _FakeSession()
    client = _client(session)
    client.close()
    assert session.closed


def test_context_manager_closes_on_exit():
    session = _FakeSession()
    with _client(session):
        pass
    assert session.closed


def test_history_with_start_after_end_is_a_value_error():
    """An inverted window is a caller bug, caught before any request."""
    with pytest.raises(ValueError):
        _client(_FakeSession()).fetch_history("MU", start=date(2020, 1, 2), end=date(2020, 1, 1))


def test_history_end_is_inclusive_via_the_next_days_start():
    """Yahoo filters timestamp < period2 and a bar's timestamp is its session open,
    so an inclusive end date must be sent as the start of the next day. The expected
    value is the independently-known epoch of 2020-01-16 00:00 UTC, so a regression
    in _to_epoch or _ONE_DAY_SECONDS cannot move both sides together."""
    session = _FakeSession(_FakeResponse(200, _CHART_EMPTY))
    _client(session).fetch_history("MU", end=date(2020, 1, 15))
    assert session.calls[-1]["params"]["period2"] == 1_579_132_800


def test_fetch_timeseries_end_none_sends_now_not_the_open_end_sentinel(monkeypatch):
    """Regression: timeseries rejects the 9999999999 open-end sentinel (returns zero
    points), so an open-ended request must send the current time instead."""
    monkeypatch.setattr("finyahoo.client.time.time", lambda: 1_800_000_000)
    session = _FakeSession(_FakeResponse(200, _TIMESERIES_JSON))
    _client(session).fetch_timeseries("AAPL", ["annualTotalRevenue"])
    period2 = session.calls[-1]["params"]["period2"]
    assert period2 == 1_800_000_000
    assert period2 != 9999999999


def test_a_5xx_is_retried_then_succeeds(_no_sleep):
    """A 500 is a transient glitch: retry with backoff and use the first good body.
    The captured waits pin the backoff schedule, not just the count."""
    session = _FakeSession(
        _FakeResponse(500, ""), _FakeResponse(500, ""), _FakeResponse(200, _CHART_EMPTY))
    history = _client(session).fetch_history("MU")
    assert history.bars == ()
    assert _no_sleep == pytest.approx([2.0, 4.0])   # geometric backoff between three attempts


def test_a_transport_error_is_retried_then_succeeds(_no_sleep):
    """A timeout (RequestsError) is transient like a 5xx: retried with backoff, then
    the first good body is used."""
    session = _FakeSession(
        cffi_requests.RequestsError("timeout"), _FakeResponse(200, _CHART_EMPTY))
    history = _client(session).fetch_history("MU")
    assert history.bars == ()
    assert len(session.calls) == 2
    assert _no_sleep == pytest.approx([2.0])


def test_exhausted_transport_errors_raise_request_error():
    session = _FakeSession(
        cffi_requests.RequestsError("t"), cffi_requests.RequestsError("t"),
        cffi_requests.RequestsError("t"))
    with pytest.raises(YahooRequestError):
        _client(session).fetch_history("MU")


def test_exhausted_5xx_retries_raise_request_error():
    session = _FakeSession(
        _FakeResponse(500, ""), _FakeResponse(500, ""), _FakeResponse(500, ""))
    with pytest.raises(YahooRequestError):
        _client(session).fetch_history("MU")


def test_a_non_crumb_html_body_raises_rather_than_being_used():
    """When Yahoo serves an HTML error page in place of a crumb, that must raise, not
    flow downstream as if it were a crumb token."""
    session = _FakeSession(_FakeResponse(404, ""), _FakeResponse(200, "<html>error</html>"))
    with pytest.raises(YahooRequestError):
        _client(session).fetch_profile("MU")


def test_a_crumbed_endpoint_sends_the_crumb():
    """The new crumb-gated fetchers route through the same mint path as fetch_profile."""
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"),
        _FakeResponse(200, _QUOTE_JSON))
    _client(session).fetch_quotes(["AAPL"])
    assert session.calls[-1]["url"].endswith("/v7/finance/quote")
    assert session.calls[-1]["params"]["crumb"] == "c"


def test_a_second_crumbed_fetch_reuses_the_cached_crumb():
    """The crumb is minted once and reused; a second crumbed fetch does not re-mint."""
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"),   # one mint
        _FakeResponse(200, _QUOTE_JSON),                    # first fetch
        _FakeResponse(200, _QUOTE_JSON))                    # second fetch, crumb reused
    client = _client(session)
    client.fetch_quotes(["AAPL"])
    client.fetch_quotes(["MSFT"])
    mints = sum(1 for call in session.calls if call["url"].endswith("/v1/test/getcrumb"))
    assert mints == 1


def test_the_second_request_waits_for_the_pacing_delay(_no_sleep, monkeypatch):
    """With a positive delay, the client sleeps to space consecutive requests; the
    first request does not wait, the second waits the delay."""
    monkeypatch.setattr("finyahoo.client.time.monotonic", lambda: 100.0)
    session = _FakeSession(_FakeResponse(200, _CHART_EMPTY), _FakeResponse(200, _CHART_EMPTY))
    client = YahooClient(delay_seconds=0.5)
    client._session = session  # type: ignore[assignment]
    client.fetch_history("MU")
    client.fetch_history("MU")
    assert _no_sleep == pytest.approx([0.5])


def test_fetch_quotes_with_one_symbol_string_is_not_split_into_letters():
    """str satisfies Sequence[str], so an unguarded join would turn "AAPL" into
    "A,A,P,L" and query the wrong symbols; one ticker must reach Yahoo intact."""
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _QUOTE_JSON))
    _client(session).fetch_quotes("AAPL")
    assert session.calls[-1]["params"]["symbols"] == "AAPL"


def test_fetch_quotes_rejects_an_empty_symbol_sequence_before_any_request():
    """An empty sequence is a caller bug caught at the boundary as ValueError, not a
    blank query sent to Yahoo."""
    session = _FakeSession()
    with pytest.raises(ValueError):
        _client(session).fetch_quotes([])
    assert session.calls == []


def test_fetch_spark_routes_to_the_spark_url_with_range_and_interval():
    session = _FakeSession(_FakeResponse(200, _SPARK_JSON))
    sparks = _client(session).fetch_spark("AAPL", period="1y", interval="1wk")
    call = session.calls[-1]
    assert call["url"].endswith("/v8/finance/spark")
    assert call["params"] == {"symbols": "AAPL", "range": "1y", "interval": "1wk"}
    assert sparks[0].symbol == "AAPL"


def test_fetch_search_routes_to_the_search_url_without_a_crumb():
    session = _FakeSession(_FakeResponse(200, _SEARCH_JSON))
    result = _client(session).fetch_search("apple")
    call = session.calls[-1]
    assert call["url"].endswith("/v1/finance/search")
    assert call["params"] == {"q": "apple", "quotesCount": 6, "newsCount": 4}
    assert "crumb" not in call["params"]
    assert result.matches[0].symbol == "AAPL"


def test_fetch_recommendations_routes_to_the_recommend_url_without_a_crumb():
    session = _FakeSession(_FakeResponse(200, _RECOMMEND_JSON))
    recs = _client(session).fetch_recommendations("AAPL")
    call = session.calls[-1]
    assert "/v6/finance/recommendationsbysymbol/AAPL" in call["url"]
    assert call["params"] is None                 # no query params, no crumb
    assert recs[0].symbol == "MSFT"


def test_fetch_insights_routes_through_the_crumb_path():
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _INSIGHTS_JSON))
    insights = _client(session).fetch_insights("AAPL")
    call = session.calls[-1]
    assert call["url"].endswith("/ws/insights/v1/finance/insights")
    assert call["params"]["symbol"] == "AAPL"
    assert call["params"]["crumb"] == "c"
    assert insights.symbol == "AAPL"


def test_fetch_screener_sends_the_page_size_as_count_and_a_crumb():
    session = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _SCREENER_JSON))
    screen = _client(session).fetch_screener("most_actives", page_size=10)
    call = session.calls[-1]
    assert call["url"].endswith("/v1/finance/screener/predefined/saved")
    assert call["params"]["scrIds"] == "most_actives"
    assert call["params"]["count"] == 10
    assert call["params"]["crumb"] == "c"
    assert screen.total == 10


def test_fetch_options_sends_a_date_only_when_an_expiration_is_given():
    without = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _OPTIONS_JSON))
    _client(without).fetch_options("AAPL")
    assert "date" not in without.calls[-1]["params"]

    with_exp = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _OPTIONS_JSON))
    _client(with_exp).fetch_options("AAPL", expiration=date(2025, 1, 17))
    assert with_exp.calls[-1]["url"].endswith("/v7/finance/options/AAPL")
    # The independently-known epoch of 2025-01-17 00:00 UTC, so a _to_epoch regression
    # cannot move both sides together.
    assert with_exp.calls[-1]["params"]["date"] == 1_737_072_000


def test_fetch_timeseries_with_start_after_end_is_a_value_error():
    """An inverted window is a caller bug, caught before any request (parity with
    fetch_history)."""
    with pytest.raises(ValueError):
        _client(_FakeSession()).fetch_timeseries(
            "AAPL", ["annualTotalRevenue"], start=date(2020, 1, 2), end=date(2020, 1, 1))
