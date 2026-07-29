"""Yahoo chart-parsing tests that need no network.

The fixtures reproduce the shapes that decide correctness: a null bar Yahoo has no
data for (dropped, not zeroed), a KST timestamp that must keep its own calendar
day, split/dividend events in the same payload, and the error object a delisted
ticker returns.
"""

import json
from datetime import date

import pytest

from pyyahoo import PriceHistory, YahooParseError, YahooRequestError, parse_history

# 005930.KS-shaped: gmtoffset 32400 (KST, UTC+9). The three timestamps are KST
# midnights, so the +9h shift lands each on its Korean date: 2018-04-27 (epoch
# 1524754800), -04-30 (1525014000, a null bar), -05-04 (1525359600), with a 50:1
# split on the last.
_KST = """
{"chart": {"error": null, "result": [{
  "meta": {"gmtoffset": 32400, "currency": "KRW", "symbol": "005930.KS"},
  "timestamp": [1524754800, 1525014000, 1525359600],
  "indicators": {
    "quote": [{
      "open":   [2669000, null, 53000],
      "high":   [2680000, null, 53900],
      "low":    [2622000, null, 51800],
      "close":  [2650000, null, 51900],
      "volume": [606216,  null, 39565391]
    }],
    "adjclose": [{"adjclose": [43118.6, null, 42223.7]}]
  },
  "events": {
    "splits": {"1525359600": {"date": 1525359600, "numerator": 50, "denominator": 1, "splitRatio": "50:1"}},
    "dividends": {"1524754800": {"date": 1524754800, "amount": 354.0}}
  }
}]}}
"""

_NOT_FOUND = """
{"chart": {"result": null, "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}}}
"""

# A valid empty window: the result exists but has no timestamp array.
_EMPTY_WINDOW = """
{"chart": {"error": null, "result": [{"meta": {"gmtoffset": 0, "symbol": "MU"}}]}}
"""


def test_parses_bars_with_split_adjusted_and_fully_adjusted_close():
    history = parse_history(_KST, "005930.KS")
    assert isinstance(history, PriceHistory)
    first = history.bars[0]
    assert first.close == pytest.approx(2650000)
    assert first.adj_close == pytest.approx(43118.6)
    assert first.volume == 606216


def test_a_null_bar_is_dropped_not_zeroed():
    """Yahoo nulls every column of a bar it has no data for; writing a 0 would read
    as a price and a zero low is every drawdown's worst input."""
    dates = [bar.trade_date for bar in parse_history(_KST, "005930.KS").bars]
    assert date(2018, 4, 30) not in dates
    assert dates == [date(2018, 4, 27), date(2018, 5, 4)]


def test_kst_timestamp_keeps_its_own_trading_date():
    """The +9h offset must be applied, or a KST bar reads a day earlier as UTC."""
    first = parse_history(_KST, "005930.KS").bars[0]
    assert first.trade_date == date(2018, 4, 27)


def test_split_is_carried_as_the_two_integers_yahoo_states():
    split = parse_history(_KST, "005930.KS").splits[0]
    assert split.ex_date == date(2018, 5, 4)
    assert (split.numerator, split.denominator) == (50, 1)


def test_dividend_is_carried_per_share():
    dividend = parse_history(_KST, "005930.KS").dividends[0]
    assert dividend.ex_date == date(2018, 4, 27)
    assert dividend.per_share == pytest.approx(354.0)


def test_split_numerator_and_denominator_are_integers_not_floats():
    """The whole point of keeping the pair is that 1/21 stays exact -- a float
    field would defeat it, so the type and the value are both int."""
    split = parse_history(_KST, "005930.KS").splits[0]
    assert isinstance(split.numerator, int) and isinstance(split.denominator, int)


def test_a_bar_with_a_null_non_close_price_is_dropped_not_stored_with_none():
    """The in-progress bar can carry a close with no adjusted close yet; a None
    must never reach a float field, so the incomplete bar is dropped."""
    import json
    payload = json.loads(_KST)
    payload["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"][2] = None
    history = parse_history(json.dumps(payload), "005930.KS")
    assert [bar.trade_date for bar in history.bars] == [date(2018, 4, 27)]


def test_a_priced_bar_with_null_volume_keeps_the_bar_with_volume_none():
    """A settled bar whose volume Yahoo omitted (a halted session, some index feeds)
    is kept -- volume is None, never 0, which is a real no-trade reading."""
    payload = json.loads(_KST)
    payload["chart"]["result"][0]["indicators"]["quote"][0]["volume"][2] = None
    last = parse_history(json.dumps(payload), "005930.KS").bars[-1]
    assert last.trade_date == date(2018, 5, 4)
    assert last.volume is None


def test_a_ragged_column_shorter_than_timestamps_raises_parse_error():
    """A quote column shorter than timestamp is a malformed payload, surfaced as a
    parse error rather than escaping as a bare IndexError past the contract."""
    import json
    payload = json.loads(_KST)
    payload["chart"]["result"][0]["indicators"]["quote"][0]["open"].pop()
    with pytest.raises(YahooParseError):
        parse_history(json.dumps(payload), "005930.KS")


def test_events_are_absent_not_an_error_when_none_occurred():
    payload = json.loads(_KST)
    del payload["chart"]["result"][0]["events"]
    history = parse_history(json.dumps(payload), "005930.KS")
    assert history.splits == () and history.dividends == ()


def test_a_delisted_ticker_is_a_request_error_carrying_yahoos_words():
    with pytest.raises(YahooRequestError) as excinfo:
        parse_history(_NOT_FOUND, "042670.KS")
    assert "Not Found" in str(excinfo.value)


def test_an_empty_window_is_no_bars_not_an_error():
    history = parse_history(_EMPTY_WINDOW, "MU")
    assert history.bars == ()


def test_non_json_payload_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_history("<html>error</html>", "MU")


def test_payload_without_the_chart_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_history('{"unexpected": "shape"}', "MU")


def test_result_present_but_missing_the_quote_block_raises_parse_error():
    broken = '{"chart": {"error": null, "result": [{"meta": {"gmtoffset": 0}, "timestamp": [1]}]}}'
    with pytest.raises(YahooParseError):
        parse_history(broken, "MU")
