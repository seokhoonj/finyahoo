"""Parsing Yahoo's quoteSummary response into a company's fundamentals and live snapshot.

Pure function of the payload -- no network -- like ``price.py``. The fundamentals a
company screen is built on (sector, size, valuation, growth, margins), plus the live
snapshot the ``price`` module carries (current price, the day's change and range,
market state); one call answers both.

Yahoo returns it as named modules (``assetProfile``, ``summaryDetail``,
``defaultKeyStatistics``, ``financialData``, ``price``), and a value is either a bare
string (``sector``, ``marketState``) or a ``{"raw": .., "fmt": ".."}`` box whose
``raw`` is the number. Any module or field may be absent -- an index carries only
``summaryDetail`` and ``price``, a young company has no ``trailingPE`` -- so every
field but ``symbol`` is optional and a missing one is ``None``, never 0, because 0 is
a real reading (a company with no debt, a stock no institution holds).

This is a **snapshot**, not history: Yahoo reports it as of now, with no as-of date,
so a value read today cannot be placed at a past bar. A point-in-time screen needs
dated financials, not this. ``change_percent`` is the quoteSummary ``raw`` -- a
fraction (-0.05 is -5%), unlike ``Quote.change_percent``, the percent /v7 gives.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .payload import epoch_to_datetime, first_dict, unwrap_raw, unwrap_raw_int, unwrap_result

# The modules this reader asks for and knows how to read. Kept here so the client
# requests exactly what ``parse_profile`` consumes -- one list, not two that drift.
# quoteType carries the name; assetProfile the sector/industry; summaryDetail and
# defaultKeyStatistics the size and valuation; financialData the growth/margins;
# price the live snapshot (current price, day change/range, market state) -- the
# same call, so the single-symbol view carries what ``quote`` reads across many.
PROFILE_MODULES = (
    "quoteType",
    "assetProfile",
    "summaryDetail",
    "defaultKeyStatistics",
    "financialData",
    "price",
)


@dataclass(frozen=True, slots=True)
class Profile:
    """A company's fundamentals and its live price snapshot, as far as Yahoo carries them.

    One quoteSummary call answers both: the ``price`` module carries the live snapshot
    (current price, the day's change and range, market state), the other modules the
    fundamentals (sector, size, valuation, growth, margins). ``quote`` reads the
    snapshot for *many* symbols at once; this is the deep single-symbol view.

    Every field but ``symbol`` is optional: Yahoo omits what it does not have for a
    given security, and the absence is ``None`` (never 0 -- 0 is a real reading).
    Ratios are fractions, not percents (``profit_margin=0.21`` is 21%,
    ``change_percent=-0.05`` is -5%): this is the quoteSummary convention, so
    ``change_percent`` here is a fraction -- unlike ``Quote.change_percent``, which
    mirrors the percent the /v7 endpoint gives. ``market_cap``, ``shares_outstanding``,
    and ``volume`` are counts; prices are in ``currency``.
    """

    symbol: str
    # Identity.
    name: str | None = None
    quote_type: str | None = None
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    currency: str | None = None
    # Live snapshot -- the price module, the same call (quote reads this across many
    # symbols; here it rides along with the fundamentals for one).
    market_state: str | None = None
    price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    day_open: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: int | None = None
    market_time: datetime | None = None
    # Size.
    market_cap: int | None = None
    shares_outstanding: int | None = None
    # Valuation.
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    trailing_eps: float | None = None
    forward_eps: float | None = None
    dividend_yield: float | None = None
    # Growth & profitability.
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    return_on_equity: float | None = None
    # Trend & risk.
    fifty_day_average: float | None = None
    two_hundred_day_average: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    beta: float | None = None


def parse_profile(payload: str, symbol: str) -> Profile:
    """Parse a quoteSummary response into ``symbol``'s fundamentals and live snapshot.

    ``symbol`` is passed rather than read from the payload, which does not reliably
    echo it.

    Raises:
        YahooRequestError: the response carries an ``error`` -- an unknown ticker,
            or a crumb the caller must re-mint.
        YahooParseError: the payload is not JSON, or not the quoteSummary shape.
    """
    result = first_dict(unwrap_result(payload, "quoteSummary", "profile", symbol), "profile")

    # Merge the modules into one flat lookup, so the reader is spared knowing which
    # module holds which field. A few keys appear in more than one module (currency in
    # summaryDetail and financialData; marketCap/quoteType/longName in price too) and
    # carry the same value, so a later module overwriting an earlier one is harmless.
    # Iterating PROFILE_MODULES (not result's payload order) makes that precedence
    # deterministic -- the last module listed wins -- rather than depending on the
    # order Yahoo happens to serialize the modules in.
    modules: dict[str, Any] = {}
    for name in PROFILE_MODULES:
        module = result.get(name)
        if isinstance(module, dict):
            modules.update(module)

    return Profile(
        symbol                  = symbol,
        name                    = modules.get("longName") or modules.get("shortName"),
        quote_type              = modules.get("quoteType"),
        sector                  = modules.get("sector"),
        industry                = modules.get("industry"),
        exchange                = modules.get("exchangeName") or modules.get("exchange"),
        currency                = modules.get("currency"),
        market_state            = modules.get("marketState"),
        price                   = unwrap_raw(modules.get("regularMarketPrice")),
        previous_close          = unwrap_raw(modules.get("regularMarketPreviousClose")),
        change                  = unwrap_raw(modules.get("regularMarketChange")),
        change_percent          = unwrap_raw(modules.get("regularMarketChangePercent")),
        day_open                = unwrap_raw(modules.get("regularMarketOpen")),
        day_high                = unwrap_raw(modules.get("regularMarketDayHigh")),
        day_low                 = unwrap_raw(modules.get("regularMarketDayLow")),
        volume                  = unwrap_raw_int(modules.get("regularMarketVolume")),
        market_time             = epoch_to_datetime(unwrap_raw(modules.get("regularMarketTime"))),
        market_cap              = unwrap_raw_int(modules.get("marketCap")),
        shares_outstanding      = unwrap_raw_int(modules.get("sharesOutstanding")),
        trailing_pe             = unwrap_raw(modules.get("trailingPE")),
        forward_pe              = unwrap_raw(modules.get("forwardPE")),
        price_to_book           = unwrap_raw(modules.get("priceToBook")),
        trailing_eps            = unwrap_raw(modules.get("trailingEps")),
        forward_eps             = unwrap_raw(modules.get("forwardEps")),
        dividend_yield          = unwrap_raw(modules.get("dividendYield")),
        revenue_growth          = unwrap_raw(modules.get("revenueGrowth")),
        earnings_growth         = unwrap_raw(modules.get("earningsGrowth")),
        profit_margin           = unwrap_raw(modules.get("profitMargins")),
        operating_margin        = unwrap_raw(modules.get("operatingMargins")),
        return_on_equity        = unwrap_raw(modules.get("returnOnEquity")),
        fifty_day_average       = unwrap_raw(modules.get("fiftyDayAverage")),
        two_hundred_day_average = unwrap_raw(modules.get("twoHundredDayAverage")),
        fifty_two_week_high     = unwrap_raw(modules.get("fiftyTwoWeekHigh")),
        fifty_two_week_low      = unwrap_raw(modules.get("fiftyTwoWeekLow")),
        beta                    = unwrap_raw(modules.get("beta")),
    )
