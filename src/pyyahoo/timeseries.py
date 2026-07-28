"""Parsing Yahoo's fundamentals-timeseries response into dated financial lines.

Pure function of the payload -- no network. Where ``profile.py`` reads a *snapshot*
of fundamentals as of now, this reads their *history*:
``/ws/fundamentals-timeseries`` answers a line item (``annualTotalRevenue``,
``quarterlyNetIncome``, ...) as a dated series, so a value can be placed at the
period it was reported for.

One request may ask several ``type``s at once; Yahoo returns one series per type,
and this returns one ``FinancialSeries`` per type in the same order. Each point
carries its ``as_of_date`` (the period end Yahoo reports it against), so a point is
dated by the fiscal period, not by when it was fetched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .errors import YahooParseError
from .payload import iso_to_date, unwrap_raw, unwrap_result


@dataclass(frozen=True, slots=True)
class FinancialPoint:
    """One reported value at one fiscal period end.

    ``period_type`` is Yahoo's own label for the span the value covers ("12M" for
    an annual line, "3M" for a quarterly one). ``value`` is in ``currency``.
    """

    as_of_date: date
    value: float
    period_type: str | None
    currency: str | None


@dataclass(frozen=True, slots=True)
class FinancialSeries:
    """One line item's history for one symbol.

    ``metric`` is Yahoo's own type name (``annualTotalRevenue``). ``points`` is
    oldest-first and drops any period Yahoo reports without a usable value.
    """

    symbol: str
    metric: str
    points: tuple[FinancialPoint, ...]


def parse_timeseries(payload: str, symbol: str) -> tuple[FinancialSeries, ...]:
    """Parse a timeseries response into one ``FinancialSeries`` per requested type.

    Raises:
        YahooRequestError: the response carries an ``error``.
        YahooParseError: the payload is not the timeseries shape.
    """
    results = unwrap_result(payload, "timeseries", "timeseries", symbol)
    series = []
    for entry in results:
        metric = _series_metric(entry)
        if metric is None:
            # No readable meta.type is shape drift (a renamed meta), not a symbol
            # that lacks data -- fail loudly rather than return a short list.
            raise YahooParseError(f"timeseries entry for {symbol} has no readable meta.type")
        # A type the symbol has no data for carries meta.type but no data key; it
        # yields an empty-points series rather than being dropped, so the returned
        # order matches the requested types positionally.
        series.append(FinancialSeries(
            symbol = symbol,
            metric = metric,
            points = _parse_points(entry.get(metric) or []),
        ))
    return tuple(series)


def _series_metric(entry: dict[str, object]) -> str | None:
    """The line-item name of one series, from its ``meta.type``.

    Yahoo keys the data array under that same name, so it is both the label and the
    lookup. None means the entry has no readable ``meta.type`` at all -- shape drift,
    which the caller raises on (distinct from a readable type that simply has no
    data key, which is a legitimately empty series).
    """
    meta = entry.get("meta")
    types = meta.get("type") if isinstance(meta, dict) else None
    if isinstance(types, list) and types and isinstance(types[0], str):
        return types[0]
    return None


def _parse_points(rows: list[object]) -> tuple[FinancialPoint, ...]:
    points = []
    for row in rows:
        if not isinstance(row, dict):
            continue      # Yahoo pads missing periods with null; not a point
        as_of = iso_to_date(row.get("asOfDate"))
        value = unwrap_raw(row.get("reportedValue"))
        if as_of is None or value is None:
            continue
        points.append(FinancialPoint(
            as_of_date  = as_of,
            value       = value,
            period_type = row.get("periodType"),
            currency    = row.get("currencyCode"),
        ))
    return tuple(points)
