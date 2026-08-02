"""Consensus-parsing tests that need no network. The fixtures reproduce what makes
the sell-side aggregate quietly wrong: a boxed number vs a bare-string rating key,
a field Yahoo omits (None, never 0 -- 0 analysts, or 0 sells, is a real reading), a
module absent (an index carries neither financialData nor recommendationTrend), the
two modules going absent independently, a malformed trend row, and the rating-trend
buckets that are the one dated part.
"""

import json

import pytest

from finyahoo import Consensus, RatingTrend
from finyahoo.consensus import parse_consensus

_FULL = """
{"quoteSummary": {"error": null, "result": [{
  "financialData": {
    "targetHighPrice": {"raw": 725000.0},
    "targetLowPrice": {"raw": 210000.0},
    "targetMeanPrice": {"raw": 470630.3},
    "targetMedianPrice": {"raw": 450000.0},
    "recommendationMean": {"raw": 1.4},
    "recommendationKey": "strong_buy",
    "numberOfAnalystOpinions": {"raw": 37}
  },
  "recommendationTrend": {"trend": [
    {"period": "0m", "strongBuy": 11, "buy": 25, "hold": 1, "sell": 0, "strongSell": 0},
    {"period": "-1m", "strongBuy": 11, "buy": 25, "hold": 0, "sell": 0, "strongSell": 1}
  ]}
}]}}
"""

# An index-shaped payload: neither financialData nor recommendationTrend.
_BARE = """
{"quoteSummary": {"error": null, "result": [{"quoteType": {"shortName": "S&P 500"}}]}}
"""


def test_parses_the_target_range_rating_and_count():
    consensus = parse_consensus(_FULL, "005930.KS")
    assert isinstance(consensus, Consensus)
    assert consensus.target_high_price == pytest.approx(725000.0)
    assert consensus.target_low_price == pytest.approx(210000.0)
    assert consensus.target_mean_price == pytest.approx(470630.3)
    assert consensus.target_median_price == pytest.approx(450000.0)
    assert consensus.recommendation_mean == pytest.approx(1.4)
    assert consensus.recommendation == "strong_buy"      # a bare string, via as_str
    assert consensus.analyst_count == 37


def test_parses_the_rating_trend_buckets_in_order():
    consensus = parse_consensus(_FULL, "005930.KS")
    assert len(consensus.trend) == 2
    first = consensus.trend[0]
    assert isinstance(first, RatingTrend)
    assert first.period == "0m"
    counts = (first.strong_buy, first.buy, first.hold, first.sell, first.strong_sell)
    assert counts == (11, 25, 1, 0, 0)                   # bare ints; a 0 stays 0, not None
    assert consensus.trend[1].period == "-1m"
    assert consensus.trend[1].strong_sell == 1


def test_scalars_none_and_trend_empty_when_both_modules_absent():
    """A symbol Yahoo carries neither module for: every scalar None (not 0), and the
    trend an empty tuple (not an error)."""
    consensus = parse_consensus(_BARE, "^GSPC")
    assert consensus.target_mean_price is None
    assert consensus.recommendation is None
    assert consensus.analyst_count is None
    assert consensus.trend == ()


def test_only_financial_data_present_parses_scalars_with_empty_trend():
    """The two modules are independently optional -- financialData without a
    recommendationTrend still parses the targets, and the trend is an empty tuple."""
    payload = json.loads(_FULL)
    del payload["quoteSummary"]["result"][0]["recommendationTrend"]
    consensus = parse_consensus(json.dumps(payload), "005930.KS")
    assert consensus.target_mean_price == pytest.approx(470630.3)
    assert consensus.trend == ()


def test_only_trend_present_parses_trend_with_none_scalars():
    """The other way: a recommendationTrend without financialData parses the buckets
    while every target/rating scalar is None."""
    payload = json.loads(_FULL)
    del payload["quoteSummary"]["result"][0]["financialData"]
    consensus = parse_consensus(json.dumps(payload), "005930.KS")
    assert consensus.target_mean_price is None
    assert consensus.analyst_count is None
    assert len(consensus.trend) == 2
    assert consensus.trend[0].period == "0m"


def test_a_non_dict_trend_row_is_skipped_not_crashed():
    """A scalar where a bucket dict is expected is skipped; the valid rows around it
    still parse, in order."""
    payload = json.loads(_FULL)
    payload["quoteSummary"]["result"][0]["recommendationTrend"]["trend"].insert(1, "junk")
    consensus = parse_consensus(json.dumps(payload), "005930.KS")
    assert [bucket.period for bucket in consensus.trend] == ["0m", "-1m"]


def test_one_absent_target_key_is_none_while_its_siblings_parse():
    """The target fields are independently optional -- a missing targetHighPrice must
    not drag its siblings to None."""
    payload = json.loads(_FULL)
    del payload["quoteSummary"]["result"][0]["financialData"]["targetHighPrice"]
    consensus = parse_consensus(json.dumps(payload), "005930.KS")
    assert consensus.target_high_price is None
    assert consensus.target_low_price == pytest.approx(210000.0)
    assert consensus.recommendation == "strong_buy"


def test_an_empty_box_is_none_not_zero():
    """A boxed field left as {} is "present but unset" -- None, not 0."""
    payload = json.loads(_FULL)
    payload["quoteSummary"]["result"][0]["financialData"]["targetHighPrice"] = {}
    consensus = parse_consensus(json.dumps(payload), "005930.KS")
    assert consensus.target_high_price is None
    assert consensus.analyst_count == 37
