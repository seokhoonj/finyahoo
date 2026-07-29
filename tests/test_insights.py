"""Yahoo insights-parsing tests that need no network.

Insights is deeply nested and provider-specific; the parser reads stable leaves
into one flat object. The fixtures cover those leaves being read, a whole branch
being absent (fields None, no AttributeError), and a horizon Yahoo nulls.
"""

import pytest

from finyahoo import InsightReport, Insights, YahooParseError, YahooRequestError
from finyahoo.insights import parse_insights

_FULL = """
{"finance": {"error": null, "result": {
  "symbol": "AAPL",
  "instrumentInfo": {
    "recommendation": {"targetPrice": 375.0, "provider": "Argus", "rating": "BUY"},
    "valuation": {"description": "Overvalued", "relativeValue": "Premium"},
    "keyTechnicals": {"support": 227.28, "stopLoss": 318.81},
    "technicalEvents": {"provider": "TC",
      "shortTerm": {"stateDescription": "Bullish", "direction": "up"},
      "midTerm": null,
      "longTerm": {"stateDescription": "Bearish"}}
  },
  "reports": [
    {"id": "r1", "title": "Apple upgrade", "provider": "Argus",
     "publishedOn": "2026-07-15", "summary": "raised target"}
  ],
  "companySnapshot": {"sectorInfo": "Technology"}
}}}
"""

_BARE = """
{"finance": {"error": null, "result": {"symbol": "XYZ", "reports": []}}}
"""

_ERROR = '{"finance": {"result": null, "error": {"code": "Not Found", "description": "no"}}}'


def test_reads_the_analyst_call_and_valuation():
    ins = parse_insights(_FULL, "AAPL")
    assert isinstance(ins, Insights)
    assert ins.target_price == pytest.approx(375.0)
    assert ins.rating == "BUY"
    assert ins.valuation == "Overvalued"


def test_reads_technical_levels_and_outlooks():
    ins = parse_insights(_FULL, "AAPL")
    assert ins.support == pytest.approx(227.28)
    assert ins.short_term_outlook == "Bullish"
    assert ins.long_term_outlook == "Bearish"


def test_a_nulled_horizon_is_none():
    assert parse_insights(_FULL, "AAPL").mid_term_outlook is None


def test_reports_are_parsed_with_dates():
    from datetime import date
    report = parse_insights(_FULL, "AAPL").reports[0]
    assert isinstance(report, InsightReport)
    assert report.published_on == date(2026, 7, 15)
    assert report.provider == "Argus"


def test_an_absent_branch_leaves_fields_none_not_an_error():
    ins = parse_insights(_BARE, "XYZ")
    assert ins.target_price is None
    assert ins.support is None
    assert ins.short_term_outlook is None
    assert ins.reports == ()


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_insights(_ERROR, "AAPL")


def test_non_insights_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_insights('{"unexpected": "shape"}', "AAPL")


def test_a_non_object_result_is_shape_drift():
    """The insights result is a bare object; a drift to a list must raise rather than
    fail later on result.get()."""
    with pytest.raises(YahooParseError):
        parse_insights('{"finance": {"error": null, "result": [1, 2, 3]}}', "AAPL")


def test_a_null_report_record_is_shape_drift():
    """A null entry in reports must raise, not leak an AttributeError from report.get()
    past the documented YahooParseError contract."""
    null_report = '{"finance": {"error": null, "result": {"symbol": "AAPL", "reports": [null]}}}'
    with pytest.raises(YahooParseError):
        parse_insights(null_report, "AAPL")


def test_a_non_numeric_target_price_becomes_none():
    """A bare numeric field guarded by as_number: a bool must read as None."""
    payload = ('{"finance": {"error": null, "result": {"symbol": "AAPL", '
               '"instrumentInfo": {"recommendation": {"targetPrice": true}}, "reports": []}}}')
    assert parse_insights(payload, "AAPL").target_price is None
