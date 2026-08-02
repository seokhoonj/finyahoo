"""Parsing Yahoo's quoteSummary response into a company's fundamentals.

Pure function of the payload -- no network -- like ``price.py``. The fundamentals a
company screen is built on: sector, size, valuation, and the growth and margin
figures a leader is judged on. The live price snapshot -- current price, the day's
change and range, market state -- is the ``quote`` reader's job, not this one.

Yahoo returns it as named modules (``assetProfile``, ``summaryDetail``,
``defaultKeyStatistics``, ``financialData``), and a value is either a bare string
(``sector``) or a ``{"raw": .., "fmt": ".."}`` box whose ``raw`` is the number.
Any module or field may be absent -- an index carries only ``summaryDetail``, a
young company has no ``trailingPE`` -- so every field but ``symbol`` is optional and
a missing one is ``None``, never 0, because 0 is a real reading (a company with no
debt, a stock no institution holds).

This is a **snapshot**, not history: Yahoo reports the fundamentals as of now, with
no as-of date, so a value read today cannot be placed at a past bar. A
point-in-time screen needs dated financials, not this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .payload import as_str, first_dict, unwrap_raw, unwrap_raw_int, unwrap_result

# The modules this reader asks for and knows how to read. Kept here so the client
# requests exactly what ``parse_profile`` consumes -- one list, not two that drift.
# quoteType carries the name; assetProfile the sector/industry; summaryDetail and
# defaultKeyStatistics the size and valuation; financialData the growth/margins and
# the sell-side analyst target range and rating.
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

    The fundamentals view: sector and industry, size (market cap, shares), the
    valuation multiples, the growth, margin, and return figures, and the sell-side
    analyst consensus (target-price range, mean rating, and how many opinions back
    it). The live price snapshot is ``Quote``'s domain, read with ``quote``, not
    carried here.

    Every field but ``symbol`` is optional: Yahoo omits what it does not have for a
    given security, and the absence is ``None`` (never 0 -- 0 is a real reading).
    Ratios are fractions, not percents (``profit_margin=0.21`` is 21%);
    ``market_cap`` and ``shares_outstanding`` are counts in the symbol's own currency
    and share unit.
    """

    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    market_cap: int | None = None
    shares_outstanding: int | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    trailing_eps: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    return_on_equity: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    beta: float | None = None
    # Sell-side analyst consensus (financialData): the target-price range and the
    # rating. target_median_price and recommendation may be absent where the mean
    # ones are present; analyst_count is how many opinions the range is built from.
    target_high_price: float | None = None
    target_low_price: float | None = None
    target_mean_price: float | None = None
    target_median_price: float | None = None
    recommendation_mean: float | None = None
    recommendation: str | None = None
    analyst_count: int | None = None


def parse_profile(payload: str, symbol: str) -> Profile:
    """Parse a quoteSummary response into ``symbol``'s fundamentals.

    ``symbol`` is passed rather than read from the payload, which does not reliably
    echo it.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown ticker,
            or a crumb the caller must re-mint.
        YahooParseError: the payload is not JSON, or not the quoteSummary shape.
    """
    result = first_dict(unwrap_result(payload, "quoteSummary", "profile", symbol), "profile")

    # Merge the modules into one flat lookup, so the reader is spared knowing which
    # module holds which field. A few keys appear in more than one module (e.g.
    # currency, in both summaryDetail and financialData) and carry the same value, so
    # a later module overwriting an earlier one is harmless. Iterating PROFILE_MODULES
    # (not result's payload order) makes that precedence deterministic -- the last
    # module listed wins -- rather than depending on the order Yahoo happens to
    # serialize the modules in.
    modules: dict[str, Any] = {}
    for name in PROFILE_MODULES:
        module = result.get(name)
        if isinstance(module, dict):
            modules.update(module)

    return Profile(
        symbol              = symbol,
        name                = as_str(modules.get("longName")) or as_str(modules.get("shortName")),
        sector              = as_str(modules.get("sector")),
        industry            = as_str(modules.get("industry")),
        currency            = as_str(modules.get("currency")),
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
        target_high_price   = unwrap_raw(modules.get("targetHighPrice")),
        target_low_price    = unwrap_raw(modules.get("targetLowPrice")),
        target_mean_price   = unwrap_raw(modules.get("targetMeanPrice")),
        target_median_price = unwrap_raw(modules.get("targetMedianPrice")),
        recommendation_mean = unwrap_raw(modules.get("recommendationMean")),
        recommendation      = as_str(modules.get("recommendationKey")),
        analyst_count       = unwrap_raw_int(modules.get("numberOfAnalystOpinions")),
    )
