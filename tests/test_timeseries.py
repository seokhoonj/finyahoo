"""Yahoo timeseries-parsing tests that need no network.

The fixtures cover what makes a dated line item right: one series per requested
type, a value unboxed from ``reportedValue.raw`` and dated by ``asOfDate``, a
padded null period dropped, and a type the symbol has no data for (a series with a
``meta`` but no matching data key) retained as an empty series rather than dropped.
"""

from datetime import date

import pytest

from pyyahoo import FinancialSeries, YahooParseError, YahooRequestError, parse_timeseries

_TWO_TYPES = """
{"timeseries": {"error": null, "result": [
  {"meta": {"symbol": ["AAPL"], "type": ["annualTotalRevenue"]},
   "timestamp": [1664496000, 1696032000],
   "annualTotalRevenue": [
     {"asOfDate": "2022-09-30", "periodType": "12M", "currencyCode": "USD",
      "reportedValue": {"raw": 394328000000.0, "fmt": "394.33B"}},
     {"asOfDate": "2023-09-30", "periodType": "12M", "currencyCode": "USD",
      "reportedValue": {"raw": 383285000000.0, "fmt": "383.29B"}}
   ]},
  {"meta": {"symbol": ["AAPL"], "type": ["annualNetIncome"]},
   "timestamp": [1664496000, null],
   "annualNetIncome": [
     {"asOfDate": "2022-09-30", "periodType": "12M", "currencyCode": "USD",
      "reportedValue": {"raw": 99803000000.0}},
     null
   ]}
]}}
"""

# A padded-but-empty series: Yahoo returns a meta for a type the symbol has no data
# for, with no matching data key.
_EMPTY_TYPE = """
{"timeseries": {"error": null, "result": [
  {"meta": {"symbol": ["AAPL"], "type": ["annualEbitda"]}, "timestamp": []}
]}}
"""

# Shape drift: an entry whose meta carries no readable type at all.
_DRIFTED_META = """
{"timeseries": {"error": null, "result": [
  {"meta": {"symbol": ["AAPL"]}, "timestamp": [1664496000]}
]}}
"""

_ERROR = '{"timeseries": {"result": null, "error": {"code": "Bad Request", "description": "nope"}}}'


def test_parses_one_series_per_requested_type():
    series = parse_timeseries(_TWO_TYPES, "AAPL")
    assert isinstance(series[0], FinancialSeries)
    assert [s.metric for s in series] == ["annualTotalRevenue", "annualNetIncome"]


def test_value_is_unboxed_and_dated_by_as_of_date():
    revenue = parse_timeseries(_TWO_TYPES, "AAPL")[0]
    assert revenue.points[0].as_of_date == date(2022, 9, 30)
    assert revenue.points[0].reported_value == pytest.approx(394328000000.0)
    assert revenue.points[0].currency == "USD"


def test_a_padded_null_period_is_dropped():
    net_income = parse_timeseries(_TWO_TYPES, "AAPL")[1]
    assert len(net_income.points) == 1                        # the null second period is gone


def test_a_type_with_no_data_yields_an_empty_series_not_a_dropped_one():
    """A readable meta.type with no data key keeps its slot with empty points, so a
    caller zipping requested types positionally is not shifted."""
    series = parse_timeseries(_EMPTY_TYPE, "AAPL")
    assert len(series) == 1
    assert series[0].metric == "annualEbitda"
    assert series[0].points == ()


def test_an_entry_with_no_readable_meta_type_raises_rather_than_dropping_silently():
    """A renamed/absent meta.type is shape drift; dropping it silently would read as
    'this symbol has no financials'."""
    with pytest.raises(YahooParseError):
        parse_timeseries(_DRIFTED_META, "AAPL")


def test_a_non_null_non_object_row_is_shape_drift_not_padding():
    """A null row is Yahoo's padding for a missing period and is skipped; a non-null,
    non-object row is drift and must raise, not be discarded like padding."""
    drifted = """
    {"timeseries": {"error": null, "result": [
      {"meta": {"symbol": ["AAPL"], "type": ["annualTotalRevenue"]},
       "annualTotalRevenue": ["not-an-object"]}
    ]}}
    """
    with pytest.raises(YahooParseError):
        parse_timeseries(drifted, "AAPL")


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_timeseries(_ERROR, "AAPL")


def test_non_timeseries_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_timeseries('{"unexpected": "shape"}', "AAPL")
