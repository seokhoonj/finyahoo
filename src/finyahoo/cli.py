"""Command-line shell over ``YahooClient`` -- ``finyahoo history`` / ``profile`` / ``quote``.

The shell over the shell: it parses ``argv``, runs one library read, and renders the
typed result as text (or ``--json``). All data-shape knowledge stays in the library --
this only formats what the library returns -- and it is stdlib-only, so the package's
single runtime dependency (``curl_cffi``) is not widened by having a CLI.

    $ finyahoo history AAPL --start 2024-01-01
    $ finyahoo profile ^GSPC --json
    $ finyahoo quote MU
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date

from . import __version__
from .client import YahooClient
from .errors import YahooError
from .price import PriceHistory, Timeframe
from .profile import Profile
from .quote import Quote

# The CLI's --timeframe words, mapped to the library enum. Kept as words so the flag
# reads (day/week/month), not Yahoo's raw 1d/1wk/1mo.
_TIMEFRAMES = {"day": Timeframe.DAY, "week": Timeframe.WEEK, "month": Timeframe.MONTH}

# How many of the most recent bars the text view prints; the full series is always
# available with --json.
_RECENT_BARS = 5


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv``, run one read, and return a process exit code.

    A domain failure -- an unknown symbol, a 429 block, a shape that drifted, or an
    invalid date range (``start`` after ``end``) -- is printed as a one-line
    ``finyahoo: <message>`` to stderr and returns 1, so a shell caller sees a clean
    error rather than a traceback. Argparse handles a bad flag or a missing
    subcommand itself (exit 2).
    """
    args = _make_parser().parse_args(argv)
    run: Callable[[argparse.Namespace], int] = args.run
    try:
        return run(args)
    # YahooError is every domain failure; ValueError is the client's one documented
    # caller-bug signal (start > end). The renderers are empty-safe, so no other
    # ValueError reaches here to be misclassified as a domain failure.
    except (YahooError, ValueError) as err:
        print(f"finyahoo: {err}", file=sys.stderr)
        return 1


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finyahoo", description="Read Yahoo Finance from the command line.")
    parser.add_argument("--version", action="version", version=f"finyahoo {__version__}")
    commands = parser.add_subparsers(required=True)

    history = commands.add_parser(
        "history", help="OHLCV bars and corporate actions for one symbol")
    history.add_argument("symbol", help="a Yahoo ticker (AAPL, 005930.KS, ^GSPC)")
    history.add_argument("--start", type=date.fromisoformat, default=None,
                         help="inclusive start date, YYYY-MM-DD (default: earliest)")
    history.add_argument("--end", type=date.fromisoformat, default=None,
                         help="inclusive end date, YYYY-MM-DD (default: latest)")
    history.add_argument("--timeframe", choices=tuple(_TIMEFRAMES), default="day",
                         help="bar size (default: day)")
    history.add_argument("--json", action="store_true", help="emit JSON instead of text")
    history.set_defaults(run=_run_history)

    profile = commands.add_parser(
        "profile", help="current fundamentals snapshot for one symbol")
    profile.add_argument("symbol", help="a Yahoo ticker (AAPL, 005930.KS, ^GSPC)")
    profile.add_argument("--json", action="store_true", help="emit JSON instead of text")
    profile.set_defaults(run=_run_profile)

    quote = commands.add_parser(
        "quote", help="live price snapshot for one symbol")
    quote.add_argument("symbol", help="a Yahoo ticker (AAPL, 005930.KS, ^GSPC)")
    quote.add_argument("--json", action="store_true", help="emit JSON instead of text")
    quote.set_defaults(run=_run_quote)

    return parser


def _run_history(args: argparse.Namespace) -> int:
    with YahooClient() as yahoo:
        history = yahoo.fetch_history(
            args.symbol, start=args.start, end=args.end,
            timeframe=_TIMEFRAMES[args.timeframe])
    print(_to_json(history) if args.json else _render_history(history))
    return 0


def _run_profile(args: argparse.Namespace) -> int:
    with YahooClient() as yahoo:
        profile = yahoo.fetch_profile(args.symbol)
    print(_to_json(profile) if args.json else _render_profile(profile))
    return 0


def _run_quote(args: argparse.Namespace) -> int:
    with YahooClient() as yahoo:
        quotes = yahoo.fetch_quotes([args.symbol])
    # /v7 answers an unknown symbol with an empty list (not an error), so a lone
    # missing symbol is reported here rather than crashing on quotes[0].
    if not quotes:
        print(f"finyahoo: no quote for {args.symbol}", file=sys.stderr)
        return 1
    quote = quotes[0]
    print(_quote_to_json(quote) if args.json else _render_quote(quote))
    return 0


def _to_json(result: PriceHistory | Profile) -> str:
    """A frozen result dataclass as indented JSON, dates rendered as ISO strings."""
    return json.dumps(dataclasses.asdict(result), default=_json_default,
                      ensure_ascii=False, indent=2)


def _quote_to_json(quote: Quote) -> str:
    """One quote as indented JSON -- the full record (every field, valuation included),
    datetimes rendered as ISO strings."""
    return json.dumps(dataclasses.asdict(quote), default=_json_default,
                      ensure_ascii=False, indent=2)


def _json_default(value: object) -> str:
    """Serialize a value json.dumps cannot: a date (or its datetime subclass) as ISO.

    Explicit rather than a blanket ``str``, so a field of some new, genuinely
    unserializable type fails loudly here instead of being stringified into whatever
    ``str()`` happens to yield.
    """
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON-serializable")


def _render_history(history: PriceHistory) -> str:
    """A one-line summary, then the most recent bars (oldest-first within the tail)."""
    head = (f"{history.symbol}  {len(history.bars)} bars"
            f"  ({len(history.splits)} splits, {len(history.dividends)} dividends)")
    if not history.bars:
        return f"{head}\n  (no bars in range)"
    lines = [head]
    for bar in history.bars[-_RECENT_BARS:]:
        volume = "-" if bar.volume is None else f"{bar.volume:,}"
        lines.append(f"  {bar.trade_date}  close {bar.close:>12,.4f}"
                     f"  adj {bar.adj_close:>12,.4f}  vol {volume}")
    return "\n".join(lines)


# The fields the quote text view prints, in order -- the live snapshot only. The
# /v7 record also carries valuation (market cap, trailing/forward PE, ...); those are
# the profile's view, so the text quote omits them, and --json keeps the full record.
_QUOTE_VIEW_FIELDS = (
    "symbol", "name", "quote_type", "exchange", "currency", "market_state",
    "price", "previous_close", "change", "change_percent",
    "day_open", "day_high", "day_low", "volume", "market_time",
    "pre_market_price", "pre_market_change", "pre_market_change_percent", "pre_market_time",
    "post_market_price", "post_market_change", "post_market_change_percent", "post_market_time",
    "fifty_day_average", "two_hundred_day_average",
)


def _render_profile(profile: Profile) -> str:
    """Every populated field as aligned ``name  value``; absent (None) fields are skipped
    so an index -- which carries only a few -- does not print a wall of dashes."""
    pairs = [(field.name, getattr(profile, field.name))
             for field in dataclasses.fields(profile)
             if getattr(profile, field.name) is not None]
    return _aligned(pairs)


def _render_quote(quote: Quote) -> str:
    """The live snapshot as aligned ``name  value`` lines -- price, the day's range,
    market state, and the pre/post-market snapshot -- for one symbol; absent fields are
    skipped. The valuation the record also carries is the profile's view and stays in
    ``--json``."""
    pairs = [(name, getattr(quote, name)) for name in _QUOTE_VIEW_FIELDS
             if getattr(quote, name) is not None]
    return _aligned(pairs)


def _aligned(pairs: list[tuple[str, object]]) -> str:
    """Name/value pairs as aligned ``name  value`` lines, the name column sized to the
    widest name. ``default=0`` keeps an empty ``pairs`` (never reached in practice --
    symbol is always present) from failing the width computation."""
    width = max((len(name) for name, _ in pairs), default=0)
    return "\n".join(f"{name:<{width}}  {value}" for name, value in pairs)


if __name__ == "__main__":
    raise SystemExit(main())
