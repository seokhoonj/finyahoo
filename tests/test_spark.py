"""Yahoo spark-parsing tests that need no network.

Spark's top level is a map keyed by symbol, not a ``{result, error}`` envelope, so
the fixtures cover that map, a null close dropped from the series, the stable
symbol sort, and a non-map payload.
"""

import pytest

from pyyahoo import Spark, YahooParseError, parse_spark

_TWO = """
{"MSFT": {"symbol": "MSFT", "timestamp": [1700000000, 1700086400, 1700172800],
          "close": [370.0, null, 375.5], "chartPreviousClose": 368.0},
 "AAPL": {"symbol": "AAPL", "timestamp": [1700000000, 1700086400],
          "close": [190.0, 191.2], "chartPreviousClose": 189.0}}
"""


def test_parses_one_spark_per_symbol_sorted_by_symbol():
    sparks = parse_spark(_TWO)
    assert isinstance(sparks[0], Spark)
    assert [s.symbol for s in sparks] == ["AAPL", "MSFT"]     # sorted, not input order


def test_previous_close_is_the_chart_previous_close():
    msft = {s.symbol: s for s in parse_spark(_TWO)}["MSFT"]
    assert msft.previous_close == pytest.approx(368.0)


def test_a_null_close_is_dropped_from_the_series():
    msft = {s.symbol: s for s in parse_spark(_TWO)}["MSFT"]
    assert len(msft.points) == 2                              # the null middle bar is gone
    assert [p.close for p in msft.points] == [pytest.approx(370.0), pytest.approx(375.5)]


def test_points_are_datetimes_oldest_first():
    aapl = {s.symbol: s for s in parse_spark(_TWO)}["AAPL"]
    assert aapl.points[0].time < aapl.points[1].time


def test_ragged_timestamp_and_close_lengths_raise_rather_than_truncate():
    """3 timestamps but 2 closes is a ragged payload; truncating silently would
    return a short series that reads as complete (the chart parser also raises)."""
    ragged = """
    {"AAPL": {"symbol": "AAPL", "timestamp": [1700000000, 1700086400, 1700172800],
              "close": [190.0, 191.2], "chartPreviousClose": 189.0}}
    """
    with pytest.raises(YahooParseError):
        parse_spark(ragged)


def test_a_non_map_payload_raises_parse_error():
    with pytest.raises(YahooParseError):
        parse_spark('["not", "a", "map"]')


def test_a_non_numeric_close_is_dropped_not_stored_in_the_float_field():
    """A JSON true/string/box in the close array must not land in SparkPoint.close;
    guarded by is_number like the chart parser, so it drops rather than lies."""
    junk = """
    {"AAPL": {"timestamp": [1700000000, 1700086400], "close": [190.0, true],
              "chartPreviousClose": 189.0}}
    """
    aapl = parse_spark(junk)[0]
    assert [p.close for p in aapl.points] == [pytest.approx(190.0)]


def test_a_non_numeric_chart_previous_close_becomes_none():
    """chartPreviousClose is a bare number; a bool or box must read as None, not a
    fake reading in previous_close."""
    boxed = '{"AAPL": {"timestamp": [], "close": [], "chartPreviousClose": {"raw": 1}}}'
    assert parse_spark(boxed)[0].previous_close is None
