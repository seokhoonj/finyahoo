"""Parsing Yahoo's predefined-screener response into a named screen's members.

Pure function of the payload -- no network.
``/v1/finance/screener/predefined/saved`` runs one of Yahoo's own saved screens
(``most_actives``, ``day_gainers``, ``undervalued_growth_stocks``, ...) and returns
its members. Each member is a quote record in the same shape ``/v7/finance/quote``
returns, so the parsing is shared with ``quote.py`` -- a member is a ``Quote``.

``total`` is how many the screen matched; ``members`` is the page this request
asked for (``count``), not necessarily all of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .payload import each_dict, first_dict, unwrap_raw_int, unwrap_result
from .quote import Quote, parse_quote_record


@dataclass(frozen=True, slots=True)
class Screen:
    """One predefined screen's result page.

    ``screen_id`` is Yahoo's canonical name (``MOST_ACTIVES``); ``total`` is the
    full match count; ``members`` is this page, each a ``Quote``.
    """

    screen_id: str
    title: str | None
    total: int | None
    members: tuple[Quote, ...]


def parse_screener(payload: str) -> Screen:
    """Parse a predefined-screener response into a ``Screen``.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown scrId.
        YahooParseError: the payload is not the screener shape.
    """
    result = first_dict(unwrap_result(payload, "finance", "screener", "the requested screen"),
                        "screener")
    return Screen(
        screen_id = result.get("canonicalName", ""),
        title     = result.get("title"),
        total     = unwrap_raw_int(result.get("total")),
        members   = tuple(
            parse_quote_record(record) for record in each_dict(result.get("quotes", []), "screener")
        ),
    )
