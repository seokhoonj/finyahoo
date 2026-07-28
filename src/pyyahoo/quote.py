"""Parsing Yahoo's quote response into a real-time snapshot per symbol.

Pure function of the payload -- no network. ``/v7/finance/quote`` answers a list of
symbols at once, each a flat record of *bare* numbers (unlike quoteSummary's
``{raw, fmt}`` boxes), so a field is read directly and a missing one is ``None``.

This is the live snapshot -- price, the day's range, the trailing multiples -- as
of the request, not history. The screener endpoint returns the same record shape,
so ``parse_quote_record`` is shared with ``screener.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .payload import epoch_to_datetime, unwrap_raw_int, unwrap_result


@dataclass(frozen=True, slots=True)
class Quote:
    """One symbol's live snapshot.

    ``price``/``previous_close``/``change`` are in the symbol's ``currency``.
    ``change_percent`` is a percent (2.5 is +2.5%), matching Yahoo's own field.
    Every field but ``symbol`` may be ``None`` -- an index has no ``trailing_pe``,
    a pre-market quote no ``volume`` yet.
    """

    symbol: str
    name: str | None
    quote_type: str | None
    currency: str | None
    exchange: str | None
    market_state: str | None
    price: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None
    day_open: float | None
    day_high: float | None
    day_low: float | None
    volume: int | None
    market_cap: int | None
    shares_outstanding: int | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    fifty_day_average: float | None
    two_hundred_day_average: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    trailing_eps: float | None
    forward_eps: float | None
    dividend_yield: float | None
    market_time: datetime | None


def parse_quotes(payload: str) -> tuple[Quote, ...]:
    """Parse a quote response into one ``Quote`` per symbol, in Yahoo's order.

    Raises:
        YahooRequestError: the response carries an ``error``.
        YahooParseError: the payload is not the quoteResponse shape.
    """
    records = unwrap_result(payload, "quoteResponse", "quote", "the requested symbols")
    return tuple(parse_quote_record(record) for record in records)


def parse_quote_record(record: dict[str, Any]) -> Quote:
    """One quote record (from ``/v7/finance/quote`` or a screener) into a ``Quote``."""
    return Quote(
        symbol                  = record.get("symbol", ""),
        name                    = record.get("longName") or record.get("shortName")
                                  or record.get("displayName"),
        quote_type              = record.get("quoteType"),
        currency                = record.get("currency"),
        exchange                = record.get("fullExchangeName") or record.get("exchange"),
        market_state            = record.get("marketState"),
        price                   = record.get("regularMarketPrice"),
        previous_close          = record.get("regularMarketPreviousClose"),
        change                  = record.get("regularMarketChange"),
        change_percent          = record.get("regularMarketChangePercent"),
        day_open                = record.get("regularMarketOpen"),
        day_high                = record.get("regularMarketDayHigh"),
        day_low                 = record.get("regularMarketDayLow"),
        volume                  = unwrap_raw_int(record.get("regularMarketVolume")),
        market_cap              = unwrap_raw_int(record.get("marketCap")),
        shares_outstanding      = unwrap_raw_int(record.get("sharesOutstanding")),
        fifty_two_week_high     = record.get("fiftyTwoWeekHigh"),
        fifty_two_week_low      = record.get("fiftyTwoWeekLow"),
        fifty_day_average       = record.get("fiftyDayAverage"),
        two_hundred_day_average = record.get("twoHundredDayAverage"),
        trailing_pe             = record.get("trailingPE"),
        forward_pe              = record.get("forwardPE"),
        price_to_book           = record.get("priceToBook"),
        trailing_eps            = record.get("epsTrailingTwelveMonths"),
        forward_eps             = record.get("epsForward"),
        dividend_yield          = record.get("dividendYield"),
        market_time             = epoch_to_datetime(record.get("regularMarketTime")),
    )
