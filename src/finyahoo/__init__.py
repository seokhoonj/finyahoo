"""Read prices and fundamentals from Yahoo Finance.

Yahoo publishes no official API. This package reaches the same undocumented JSON
endpoints the finance.yahoo.com web app uses and models their responses as typed
results. They can change without notice; the parsers fail loudly rather than
silently when a shape shifts.

One ``YahooClient`` reaches every endpoint. The two core reads:

  fetch_history  daily/weekly/monthly OHLCV + adjusted close, with the split and
                 dividend events carried alongside as data.
  fetch_profile  a company's current fundamentals -- sector, size, valuation,
                 growth, margins -- the snapshot a leader screen is built on.

and the wider surface: ``fetch_quotes`` (live snapshot), ``fetch_search`` (symbol
lookup), ``fetch_timeseries`` (dated financials), ``fetch_spark`` (compact multi-
symbol series), ``fetch_options`` (option chain), ``fetch_recommendations``
(similar symbols), ``fetch_insights`` (gathered research), ``fetch_consensus``
(sell-side analyst consensus), ``fetch_screener`` (predefined screens).

Reaches Yahoo through ``curl_cffi``'s Chrome TLS impersonation, without which the
endpoints answer 429.

    >>> from finyahoo import YahooClient
    >>> with YahooClient() as yahoo:
    ...     history = yahoo.fetch_history("AAPL")
    ...     profile = yahoo.fetch_profile("AAPL")
"""

from importlib.metadata import PackageNotFoundError, version

from .client import YahooClient
from .consensus import Consensus, RatingTrend
from .errors import (
    YahooBlockedError,
    YahooError,
    YahooParseError,
    YahooRequestError,
)
from .insights import InsightReport, Insights
from .options import OptionChain, OptionContract
from .price import (
    Dividend,
    PriceBar,
    PriceHistory,
    Split,
    Timeframe,
)
from .profile import Profile
from .quote import Quote
from .recommend import Recommendation
from .screener import Screen
from .search import Search, SearchMatch, SearchNews
from .spark import Spark, SparkInterval, SparkPeriod, SparkPoint
from .timeseries import FinancialPoint, FinancialSeries

__all__ = [
    "Consensus",
    "Dividend",
    "FinancialPoint",
    "FinancialSeries",
    "InsightReport",
    "Insights",
    "OptionChain",
    "OptionContract",
    "PriceBar",
    "PriceHistory",
    "Profile",
    "Quote",
    "RatingTrend",
    "Recommendation",
    "Screen",
    "Search",
    "SearchMatch",
    "SearchNews",
    "Spark",
    "SparkInterval",
    "SparkPeriod",
    "SparkPoint",
    "Split",
    "Timeframe",
    "YahooBlockedError",
    "YahooClient",
    "YahooError",
    "YahooParseError",
    "YahooRequestError",
]

try:
    __version__ = version("finyahoo")
except PackageNotFoundError:   # running from a source tree with no install
    __version__ = "0.0.0+unknown"
