"""YahooClient network-shell tests with a fake session -- no real network.

The pure parsers are tested elsewhere; this covers the shell's own logic, which is
where a broken client would otherwise ship green: the crumb mint-and-retry, the
429 block that must not be retried, and the session close. The session is faked
(the one true boundary, per Ch 10.6) and the sleep is captured so nothing waits.
"""

from datetime import date
from typing import Any

import pytest

from pyyahoo import YahooBlockedError, YahooClient, YahooRequestError
from pyyahoo.client import _ONE_DAY_SECONDS, _to_epoch

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


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text


class _FakeSession:
    """Serves canned responses in order and records each call's params."""

    def __init__(self, *responses: _FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Capture backoff sleeps so a retry never actually waits."""
    slept: list[float] = []
    monkeypatch.setattr("pyyahoo.client.time.sleep", slept.append)
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
    from pyyahoo import YahooRequestError
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
    from pyyahoo import YahooRequestError
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
    so an inclusive end date must be sent as the start of the next day."""
    session = _FakeSession(_FakeResponse(200, _CHART_EMPTY))
    _client(session).fetch_history("MU", end=date(2020, 1, 15))
    assert session.calls[-1]["params"]["period2"] == _to_epoch(date(2020, 1, 15)) + _ONE_DAY_SECONDS


def test_fetch_timeseries_end_none_sends_now_not_the_open_end_sentinel(monkeypatch):
    """Regression: timeseries rejects the 9999999999 open-end sentinel (returns zero
    points), so an open-ended request must send the current time instead."""
    monkeypatch.setattr("pyyahoo.client.time.time", lambda: 1_800_000_000)
    session = _FakeSession(_FakeResponse(200, _TIMESERIES_JSON))
    _client(session).fetch_timeseries("AAPL", ["annualTotalRevenue"])
    period2 = session.calls[-1]["params"]["period2"]
    assert period2 == 1_800_000_000
    assert period2 != 9999999999


def test_a_5xx_is_retried_then_succeeds(_no_sleep):
    """A 500 is a transient glitch: retry with backoff and use the first good body."""
    session = _FakeSession(
        _FakeResponse(500, ""), _FakeResponse(500, ""), _FakeResponse(200, _CHART_EMPTY))
    history = _client(session).fetch_history("MU")
    assert history.bars == ()
    assert len(_no_sleep) == 2                 # two backoff waits between three attempts


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
    assert session.calls[-1]["params"]["crumb"] == "c"


def test_fetch_options_sends_a_date_only_when_an_expiration_is_given():
    without = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _OPTIONS_JSON))
    _client(without).fetch_options("AAPL")
    assert "date" not in without.calls[-1]["params"]

    with_exp = _FakeSession(
        _FakeResponse(404, ""), _FakeResponse(200, "c"), _FakeResponse(200, _OPTIONS_JSON))
    _client(with_exp).fetch_options("AAPL", expiration=date(2025, 1, 17))
    assert with_exp.calls[-1]["params"]["date"] == _to_epoch(date(2025, 1, 17))
