"""Yahoo recommendations-parsing tests that need no network."""

import pytest

from finyahoo import Recommendation, YahooParseError, YahooRequestError
from finyahoo.recommend import parse_recommendations

_THREE = """
{"finance": {"error": null, "result": [{
  "symbol": "AAPL",
  "recommendedSymbols": [
    {"symbol": "AMZN", "score": 0.189631},
    {"symbol": "TSLA", "score": 0.179},
    {"symbol": "GOOG"}
  ]
}]}}
"""

_ERROR = '{"finance": {"result": null, "error": {"code": "Not Found", "description": "no"}}}'


def test_parses_recommended_symbols_with_scores():
    recs = parse_recommendations(_THREE, "AAPL")
    assert isinstance(recs[0], Recommendation)
    assert [r.symbol for r in recs] == ["AMZN", "TSLA", "GOOG"]
    assert recs[0].score == pytest.approx(0.189631)


def test_a_recommendation_without_a_score_is_none():
    assert parse_recommendations(_THREE, "AAPL")[2].score is None


def test_error_envelope_raises_request_error():
    with pytest.raises(YahooRequestError):
        parse_recommendations(_ERROR, "AAPL")


def test_non_recommendation_shape_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_recommendations('{"unexpected": "shape"}', "AAPL")
