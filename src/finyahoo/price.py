"""Parsing Yahoo's chart response into bars and the corporate actions beside them.

Pure functions of the payload -- no network -- so every shape Yahoo emits is
testable against a saved fixture. The client in ``client.py`` is the I/O shell;
this is its functional core.

Yahoo's ``/v8/finance/chart`` answers one symbol with a parallel-array block:
``timestamp`` and, under ``indicators``, ``quote`` (open/high/low/close/volume as
columns) and ``adjclose``. A bar Yahoo has no data for is ``null`` at that index,
and the in-progress current-day bar can carry a close with no adjusted close yet;
either way it is not a settled bar, so a row is kept only when every price is
present -- dropped rather than written with a 0 that would read as a price, or a
None in a float field.

``close`` is already split-adjusted (a 50:1 split shows a continuous line, not a
cliff); ``adj_close`` is that, further adjusted for dividends. Both are carried,
because the right one depends on the question -- correlation of a dividend-payer
wants adj_close, a chart wants close -- and Yahoo gives both.

The split and dividend events ride in the same response and are carried as data,
never acted on. They are Yahoo's, and Yahoo's are not always right: it reports
Samsung Electronics splitting 50:1 twice, on 2018-05-04 and 2018-05-16, and only
the first happened. So they are stored as the two integers Yahoo states -- numerator and
denominator, not a single float that would round 1/21 away -- and left for a reader
to use or distrust. A consumer that needs verified adjustment factors should
measure them from the prices, not trust this feed.

Dates come as epoch seconds in UTC; Yahoo also gives ``meta.gmtoffset``, and a bar
is labelled by its *local* trading date, so a KST session (UTC+9) is not shifted a
day earlier by reading the timestamp as UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any

from .errors import YahooParseError
from .payload import dict_or_empty, first_dict, is_number, unwrap_result


class Timeframe(Enum):
    """A bar's period. The value is Yahoo's own ``interval`` argument."""

    DAY   = "1d"
    WEEK  = "1wk"
    MONTH = "1mo"


@dataclass(frozen=True, slots=True)
class PriceBar:
    """One daily/weekly/monthly bar.

    ``close`` is split-adjusted; ``adj_close`` is split- and dividend-adjusted.
    Prices are float and in the symbol's own currency (``meta.currency`` -- KRW for
    ``005930.KS``, USD for ``MU``); this does not convert. ``volume`` is shares, or
    ``None`` when Yahoo omits it for an otherwise-priced bar (a halted session, some
    index feeds) -- never 0, which is a real no-trade reading.
    """

    trade_date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int | None


@dataclass(frozen=True, slots=True)
class Split:
    """A share split on its ex-date, as the two integers Yahoo states.

    ``numerator``/``denominator`` is Yahoo's own form: a 50:1 split is
    ``numerator=50, denominator=1``, a 1:21 reverse split ``1``/``21``. Kept as the
    integer pair rather than a ratio so a reverse split's exact fraction survives
    (a single float rounds 1/21). This is carried metadata, not a verified fact --
    see the module docstring.
    """

    ex_date: date
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class Dividend:
    """A cash dividend on its ex-date, per share, in the symbol's currency."""

    ex_date: date
    per_share: float


@dataclass(frozen=True, slots=True)
class PriceHistory:
    """One symbol's bars and the corporate actions over the same span.

    A single response carries all three, so a single object returns them: asking
    for the bars and the events separately would fetch the symbol twice.
    ``splits`` and ``dividends`` are oldest-first like ``bars``, and may be empty.
    """

    symbol: str
    bars: tuple[PriceBar, ...]
    splits: tuple[Split, ...]
    dividends: tuple[Dividend, ...]


def parse_history(payload: str, symbol: str) -> PriceHistory:
    """Parse a chart response into ``symbol``'s bars, splits, and dividends.

    ``symbol`` is passed rather than read from the payload so the result is
    labelled by what the caller asked for, not by whatever the response echoes.

    Raises:
        YahooRequestError: the response carries an ``error`` -- a delisted or
            unknown ticker, which found no data rather than arriving malformed.
        YahooParseError: the payload is not JSON, or not the chart shape.
    """
    result = first_dict(unwrap_result(payload, "chart", "chart", symbol), "chart")
    offset = timedelta(seconds=_int_or_zero(dict_or_empty(result.get("meta")).get("gmtoffset")))
    return PriceHistory(
        symbol    = symbol,
        bars      = _parse_bars(result, offset),
        splits    = _parse_splits(result, offset),
        dividends = _parse_dividends(result, offset),
    )


def _parse_bars(result: dict[str, Any], offset: timedelta) -> tuple[PriceBar, ...]:
    timestamps = result.get("timestamp")
    if timestamps is None:
        # A valid empty window (a range with no trading days) has no timestamp
        # array; that is no bars, not a broken shape.
        return ()
    # Bind each column once and read them in parallel. Any of them being shorter
    # than `timestamps`, or missing, is a ragged payload -- caught here as a parse
    # error rather than escaping as a bare IndexError past the documented contract.
    try:
        quote = result["indicators"]["quote"][0]
        opens, highs, lows, closes, volumes = (
            quote["open"], quote["high"], quote["low"], quote["close"], quote["volume"])
        adj_closes = result["indicators"]["adjclose"][0]["adjclose"]
        rows = zip(timestamps, opens, highs, lows, closes, adj_closes, volumes, strict=True)
        bars = tuple(
            PriceBar(
                trade_date = _local_date(epoch, offset),
                open       = open_,
                high       = high,
                low        = low,
                close      = close,
                adj_close  = adj_close,
                volume     = int(volume) if is_number(volume) else None,
            )
            for epoch, open_, high, low, close, adj_close, volume in rows
            # A bar is stored only when every price is a real number. Yahoo nulls a
            # bar it has no data for, and the in-progress current-day bar can carry
            # a close with no adjusted close yet -- either way it is not a settled
            # bar. Testing for a number (not just non-None) also keeps a stray bool
            # or boxed value out of the float fields.
            if all(is_number(v) for v in (open_, high, low, close, adj_close))
        )
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise YahooParseError(f"chart result has a malformed quote block: {err}") from err
    return bars


def _parse_splits(result: dict[str, Any], offset: timedelta) -> tuple[Split, ...]:
    events = dict_or_empty(dict_or_empty(result.get("events")).get("splits"))
    try:
        splits = [
            Split(ex_date     = _local_date(event["date"], offset),
                  numerator   = int(event["numerator"]),
                  denominator = int(event["denominator"]))
            for event in events.values()
        ]
    except (KeyError, TypeError, ValueError) as err:
        raise YahooParseError(f"chart result has a malformed split event: {err}") from err
    return tuple(sorted(splits, key=lambda split: split.ex_date))


def _parse_dividends(result: dict[str, Any], offset: timedelta) -> tuple[Dividend, ...]:
    events = dict_or_empty(dict_or_empty(result.get("events")).get("dividends"))
    try:
        dividends = [
            Dividend(ex_date=_local_date(event["date"], offset), per_share=float(event["amount"]))
            for event in events.values()
        ]
    except (KeyError, TypeError, ValueError) as err:
        raise YahooParseError(f"chart result has a malformed dividend event: {err}") from err
    return tuple(sorted(dividends, key=lambda dividend: dividend.ex_date))


def _local_date(epoch: int, offset: timedelta) -> date:
    """The local trading date of a UTC epoch-second timestamp, shifted by the
    exchange's gmtoffset so a KST bar keeps its own calendar day."""
    return (datetime.fromtimestamp(epoch, tz=UTC) + offset).date()


def _int_or_zero(value: object) -> int:
    """A Yahoo ``gmtoffset`` as int, with an absent offset reading as 0 (UTC).

    An offset genuinely defaults to 0 when missing, unlike a bar's volume, where a
    missing reading is None rather than a real zero.
    """
    return int(value) if is_number(value) else 0
