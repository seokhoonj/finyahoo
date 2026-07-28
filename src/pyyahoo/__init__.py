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
(similar symbols), ``fetch_insights`` (gathered research), ``fetch_screener``
(predefined screens).

Reaches Yahoo through ``curl_cffi``'s Chrome TLS impersonation, without which the
endpoints answer 429.

    >>> from pyyahoo import YahooClient
    >>> with YahooClient() as yahoo:
    ...     history = yahoo.fetch_history("AAPL")
    ...     profile = yahoo.fetch_profile("AAPL")
"""

from .client import YahooClient
from .errors import (
    YahooBlockedError,
    YahooError,
    YahooParseError,
    YahooRequestError,
)
from .insights import InsightReport, Insights, parse_insights
from .options import OptionChain, OptionContract, parse_options
from .price import (
    Dividend,
    PriceBar,
    PriceHistory,
    Split,
    Timeframe,
    parse_history,
)
from .profile import Profile, parse_profile
from .quote import Quote, parse_quotes
from .recommend import Recommendation, parse_recommendations
from .screener import Screen, parse_screener
from .search import Search, SearchMatch, SearchNews, parse_search
from .spark import Spark, SparkInterval, SparkPeriod, SparkPoint, parse_spark
from .timeseries import FinancialPoint, FinancialSeries, parse_timeseries

__all__ = [
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
    "parse_history",
    "parse_insights",
    "parse_options",
    "parse_profile",
    "parse_quotes",
    "parse_recommendations",
    "parse_screener",
    "parse_search",
    "parse_spark",
    "parse_timeseries",
]
