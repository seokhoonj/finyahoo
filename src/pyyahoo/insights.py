"""Parsing Yahoo's insights response into a research summary.

Pure function of the payload -- no network. ``/ws/insights`` gathers third-party
research on a symbol: an analyst target and rating, a valuation call, key technical
levels, near-/mid-/long-term technical outlooks, and a list of research reports.
The upstream payload is deeply nested and provider-specific; this reads the stable,
useful leaves into one flat ``Insights`` and leaves the rest.

The figures are the providers' (Argus, Trading Central, ...), carried as data, not
this package's judgement -- ``rating`` is what the provider said, not a signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .errors import YahooParseError
from .payload import as_number, each_dict, iso_to_date, unwrap_result


@dataclass(frozen=True, slots=True)
class InsightReport:
    """One research report Yahoo lists for the symbol."""

    report_id: str
    title: str | None
    provider: str | None
    published_on: date | None
    summary: str | None


@dataclass(frozen=True, slots=True)
class Insights:
    """A symbol's gathered research, flattened to its useful leaves.

    Every field but ``symbol`` may be ``None``: a given provider covers a given
    symbol or does not. ``target_price`` and ``rating`` are the analyst call;
    ``valuation`` is the over/under-valued label; ``support``/``resistance``/
    ``stop_loss`` are the technical levels; the three ``*_outlook`` fields are the
    directional calls for each horizon.
    """

    symbol: str
    target_price: float | None
    rating: str | None
    valuation: str | None
    support: float | None
    resistance: float | None
    stop_loss: float | None
    short_term_outlook: str | None
    mid_term_outlook: str | None
    long_term_outlook: str | None
    sector: str | None
    reports: tuple[InsightReport, ...]


def parse_insights(payload: str, symbol: str) -> Insights:
    """Parse an insights response into a flat ``Insights`` for ``symbol``.

    Raises:
        YahooRequestError: the response carries an ``error``.
        YahooParseError: the payload is not the insights shape.
    """
    result = unwrap_result(payload, "finance", "insights", symbol)
    if not isinstance(result, dict):
        raise YahooParseError(f"insights result for {symbol} is not an object: {type(result).__name__}")
    info = _dict_or_empty(result.get("instrumentInfo"))
    recommendation = _dict_or_empty(info.get("recommendation"))
    valuation = _dict_or_empty(info.get("valuation"))
    technicals = _dict_or_empty(info.get("keyTechnicals"))
    events = _dict_or_empty(info.get("technicalEvents"))
    snapshot = _dict_or_empty(result.get("companySnapshot"))
    return Insights(
        symbol             = result.get("symbol", symbol),
        target_price       = as_number(recommendation.get("targetPrice")),
        rating             = recommendation.get("rating"),
        valuation          = valuation.get("description"),
        support            = as_number(technicals.get("support")),
        resistance         = as_number(technicals.get("resistance")),
        stop_loss          = as_number(technicals.get("stopLoss")),
        short_term_outlook = _direction(events.get("shortTerm")),
        mid_term_outlook   = _direction(events.get("midTerm")),
        long_term_outlook  = _direction(events.get("longTerm")),
        sector             = snapshot.get("sectorInfo"),
        reports            = tuple(
            InsightReport(
                report_id    = report.get("id", ""),
                title        = report.get("title"),
                provider     = report.get("provider"),
                published_on = iso_to_date(report.get("publishedOn")),
                summary      = report.get("summary"),
            )
            for report in each_dict(result.get("reports", []), "insights reports")
        ),
    )


def _dict_or_empty(node: object) -> dict[str, Any]:
    """``node`` if it is a dict, else an empty one -- so a missing branch reads as
    absent fields rather than an AttributeError."""
    return node if isinstance(node, dict) else {}


def _direction(outlook: object) -> str | None:
    """The state description of one horizon's outlook, or None when absent.

    Yahoo nulls a horizon it has no read on, and otherwise carries a
    ``stateDescription`` ("Bullish", "Bearish", ...) that is the one useful leaf.
    """
    state = _dict_or_empty(outlook).get("stateDescription")
    return state if isinstance(state, str) else None
