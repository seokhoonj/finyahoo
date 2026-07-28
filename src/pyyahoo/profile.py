"""Parsing Yahoo's quoteSummary response into a company's fundamentals.

Pure function of the payload -- no network -- like ``price.py``. The fundamentals a
company screen is built on: sector, size, valuation, and the growth and margin
figures a leader is judged on.

Yahoo returns it as named modules (``assetProfile``, ``summaryDetail``,
``defaultKeyStatistics``, ``financialData``), and a value is either a bare string
(``sector``) or a ``{"raw": .., "fmt": ".."}`` box whose ``raw`` is the number.
Any module or field may be absent -- an index carries only ``summaryDetail``, a
young company has no ``trailingPE`` -- so every numeric field is optional and a
missing one is ``None``, never 0, because 0 is a real reading (a company with no
debt, a stock no institution holds).

This is a **snapshot**, not history: Yahoo reports the fundamentals as of now, with
no as-of date, so a value read today cannot be placed at a past bar. A
point-in-time screen needs dated financials, not this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .payload import unwrap_raw, unwrap_raw_int, unwrap_result

# The modules this reader asks for and knows how to read. Kept here so the client
# requests exactly what ``parse_profile`` consumes -- one list, not two that drift.
# quoteType carries the name; assetProfile the sector/industry; summaryDetail and
# defaultKeyStatistics the size and valuation; financialData the growth/margins.
PROFILE_MODULES = (
    "quoteType",
    "assetProfile",
    "summaryDetail",
    "defaultKeyStatistics",
    "financialData",
)


@dataclass(frozen=True, slots=True)
class Profile:
    """A company's current fundamentals, as far as Yahoo carries them.

    Every field but ``symbol`` is optional: Yahoo omits what it does not have for a
    given security, and the absence is ``None``. Ratios are fractions, not percents
    (``profit_margin=0.21`` is 21%); ``market_cap`` and ``shares_outstanding`` are
    counts in the symbol's own currency and share unit.
    """

    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    currency: str | None
    market_cap: int | None
    shares_outstanding: int | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    trailing_eps: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    profit_margin: float | None
    operating_margin: float | None
    return_on_equity: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    beta: float | None


def parse_profile(payload: str, symbol: str) -> Profile:
    """Parse a quoteSummary response into ``symbol``'s fundamentals.

    ``symbol`` is passed rather than read from the payload, which does not reliably
    echo it.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown ticker,
            or a crumb the caller must re-mint.
        YahooParseError: the payload is not JSON, or not the quoteSummary shape.
    """
    result = unwrap_result(payload, "quoteSummary", "profile", symbol)[0]

    # Merge the modules into one flat lookup: each field lives in exactly one
    # module, so there is no collision, and a merged view spares the reader from
    # knowing which module holds which field.
    modules: dict[str, Any] = {}
    for module in result.values():
        if isinstance(module, dict):
            modules.update(module)

    return Profile(
        symbol              = symbol,
        name                = modules.get("longName") or modules.get("shortName"),
        sector              = modules.get("sector"),
        industry            = modules.get("industry"),
        currency            = modules.get("currency"),
        market_cap          = unwrap_raw_int(modules.get("marketCap")),
        shares_outstanding  = unwrap_raw_int(modules.get("sharesOutstanding")),
        trailing_pe         = unwrap_raw(modules.get("trailingPE")),
        forward_pe          = unwrap_raw(modules.get("forwardPE")),
        price_to_book       = unwrap_raw(modules.get("priceToBook")),
        trailing_eps        = unwrap_raw(modules.get("trailingEps")),
        revenue_growth      = unwrap_raw(modules.get("revenueGrowth")),
        earnings_growth     = unwrap_raw(modules.get("earningsGrowth")),
        profit_margin       = unwrap_raw(modules.get("profitMargins")),
        operating_margin    = unwrap_raw(modules.get("operatingMargins")),
        return_on_equity    = unwrap_raw(modules.get("returnOnEquity")),
        fifty_two_week_high = unwrap_raw(modules.get("fiftyTwoWeekHigh")),
        fifty_two_week_low  = unwrap_raw(modules.get("fiftyTwoWeekLow")),
        beta                = unwrap_raw(modules.get("beta")),
    )
