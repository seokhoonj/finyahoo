"""Reader for Yahoo Finance's query API -- one session over several endpoints.

The client is the imperative shell over the pure parsers in the endpoint modules
(``price.py``, ``profile.py``, ``quote.py``, ...): it holds the HTTP session and
the crumb, and each ``fetch_*`` method reaches one endpoint on the same host and
hands the payload to that endpoint's parser. So it is one client with a method per
endpoint -- chart, quoteSummary, quote, search, spark, timeseries, options,
recommendations, insights, screener -- not a client per endpoint.

The one thing that makes it work: **the session impersonates Chrome's TLS
fingerprint**, through ``curl_cffi``. Yahoo blocks a client whose handshake does
not look like a browser's, and no User-Agent header fixes it -- the header is
right but the TLS handshake is a bare HTTP library's, and that is what Yahoo
reads. ``curl_cffi``'s ``impersonate="chrome"`` presents Chrome's handshake, and a
plain ``requests`` or ``urllib`` call gets 429 where this succeeds. It is the whole
reason this package has its own dependency.

Some endpoints need no authentication; others (quoteSummary, quote, options,
insights, screener) need a **crumb** -- a rotating token minted against a session
cookie. The client mints it lazily on the first such request, reuses it, and
re-mints once if Yahoo rejects it (crumbs expire).

No history floor is imposed. Yahoo simply has what it has -- US equities from 1962,
Korean from 2000, the S&P 500 index from 1927 -- and asking for more returns what
exists. Yahoo's old data is absent, not corrupt, so there is nothing to guard
against on the low end.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any, Literal
from urllib.parse import quote

from curl_cffi import requests

from .errors import YahooBlockedError, YahooRequestError
from .insights import Insights, parse_insights
from .options import OptionChain, parse_options
from .price import PriceHistory, Timeframe, parse_history
from .profile import PROFILE_MODULES, Profile, parse_profile
from .quote import Quote, parse_quotes
from .recommend import Recommendation, parse_recommendations
from .screener import Screen, parse_screener
from .search import Search, parse_search
from .spark import Spark, SparkInterval, SparkPeriod, parse_spark
from .timeseries import FinancialSeries, parse_timeseries

_HOST = "https://query2.finance.yahoo.com"
_CHART_URL = _HOST + "/v8/finance/chart/{symbol}"
_SUMMARY_URL = _HOST + "/v10/finance/quoteSummary/{symbol}"
_QUOTE_URL = _HOST + "/v7/finance/quote"
_SEARCH_URL = _HOST + "/v1/finance/search"
_SPARK_URL = _HOST + "/v8/finance/spark"
_OPTIONS_URL = _HOST + "/v7/finance/options/{symbol}"
_RECOMMEND_URL = _HOST + "/v6/finance/recommendationsbysymbol/{symbol}"
_INSIGHTS_URL = _HOST + "/ws/insights/v1/finance/insights"
_SCREENER_URL = _HOST + "/v1/finance/screener/predefined/saved"
_TIMESERIES_URL = _HOST + "/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"
_COOKIE_URL = "https://fc.yahoo.com"
_CRUMB_URL = _HOST + "/v1/test/getcrumb"

# The browser whose TLS handshake curl_cffi presents. Yahoo gates on the
# fingerprint, so this is load-bearing, not cosmetic (see the module docstring).
_IMPERSONATE: Literal["chrome"] = "chrome"

# 429 is how Yahoo refuses a client it will not serve (typically an unrecognized
# fingerprint or a rate limit). Reported, never retried through.
_BLOCKED_STATUS = 429

# 401 on a quoteSummary call means the crumb has expired; re-mint once and retry.
_STALE_CRUMB_STATUS = 401

# Sentinel end date: Yahoo clamps this to the latest available bar, so a request
# for "everything up to now" needs no clock reading.
_OPEN_END = 9999999999
_EPOCH_START = 0

# An inclusive end date is sent as the start of the next day: Yahoo filters on
# timestamp < period2, and a bar's timestamp is its session open (intraday), so a
# period2 at the end date's midnight would exclude that very day's bar.
_ONE_DAY_SECONDS = 86400

_TRANSIENT_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0
_RETRY_BACKOFF_FACTOR = 2      # each retry waits this many times the last

# How much of an unusable crumb to show in the error -- enough to see whether an
# HTML error page came back in its place, short enough not to dump the page.
_CRUMB_ERROR_PREVIEW_CHARS = 40


class YahooClient:
    """Reader for Yahoo Finance's chart, quoteSummary, and related endpoints.

    A SOURCE object: it holds the impersonating HTTP session and the crumb, and
    each method fetches from one endpoint. ``delay_seconds`` spaces consecutive
    requests; Yahoo publishes no rate limit for these endpoints, so the default is
    courtesy rather than a quota.

    Not thread-safe: the session, crumb, and pacing clock are mutable instance
    state with no locking (and ``curl_cffi`` sessions are not thread-safe), so use
    one client per thread rather than sharing an instance.
    """

    def __init__(self, *, timeout: float = 30.0, delay_seconds: float = 0.5) -> None:
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self._session: requests.Session[Any] = requests.Session(impersonate=_IMPERSONATE)
        self._crumb: str | None = None
        self._next_request_at = 0.0

    def __repr__(self) -> str:
        return f"YahooClient(delay_seconds={self.delay_seconds})"

    def close(self) -> None:
        """Close the underlying HTTP session (also called on context exit)."""
        self._session.close()

    def __enter__(self) -> YahooClient:
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def fetch_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        timeframe: Timeframe = Timeframe.DAY,
    ) -> PriceHistory:
        """Fetch ``symbol``'s bars and corporate actions in [``start``, ``end``].

        ``symbol`` is a Yahoo ticker: a US stock is bare (``MU``), a Korean one
        carries the market suffix (``005930.KS`` KOSPI, ``.KQ`` KOSDAQ), an index
        is caret-prefixed (``^GSPC``). Both bounds are inclusive and both default
        to the widest available window -- ``start`` to Yahoo's earliest bar,
        ``end`` to the latest.

        A delisted or unknown ticker raises ``YahooRequestError`` ("Not Found"),
        not an empty result, because Yahoo distinguishes the two.

        Raises:
            ValueError: ``start`` is after ``end`` (a caller bug).
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the symbol has no data.
            YahooParseError: the payload was not the chart shape.
        """
        if start is not None and end is not None and start > end:
            raise ValueError(f"start {start} is after end {end}")
        payload = self._get(_CHART_URL.format(symbol=quote(symbol, safe="")), params={
            "period1":  _EPOCH_START if start is None else _to_epoch(start),
            "period2":  _OPEN_END if end is None else _to_epoch(end) + _ONE_DAY_SECONDS,
            "interval": timeframe.value,
            "events":   "div,split",
        }).text
        return parse_history(payload, symbol)

    def fetch_profile(self, symbol: str) -> Profile:
        """Fetch ``symbol``'s current fundamentals (sector, size, valuation,
        growth, margins).

        A snapshot as of now, not history -- see ``profile.py``. Mints a crumb on
        the first call and re-mints once if Yahoo rejects a stale one.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the symbol is unknown.
            YahooParseError: the payload was not the quoteSummary shape.
        """
        url = _SUMMARY_URL.format(symbol=quote(symbol, safe=""))
        return parse_profile(self._get_crumbed(url, {"modules": ",".join(PROFILE_MODULES)}), symbol)

    def fetch_quotes(self, symbols: Sequence[str]) -> tuple[Quote, ...]:
        """Fetch a live snapshot for each of ``symbols`` in one request.

        The real-time price, day range, and trailing multiples as of now -- not
        history. Returns one ``Quote`` per symbol, in Yahoo's order.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed.
            YahooParseError: the payload was not the quoteResponse shape.
        """
        text = self._get_crumbed(_QUOTE_URL, {"symbols": ",".join(symbols)})
        return parse_quotes(text)

    def fetch_search(self, query: str, *, quotes_count: int = 6,
                     news_count: int = 4) -> Search:
        """Look up securities (and related news) matching a free-text ``query``.

        The ranked ``matches`` are what identify and route a symbol; ``news`` is a
        convenience Yahoo bundles in. Needs no crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed.
            YahooParseError: the payload was not the search shape.
        """
        text = self._get(_SEARCH_URL, params={
            "q": query, "quotesCount": quotes_count, "newsCount": news_count,
        }).text
        return parse_search(text, query)

    def fetch_spark(self, symbols: Sequence[str], *, period: SparkPeriod = "1mo",
                    interval: SparkInterval = "1d") -> tuple[Spark, ...]:
        """Fetch a compact close series for each of ``symbols`` in one request.

        Close-only, for a sparkline; for full OHLCV and events fetch one symbol
        through ``fetch_history``. ``period`` is the lookback window (Yahoo's own
        ``range`` argument -- ``1mo``/``1y``/``ytd``...), ``interval`` the bar size
        within it. Needs no crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed.
            YahooParseError: the payload was not the spark shape.
        """
        text = self._get(_SPARK_URL, params={
            "symbols": ",".join(symbols), "range": period, "interval": interval,
        }).text
        return parse_spark(text)

    def fetch_timeseries(self, symbol: str, types: Sequence[str], *,
                         start: date | None = None,
                         end: date | None = None) -> tuple[FinancialSeries, ...]:
        """Fetch dated financial line items for ``symbol``.

        ``types`` are Yahoo's own line-item names (``annualTotalRevenue``,
        ``quarterlyNetIncome``, ...); one request may ask several and one
        ``FinancialSeries`` comes back per type. Where ``fetch_profile`` is a
        snapshot, this is the history. Needs no crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed.
            YahooParseError: the payload was not the timeseries shape.
        """
        # Unlike the chart endpoint, timeseries rejects the 9999999999 open-end
        # sentinel (it reads as out of range and returns zero points), so "up to
        # now" is the current time, not a sentinel.
        text = self._get(_TIMESERIES_URL.format(symbol=quote(symbol, safe="")), params={
            "type":          ",".join(types),
            "period1":       _EPOCH_START if start is None else _to_epoch(start),
            "period2":       int(time.time()) if end is None else _to_epoch(end) + _ONE_DAY_SECONDS,
            "merge":         "false",
            "padTimeSeries": "true",
        }).text
        return parse_timeseries(text, symbol)

    def fetch_options(self, symbol: str, *, expiration: date | None = None) -> OptionChain:
        """Fetch ``symbol``'s option chain for one expiration.

        With no ``expiration`` Yahoo returns the nearest one; the full list of
        available expirations rides on the result either way. Needs a crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the symbol is unknown.
            YahooParseError: the payload was not the optionChain shape.
        """
        url = _OPTIONS_URL.format(symbol=quote(symbol, safe=""))
        params = {} if expiration is None else {"date": _to_epoch(expiration)}
        return parse_options(self._get_crumbed(url, params))

    def fetch_recommendations(self, symbol: str) -> tuple[Recommendation, ...]:
        """Fetch the symbols Yahoo considers similar to ``symbol``.

        Needs no crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the symbol is unknown.
            YahooParseError: the payload was not the expected shape.
        """
        text = self._get(_RECOMMEND_URL.format(symbol=quote(symbol, safe=""))).text
        return parse_recommendations(text, symbol)

    def fetch_insights(self, symbol: str) -> Insights:
        """Fetch gathered third-party research on ``symbol``.

        An analyst target and rating, a valuation call, technical levels and
        outlooks, and research reports -- the providers' figures, carried as data.
        Needs a crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the symbol is unknown.
            YahooParseError: the payload was not the insights shape.
        """
        return parse_insights(self._get_crumbed(_INSIGHTS_URL, {"symbol": symbol}), symbol)

    def fetch_screener(self, screen_id: str, *, count: int = 25) -> Screen:
        """Run one of Yahoo's predefined screens (``most_actives``,
        ``day_gainers``, ``undervalued_growth_stocks``, ...).

        ``count`` bounds the page returned; the screen's full match ``total`` rides
        on the result. Members come back as ``Quote``s. Needs a crumb.

        Raises:
            YahooBlockedError: Yahoo is refusing this client (429) -- back off.
            YahooRequestError: the request failed, or the screen id is unknown.
            YahooParseError: the payload was not the screener shape.
        """
        text = self._get_crumbed(_SCREENER_URL, {"scrIds": screen_id, "count": count})
        return parse_screener(text)

    def _get_crumbed(self, url: str, params: Mapping[str, str | int]) -> str:
        """Fetch a crumb-gated endpoint's body, minting the crumb as needed.

        quoteSummary, quote, options, insights, and screener require a crumb. The
        first call tolerates a 401 (a stale crumb) as a return rather than an error;
        a re-mint then carries one retry, and a second 401 is a real failure the
        retry raises.
        """
        response = self._get(url, params={**params, "crumb": self._ensure_crumb()},
                             allow_stale_crumb=True)
        if response.status_code == _STALE_CRUMB_STATUS:
            # The crumb rotated out from under us; mint a fresh one and try once
            # more before giving up.
            response = self._get(url, params={**params, "crumb": self._ensure_crumb(force=True)})
        return response.text

    def _ensure_crumb(self, *, force: bool = False) -> str:
        """The session crumb, minting it if absent (or ``force``d after a reject).

        Minting is two steps: a request that sets the session cookie, then the
        crumb endpoint that reads it. The cookie request answers 404 and that is
        expected -- the cookie, not the body, is the point.
        """
        if self._crumb is not None and not force:
            return self._crumb
        self._request(_COOKIE_URL)                    # 404 is fine; sets the cookie
        crumb = self._request(_CRUMB_URL).text.strip()
        if not crumb or "<" in crumb:
            raise YahooRequestError(
                f"Yahoo returned no usable crumb: {crumb[:_CRUMB_ERROR_PREVIEW_CHARS]!r}")
        self._crumb = crumb
        return crumb

    def _get(self, url: str, *, params: dict[str, str | int] | None = None,
             allow_stale_crumb: bool = False) -> requests.Response:
        """Fetch one URL, returning the response for the caller to read.

        A 401 is returned rather than raised only when ``allow_stale_crumb`` -- the
        profile path's first call opts in, so its re-mint can handle it. It
        defaults off: the chart endpoint carries no crumb, so a 401 there is a real
        failure, not something to hand on as a normal response.
        """
        response = self._request(url, params=params)
        if response.status_code == _STALE_CRUMB_STATUS and allow_stale_crumb:
            return response
        if response.status_code >= 400:
            raise YahooRequestError(f"GET {url} returned {response.status_code}")
        return response

    def _request(self, url: str, *, params: dict[str, str | int] | None = None) -> requests.Response:
        """One paced, retrying HTTP GET.

        A 5xx or a timeout is a glitch worth retrying; a 429 is an answer, and this
        client does not knock again. Everything else (404, 401) is returned for the
        caller to interpret -- a 404 crumb-cookie request is normal, a 401 is a
        stale crumb.
        """
        last_error: Exception | None = None
        for attempt in range(_TRANSIENT_RETRIES):
            self._wait_for_next_slot()
            try:
                response: requests.Response = self._session.get(
                    url, params=params, timeout=self.timeout)
            except requests.RequestsError as err:
                last_error = err
            else:
                if response.status_code == _BLOCKED_STATUS:
                    raise YahooBlockedError(
                        f"Yahoo returned {_BLOCKED_STATUS} for {url}; it is refusing "
                        f"this client (TLS fingerprint or rate limit)")
                if response.status_code < 500:
                    return response
                last_error = YahooRequestError(f"{response.status_code} from {url}")
            if attempt + 1 < _TRANSIENT_RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS * _RETRY_BACKOFF_FACTOR ** attempt)
        raise YahooRequestError(f"GET {url} failed after {_TRANSIENT_RETRIES} "
                                f"attempts: {last_error}") from last_error

    def _wait_for_next_slot(self) -> None:
        now = time.monotonic()
        if now < self._next_request_at:
            time.sleep(self._next_request_at - now)
        self._next_request_at = time.monotonic() + self.delay_seconds


def _to_epoch(day: date) -> int:
    """A date as UTC epoch seconds -- Yahoo's ``period1``/``period2`` unit."""
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
