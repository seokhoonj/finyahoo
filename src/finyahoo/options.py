"""Parsing Yahoo's options response into an option chain.

Pure function of the payload -- no network. ``/v7/finance/options`` answers one
underlying with its available ``expiration_dates`` and ``strikes``, and -- for one
expiration at a time -- the calls and puts at each strike. A request without an
expiration returns the nearest one; passing a date returns that expiration's chain.

Contracts carry the fields an options screen reads -- strike, bid/ask, last,
volume, open interest, implied volatility, moneyness -- each a bare number, with a
missing one ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .errors import YahooParseError
from .payload import (
    as_bool,
    as_number,
    as_str,
    each_dict,
    epoch_to_date,
    epoch_to_datetime,
    first_dict,
    is_number,
    unwrap_raw_int,
    unwrap_result,
)


@dataclass(frozen=True, slots=True)
class OptionContract:
    """One call or put at one strike and expiration.

    ``implied_volatility`` is a fraction (0.25 is 25%), Yahoo's own form.
    ``change_percent`` is a percent (2.5 is +2.5%), matching ``Quote.change_percent``.
    ``is_in_the_money`` is Yahoo's flag, not recomputed here.
    """

    contract_symbol: str
    strike: float | None
    currency: str | None
    last_price: float | None
    change: float | None
    change_percent: float | None
    bid: float | None
    ask: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    is_in_the_money: bool | None
    contract_size: str | None
    expiration: date | None
    last_trade: datetime | None


@dataclass(frozen=True, slots=True)
class OptionChain:
    """One underlying's option chain for a single expiration.

    ``expiration_dates`` and ``strikes`` list *all* the expirations and strikes the
    underlying offers; ``calls`` and ``puts`` are the contracts for the *one*
    expiration this response carries (the nearest, unless a date was requested).
    """

    underlying: str
    expiration_dates: tuple[date, ...]
    strikes: tuple[float, ...]
    expiration: date | None
    calls: tuple[OptionContract, ...]
    puts: tuple[OptionContract, ...]


def parse_options(payload: str) -> OptionChain:
    """Parse an options response into one expiration's ``OptionChain``.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown symbol.
        YahooParseError: the payload is not the optionChain shape.
    """
    result = first_dict(unwrap_result(payload, "optionChain", "options", "the requested symbol"),
                        "options")
    # A missing "options" key is shape drift and must fail loudly; an empty list is
    # a real underlying that lists no options, and yields an empty chain.
    if "options" not in result:
        raise YahooParseError("optionChain result has no options block")
    # An empty options list is a real underlying with no chain; a non-empty one must
    # carry an object first element, so drift there fails loudly like the outer result.
    chains = each_dict(result["options"], "options")
    chain = chains[0] if chains else {}
    return OptionChain(
        underlying       = result.get("underlyingSymbol", ""),
        expiration_dates = tuple(
            day for epoch in result.get("expirationDates", [])
            if (day := epoch_to_date(epoch)) is not None
        ),
        strikes          = tuple(s for s in result.get("strikes", []) if is_number(s)),
        expiration       = epoch_to_date(chain.get("expirationDate")),
        calls            = _parse_contracts(each_dict(chain.get("calls") or [], "options calls")),
        puts             = _parse_contracts(each_dict(chain.get("puts") or [], "options puts")),
    )


def _parse_contracts(rows: list[dict[str, Any]]) -> tuple[OptionContract, ...]:
    return tuple(
        OptionContract(
            contract_symbol    = row.get("contractSymbol", ""),
            strike             = as_number(row.get("strike")),
            currency           = as_str(row.get("currency")),
            last_price         = as_number(row.get("lastPrice")),
            change             = as_number(row.get("change")),
            change_percent     = as_number(row.get("percentChange")),
            bid                = as_number(row.get("bid")),
            ask                = as_number(row.get("ask")),
            volume             = unwrap_raw_int(row.get("volume")),
            open_interest      = unwrap_raw_int(row.get("openInterest")),
            implied_volatility = as_number(row.get("impliedVolatility")),
            is_in_the_money    = as_bool(row.get("inTheMoney")),
            contract_size      = as_str(row.get("contractSize")),
            expiration         = epoch_to_date(row.get("expiration")),
            last_trade         = epoch_to_datetime(row.get("lastTradeDate")),
        )
        for row in rows
    )
