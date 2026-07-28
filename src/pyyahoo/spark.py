"""Parsing Yahoo's spark response into a compact close series per symbol.

Pure function of the payload -- no network. ``/v8/finance/spark`` is chart's little
sibling: many symbols at once, close-only, for a sparkline. The envelope is not the
usual ``{result, error}`` -- the top level is a map keyed by symbol -- so this
parser walks that map rather than ``unwrap_result``.

For full OHLCV and corporate actions, fetch one symbol through ``fetch_history``;
spark is the cheap multi-symbol overview, not a replacement for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .errors import YahooParseError
from .payload import epoch_to_datetime, load_json

# Yahoo's documented spark/chart vocabularies, as closed sets so an illegal value
# fails at the call site rather than at Yahoo. `SparkPeriod` is the lookback window
# (Yahoo's ``range`` query arg); `SparkInterval` is the bar size within it.
SparkPeriod = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
SparkInterval = Literal[
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"
]


@dataclass(frozen=True, slots=True)
class SparkPoint:
    """One close at one instant."""

    time: datetime
    close: float


@dataclass(frozen=True, slots=True)
class Spark:
    """One symbol's close series over the requested range.

    ``previous_close`` is the close before the series starts (Yahoo's
    ``chartPreviousClose``), the baseline a sparkline draws its change against.
    ``points`` is oldest-first and drops any instant Yahoo has no close for.
    """

    symbol: str
    previous_close: float | None
    points: tuple[SparkPoint, ...]


def parse_spark(payload: str) -> tuple[Spark, ...]:
    """Parse a spark response into one ``Spark`` per symbol.

    Order is not guaranteed by Yahoo's symbol-keyed map, so the result is sorted by
    symbol for a stable return.

    Raises:
        YahooParseError: the payload is not JSON or not the spark map shape.
    """
    root = load_json(payload, "spark")
    if not isinstance(root, dict):
        raise YahooParseError(f"spark payload is not a symbol map: {type(root).__name__}")
    sparks = []
    for symbol, series in root.items():
        if not isinstance(series, dict):
            raise YahooParseError(f"spark entry for {symbol} is not an object")
        timestamps = series.get("timestamp") or []
        closes = series.get("close") or []
        # Parallel arrays that disagree in length are a ragged payload, not data to
        # truncate silently -- fail loudly, as the chart parser does.
        try:
            pairs = list(zip(timestamps, closes, strict=True))
        except ValueError as err:
            raise YahooParseError(
                f"spark entry for {symbol} is ragged: "
                f"{len(timestamps)} timestamps vs {len(closes)} closes") from err
        points = tuple(
            SparkPoint(time=moment, close=close)
            for epoch, close in pairs
            if (moment := epoch_to_datetime(epoch)) is not None and close is not None
        )
        sparks.append(Spark(
            symbol         = symbol,
            previous_close = series.get("chartPreviousClose"),
            points         = points,
        ))
    return tuple(sorted(sparks, key=lambda spark: spark.symbol))
