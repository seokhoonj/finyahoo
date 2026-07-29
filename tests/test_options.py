"""Yahoo options-parsing tests that need no network.

The fixtures cover the two-level shape: the underlying's full expiration/strike
lists, and the one expiration's calls and puts, with epoch fields becoming dates
and a missing field reading as None.
"""

from datetime import date

import pytest

from finyahoo import OptionChain, YahooParseError, YahooRequestError
from finyahoo.options import parse_options

_CHAIN = """
{"optionChain": {"error": null, "result": [{
  "underlyingSymbol": "AAPL",
  "expirationDates": [1735084800, 1735689600],
  "strikes": [210.0, 220.0, 230.0],
  "options": [{
    "expirationDate": 1735084800,
    "calls": [
      {"contractSymbol": "AAPL241225C00210000", "strike": 210.0, "currency": "USD",
       "lastPrice": 15.2, "bid": 15.0, "ask": 15.5, "volume": 120, "openInterest": 3400,
       "impliedVolatility": 0.294, "inTheMoney": true, "contractSize": "REGULAR",
       "expiration": 1735084800, "lastTradeDate": 1734900000},
      {"contractSymbol": "AAPL241225C00220000", "strike": 220.0, "inTheMoney": false}
    ],
    "puts": [
      {"contractSymbol": "AAPL241225P00210000", "strike": 210.0, "bid": 2.1, "ask": 2.3}
    ]
  }]
}]}}
"""

_ERROR = '{"optionChain": {"result": null, "error": {"code": "Not Found", "description": "no"}}}'


def test_parses_the_underlying_and_its_expiration_and_strike_lists():
    chain = parse_options(_CHAIN)
    assert isinstance(chain, OptionChain)
    assert chain.underlying == "AAPL"
    assert chain.expiration_dates == (date(2024, 12, 25), date(2025, 1, 1))
    assert chain.strikes == pytest.approx((210.0, 220.0, 230.0))


def test_calls_and_puts_are_parsed_for_the_expiration():
    chain = parse_options(_CHAIN)
    assert len(chain.calls) == 2
    assert len(chain.puts) == 1
    assert chain.expiration == date(2024, 12, 25)


def test_a_contracts_epoch_fields_become_dates():
    call = parse_options(_CHAIN).calls[0]
    assert call.expiration == date(2024, 12, 25)
    assert call.last_trade is not None
    assert call.strike == pytest.approx(210.0)
    assert call.implied_volatility == pytest.approx(0.294)


def test_a_missing_contract_field_is_none():
    sparse_call = parse_options(_CHAIN).calls[1]
    assert sparse_call.bid is None
    assert sparse_call.volume is None
    assert sparse_call.is_in_the_money is False     # present and false, not None


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_options(_ERROR)


def test_non_option_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_options('{"unexpected": "shape"}')


def test_a_result_without_an_options_block_is_shape_drift():
    """A valid optionChain envelope whose result lacks the options key is drift; an
    empty options list is a real underlying with no chain, but a missing key must
    raise rather than silently yield an empty chain."""
    no_block = '{"optionChain": {"error": null, "result": [{"underlyingSymbol": "AAPL"}]}}'
    with pytest.raises(YahooParseError):
        parse_options(no_block)


def test_a_non_list_options_block_is_shape_drift():
    """options drifting to a non-list must raise, not leak a KeyError/TypeError from
    chains[0] past the documented YahooParseError contract."""
    drifted = '{"optionChain": {"error": null, "result": [{"underlyingSymbol": "AAPL", "options": {}}]}}'
    with pytest.raises(YahooParseError):
        parse_options(drifted)


def test_a_null_contract_row_is_shape_drift():
    """A null entry in calls/puts must raise, not leak an AttributeError from a later
    row.get() past the contract."""
    null_call = """
    {"optionChain": {"error": null, "result": [{"underlyingSymbol": "AAPL",
      "options": [{"expirationDate": 1735084800, "calls": [null], "puts": []}]}]}}
    """
    with pytest.raises(YahooParseError):
        parse_options(null_call)


def test_change_percent_maps_from_yahoos_percent_change_field():
    """The change_percent field carries Yahoo's percentChange (named to parallel
    Quote.change_percent)."""
    payload = ('{"optionChain": {"error": null, "result": [{"underlyingSymbol": "AAPL", '
               '"options": [{"expirationDate": 1735084800, '
               '"calls": [{"contractSymbol": "X", "percentChange": 2.5}], "puts": []}]}]}}')
    assert parse_options(payload).calls[0].change_percent == pytest.approx(2.5)
