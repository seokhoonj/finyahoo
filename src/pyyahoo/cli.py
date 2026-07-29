"""Command-line shell over ``YahooClient`` -- ``pyyahoo history`` / ``pyyahoo profile``.

The shell over the shell: it parses ``argv``, runs one library read, and renders the
typed result as text (or ``--json``). All data-shape knowledge stays in the library --
this only formats what the library returns -- and it is stdlib-only, so the package's
single runtime dependency (``curl_cffi``) is not widened by having a CLI.

    $ pyyahoo history AAPL --start 2024-01-01
    $ pyyahoo profile ^GSPC --json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date

from .client import YahooClient
from .errors import YahooError
from .price import PriceHistory, Timeframe
from .profile import Profile

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
    ``pyyahoo: <message>`` to stderr and returns 1, so a shell caller sees a clean
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
        print(f"pyyahoo: {err}", file=sys.stderr)
        return 1


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyyahoo", description="Read Yahoo Finance from the command line.")
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


def _to_json(result: PriceHistory | Profile) -> str:
    """A frozen result dataclass as indented JSON, dates rendered as ISO strings."""
    return json.dumps(dataclasses.asdict(result), default=_json_default,
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


def _render_profile(profile: Profile) -> str:
    """Every populated field as aligned ``name: value``; absent (None) fields are skipped
    so an index -- which carries only a few -- does not print a wall of dashes."""
    present = [(field.name, getattr(profile, field.name))
               for field in dataclasses.fields(profile)
               if getattr(profile, field.name) is not None]
    # symbol is always present, so `present` is never empty; default=0 keeps the
    # width computation safe rather than leaning on that invariant.
    width = max((len(name) for name, _ in present), default=0)
    return "\n".join(f"{name:<{width}}  {value}" for name, value in present)


if __name__ == "__main__":
    raise SystemExit(main())
