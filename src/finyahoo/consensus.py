"""Parsing Yahoo's quoteSummary into the sell-side analyst consensus.

Pure function of the payload -- no network -- like ``profile.py``. Where ``profile``
carries what a company *is* (its own fundamentals), this carries what analysts
*expect* of it: the target-price range, the mean rating and how many opinions back
it, and the recent drift of those ratings. It is a separate read from the single
third-party (Trading Central) call in ``insights.py`` -- this is the sell-side
aggregate Yahoo builds across analysts, from the ``financialData`` and
``recommendationTrend`` modules.

A snapshot as of now, not history: Yahoo carries the current aggregate with no
as-of date. The rating ``trend`` is the one dated part -- monthly buckets over the
recent months, most-recent first (``0m`` = current, ``-1m`` = a month ago).
"""

from __future__ import annotations

from dataclasses import dataclass

from .payload import as_str, first_dict, unwrap_raw, unwrap_raw_int, unwrap_result

# The two modules this reader asks for: financialData carries the target-price range,
# the mean rating, and the analyst count; recommendationTrend the monthly buckets.
CONSENSUS_MODULES = ("financialData", "recommendationTrend")


@dataclass(frozen=True, slots=True)
class RatingTrend:
    """The rating-count breakdown for one month bucket (``period`` ``0m`` = current,
    ``-1m`` = a month ago, ...). A count is ``None`` only when Yahoo omits it, never
    0 -- 0 is a real reading (no analyst in that rating)."""

    period: str
    strong_buy: int | None = None
    buy: int | None = None
    hold: int | None = None
    sell: int | None = None
    strong_sell: int | None = None


@dataclass(frozen=True, slots=True)
class Consensus:
    """The sell-side analyst consensus for one symbol, as far as Yahoo carries it.

    The target-price range (``target_high_price`` .. ``target_median_price``), the
    mean rating (``recommendation_mean``: 1.0 = strong buy .. 5.0 = strong sell) and
    its key (``recommendation``: ``strong_buy``/``buy``/...), and ``analyst_count``,
    how many opinions back the range -- plus ``trend``, the monthly rating-count
    buckets most-recent first.

    Distinct from ``Insights`` (``fetch_insights``), which is one third-party
    provider's call; this is the across-analyst aggregate. Every field but ``symbol``
    is optional and a missing one is ``None`` (never 0 -- ``analyst_count=0``, a
    covered-but-unrated name, is a real reading).
    """

    symbol: str
    target_high_price: float | None = None
    target_low_price: float | None = None
    target_mean_price: float | None = None
    target_median_price: float | None = None
    recommendation_mean: float | None = None
    recommendation: str | None = None
    analyst_count: int | None = None
    trend: tuple[RatingTrend, ...] = ()


def parse_consensus(payload: str, symbol: str) -> Consensus:
    """Parse a quoteSummary response into ``symbol``'s analyst consensus.

    ``symbol`` is passed rather than read from the payload, which does not reliably
    echo it.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown ticker,
            or a crumb the caller must re-mint.
        YahooParseError: the payload is not JSON, or not the quoteSummary shape.
    """
    result = first_dict(
        unwrap_result(payload, "quoteSummary", "consensus", symbol), "consensus")
    financial = result.get("financialData")
    financial = financial if isinstance(financial, dict) else {}
    trend_module = result.get("recommendationTrend")
    trend_module = trend_module if isinstance(trend_module, dict) else {}
    return Consensus(
        symbol              = symbol,
        target_high_price   = unwrap_raw(financial.get("targetHighPrice")),
        target_low_price    = unwrap_raw(financial.get("targetLowPrice")),
        target_mean_price   = unwrap_raw(financial.get("targetMeanPrice")),
        target_median_price = unwrap_raw(financial.get("targetMedianPrice")),
        recommendation_mean = unwrap_raw(financial.get("recommendationMean")),
        recommendation      = as_str(financial.get("recommendationKey")),
        analyst_count       = unwrap_raw_int(financial.get("numberOfAnalystOpinions")),
        trend               = _parse_trend(trend_module.get("trend")),
    )


def _parse_trend(rows: object) -> tuple[RatingTrend, ...]:
    """The monthly rating buckets, in Yahoo's order (most-recent first). Anything but
    a list of dicts (a module Yahoo omitted) yields an empty tuple, not an error --
    the trend is a convenience, and its absence is a real "Yahoo carried none". The
    counts are bare ints in this module, which ``unwrap_raw_int`` reads as readily as
    the boxed numbers elsewhere."""
    if not isinstance(rows, list):
        return ()
    return tuple(
        RatingTrend(
            period      = as_str(row.get("period")) or "",
            strong_buy  = unwrap_raw_int(row.get("strongBuy")),
            buy         = unwrap_raw_int(row.get("buy")),
            hold        = unwrap_raw_int(row.get("hold")),
            sell        = unwrap_raw_int(row.get("sell")),
            strong_sell = unwrap_raw_int(row.get("strongSell")),
        )
        for row in rows
        if isinstance(row, dict)
    )
