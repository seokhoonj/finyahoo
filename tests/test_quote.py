"""Yahoo quote-parsing tests that need no network.

The fixtures cover what the record shape decides: bare numbers (not ``{raw}``
boxes), the name fallback chain, a missing field reading as None, and the error
envelope.
"""

from datetime import UTC, datetime

import pytest

from finyahoo import Quote, YahooParseError, YahooRequestError
from finyahoo.quote import parse_quotes

_TWO = """
{"quoteResponse": {"error": null, "result": [
  {"symbol": "AAPL", "longName": "Apple Inc.", "quoteType": "EQUITY", "currency": "USD",
   "fullExchangeName": "NasdaqGS", "marketState": "REGULAR",
   "regularMarketPrice": 339.25, "regularMarketPreviousClose": 335.0,
   "regularMarketChange": 4.25, "regularMarketChangePercent": 1.27,
   "regularMarketVolume": 41234567, "marketCap": 4900000000000,
   "trailingPE": 34.2, "regularMarketTime": 1785441600,
   "preMarketPrice": 340.5, "preMarketChange": 1.25,
   "preMarketChangePercent": 0.3684, "preMarketTime": 1785470400,
   "postMarketPrice": 338.75, "postMarketChange": -0.5,
   "postMarketChangePercent": -0.1474, "postMarketTime": 1785502800},
  {"symbol": "005930.KS", "shortName": "Samsung Elec", "currency": "KRW",
   "regularMarketPrice": 71000}
]}}
"""

_ERROR = '{"quoteResponse": {"result": null, "error": {"code": "Bad Request", "description": "nope"}}}'


def test_parses_each_symbol_in_order():
    quotes = parse_quotes(_TWO)
    assert isinstance(quotes[0], Quote)
    assert [q.symbol for q in quotes] == ["AAPL", "005930.KS"]


def test_bare_numbers_are_read_directly_not_unwrapped():
    apple = parse_quotes(_TWO)[0]
    assert apple.price == pytest.approx(339.25)
    assert apple.change_percent == pytest.approx(1.27)
    assert apple.market_cap == 4900000000000


def test_name_falls_back_from_long_to_short():
    quotes = parse_quotes(_TWO)
    assert quotes[0].name == "Apple Inc."          # longName
    assert quotes[1].name == "Samsung Elec"        # shortName, no longName


def test_a_missing_field_is_none_not_zero():
    samsung = parse_quotes(_TWO)[1]
    assert samsung.trailing_pe is None
    assert samsung.volume is None
    assert samsung.market_cap is None
    for field in (
        "pre_market_price",
        "pre_market_change",
        "pre_market_change_percent",
        "pre_market_time",
        "post_market_price",
        "post_market_change",
        "post_market_change_percent",
        "post_market_time",
    ):
        assert getattr(samsung, field) is None


def test_epoch_market_time_becomes_a_datetime():
    apple = parse_quotes(_TWO)[0]
    assert isinstance(apple.market_time, datetime)


def test_extended_hours_bare_numbers_and_times_are_parsed():
    apple = parse_quotes(_TWO)[0]
    assert apple.pre_market_price == pytest.approx(340.5, rel=1e-9)
    assert apple.pre_market_change == pytest.approx(1.25, rel=1e-9)
    assert apple.pre_market_change_percent == pytest.approx(0.3684, rel=1e-9)
    assert apple.pre_market_time == datetime(2026, 7, 31, 4, 0, tzinfo=UTC)
    assert apple.post_market_price == pytest.approx(338.75, rel=1e-9)
    assert apple.post_market_change == pytest.approx(-0.5, rel=1e-9)
    assert apple.post_market_change_percent == pytest.approx(-0.1474, rel=1e-9)
    assert apple.post_market_time == datetime(2026, 7, 31, 13, 0, tzinfo=UTC)


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_quotes(_ERROR)


def test_non_quote_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_quotes('{"unexpected": "shape"}')


def test_a_json_bool_does_not_read_as_a_price():
    """bool is an int subclass, so an unguarded field would take `true` as 1.0; the
    bare-number guard must keep it out of a float field."""
    payload = '{"quoteResponse": {"error": null, "result": [{"symbol": "X", "regularMarketPrice": true}]}}'
    assert parse_quotes(payload)[0].price is None


def test_a_null_record_is_shape_drift_not_a_silent_skip():
    """A valid envelope carrying a null quote record is drift; it must raise, not
    escape as an AttributeError from a later .get()."""
    payload = '{"quoteResponse": {"error": null, "result": [null]}}'
    with pytest.raises(YahooParseError):
        parse_quotes(payload)


def test_an_empty_result_is_no_matches_not_an_error():
    """A request that matched only unknown symbols returns an empty result with a
    null error -- a legitimate 'no matches', so an empty tuple, not a parse error."""
    payload = '{"quoteResponse": {"error": null, "result": []}}'
    assert parse_quotes(payload) == ()


def test_a_non_list_result_is_shape_drift():
    """result drifting to a non-list must raise through the public parser, not only
    when the helper is called directly."""
    payload = '{"quoteResponse": {"error": null, "result": {"symbol": "AAPL"}}}'
    with pytest.raises(YahooParseError):
        parse_quotes(payload)
