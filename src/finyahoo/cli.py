"""Command-line shell over ``YahooClient`` -- ``finyahoo history`` / ``profile`` / ``quote``.

The shell over the shell: it parses ``argv``, runs one library read, and renders the
typed result as text (or ``--json``). All data-shape knowledge stays in the library --
this only formats what the library returns -- and it is stdlib-only, so the package's
single runtime dependency (``curl_cffi``) is not widened by having a CLI.

    $ finyahoo history AAPL --start 2024-01-01
    $ finyahoo profile ^GSPC --json
    $ finyahoo quote MU NVDA 005930.KS
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
        "quote", help="live price snapshot for one or more symbols")
    quote.add_argument("symbols", nargs="+",
                       help="one or more Yahoo tickers (MU NVDA 005930.KS)")
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
        quotes = yahoo.fetch_quotes(args.symbols)
    print(_quotes_to_json(quotes) if args.json else _render_quotes(quotes))
    return 0


def _to_json(result: PriceHistory | Profile) -> str:
    """A frozen result dataclass as indented JSON, dates rendered as ISO strings."""
    return json.dumps(dataclasses.asdict(result), default=_json_default,
                      ensure_ascii=False, indent=2)


def _quotes_to_json(quotes: tuple[Quote, ...]) -> str:
    """A quote per symbol as a JSON array, datetimes rendered as ISO strings."""
    return json.dumps([dataclasses.asdict(quote) for quote in quotes],
                      default=_json_default, ensure_ascii=False, indent=2)


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


def _render_profile(profile: Profile) -> str:
    """Every populated field as aligned ``name  value``; absent (None) fields are skipped
    so an index -- which carries only a few -- does not print a wall of dashes."""
    return _aligned_fields(profile)


def _aligned_fields(record: Profile | Quote) -> str:
    """A dataclass's populated fields as aligned ``name  value`` lines, one per line;
    None fields are skipped so a sparse record does not print a wall of dashes."""
    present = [(field.name, getattr(record, field.name))
               for field in dataclasses.fields(record)
               if getattr(record, field.name) is not None]
    # symbol is always present, so `present` is never empty; default=0 keeps the
    # width computation safe rather than leaning on that invariant.
    width = max((len(name) for name, _ in present), default=0)
    return "\n".join(f"{name:<{width}}  {value}" for name, value in present)


def _render_quotes(quotes: tuple[Quote, ...]) -> str:
    """One symbol -> its full snapshot as aligned fields; many -> a watchlist table.

    The layout follows the count: a single quote is read in depth (every populated
    field, like a profile), while a basket is scanned across (price, change, and
    market state per row), which stays narrow no matter how many symbols.
    """
    if not quotes:
        return "  (no quotes for the requested symbols)"
    if len(quotes) == 1:
        return _aligned_fields(quotes[0])
    return _render_quote_table(quotes)


def _render_quote_table(quotes: tuple[Quote, ...]) -> str:
    """One row per symbol -- symbol, price, change, market state -- with each column
    sized to its widest cell. The full per-symbol detail is the single-symbol view or
    ``--json``; a None price or change renders as a dash, not a zero."""
    header = ("SYMBOL", "PRICE", "CHG%", "STATE")
    rows = [header]
    for quote in quotes:
        price = "-" if quote.price is None else f"{quote.price:,.2f}"
        change = "-" if quote.change_percent is None else f"{quote.change_percent:+.2f}%"
        rows.append((quote.symbol, price, change, quote.market_state or "-"))
    width = [max(len(row[col]) for row in rows) for col in range(len(header))]
    return "\n".join(
        f"{row[0]:<{width[0]}}  {row[1]:>{width[1]}}  "
        f"{row[2]:>{width[2]}}  {row[3]:<{width[3]}}"
        for row in rows)


if __name__ == "__main__":
    raise SystemExit(main())
