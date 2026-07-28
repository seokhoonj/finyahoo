"""Parsing Yahoo's recommendations response into similar symbols.

Pure function of the payload -- no network. ``/v6/finance/recommendationsbysymbol``
answers with the symbols Yahoo considers similar to the one asked for, each with a
similarity ``score`` (higher is closer). Carried as data, not a recommendation to
act on.
"""

from __future__ import annotations

from dataclasses import dataclass

from .payload import unwrap_result


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A symbol similar to the one queried, with Yahoo's similarity score."""

    symbol: str
    score: float | None


def parse_recommendations(payload: str, symbol: str) -> tuple[Recommendation, ...]:
    """Parse a recommendations response into the similar symbols for ``symbol``.

    ``symbol`` labels the request in any error message; the result carries the
    *recommended* symbols, not the queried one.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown symbol.
        YahooParseError: the payload is not the expected shape.
    """
    results = unwrap_result(payload, "finance", "recommendations", symbol)
    similar = results[0].get("recommendedSymbols", [])
    return tuple(
        Recommendation(symbol=item.get("symbol", ""), score=item.get("score"))
        for item in similar
    )
