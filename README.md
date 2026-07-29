# finyahoo

[![check](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/finyahoo)](https://pypi.org/project/finyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/finyahoo)](https://pypi.org/project/finyahoo/)
[![License](https://img.shields.io/pypi/l/finyahoo)](https://github.com/seokhoonj/finyahoo/blob/main/LICENSE)

**English** | [한국어](README.ko.md)

Read prices and fundamentals from Yahoo Finance.

Daily, weekly, and monthly open/high/low/close and volume, the adjusted close,
dividends and splits, company fundamentals (sector, market cap, valuation, ...),
live quotes, options, screeners, and news.

## 1. Install

```sh
pip install finyahoo
```

Requires Python 3.11+.

## 2. Quickstart

```python
from finyahoo import YahooClient

yahoo = YahooClient()
history = yahoo.fetch_history("AAPL", start="2020-01-01")
latest = history.bars[-1]
print(latest.trade_date, latest.close, latest.adj_close, latest.volume)
print(len(history.splits), "splits,", len(history.dividends), "dividends")

profile = yahoo.fetch_profile("AAPL")
print(profile.sector, profile.market_cap, profile.trailing_pe)
```

Symbols are Yahoo tickers: a US stock is bare (`AAPL`), a Korean one carries the
market suffix (`005930.KS` KOSPI, `.KQ` KOSDAQ), an index is caret-prefixed
(`^GSPC`). A delisted or unknown ticker raises `YahooRequestError`, not an empty
result.

## 3. Client options

`YahooClient` takes two optional keyword-only settings:

| argument | default | what it does |
|---|---|---|
| `timeout` | `30.0` | per-request timeout, in seconds |
| `delay_seconds` | `0.5` | pause between consecutive requests; raise it if reading many symbols in a row runs into rate limits |

```python
yahoo = YahooClient(timeout=10, delay_seconds=1.0)
```

## 4. Methods

| method | returns |
|---|---|
| `fetch_history(symbol, *, start, end, timeframe)` | `PriceHistory` — OHLCV bars + `Split`/`Dividend` events |
| `fetch_profile(symbol)` | `Profile` — current fundamentals snapshot |
| `fetch_quotes(symbols)` | `tuple[Quote]` — live snapshot per symbol |
| `fetch_search(query, *, quotes_count, news_count)` | `Search` — symbol matches + related news |
| `fetch_timeseries(symbol, metric_types, *, start, end)` | `tuple[FinancialSeries]` — dated financial line items |
| `fetch_spark(symbols, *, period, interval)` | `tuple[Spark]` — compact close series per symbol |
| `fetch_options(symbol, *, expiration)` | `OptionChain` — calls/puts for one expiration |
| `fetch_recommendations(symbol)` | `tuple[Recommendation]` — similar symbols |
| `fetch_insights(symbol)` | `Insights` — analyst target, valuation, outlooks, reports |
| `fetch_screener(screen_id, *, page_size)` | `Screen` — a predefined screen's members (as `Quote`s) |

### The two core reads

- `fetch_history` — a `PriceHistory`: OHLCV bars (`close` split-adjusted,
  `adj_close` also dividend-adjusted), plus the `Split` and `Dividend` events that
  fell in the same span, carried as data. Both bounds inclusive; both default to
  the widest window Yahoo has.
- `fetch_profile` — a `Profile`: the company's current fundamentals (sector, size,
  valuation, growth, margins). A snapshot as of now, not history; every numeric
  field is optional and a missing one is `None`, never `0`.

## 5. DataFrames

Every result record is a dataclass, so pandas or polars tabulates it directly:

```python
import pandas as pd
prices = pd.DataFrame(history.bars).set_index("trade_date")
```

```python
import polars as pl
prices = pl.DataFrame(history.bars)
```

The same works for `history.splits`, `history.dividends`, a screen's `members`, or a
`fetch_quotes(...)` result.

## 6. Command line

Installing the package puts a `finyahoo` command on PATH (also `python -m finyahoo`):

```sh
finyahoo history AAPL --start 2024-01-01  # OHLCV bars + split/dividend events
finyahoo history ^GSPC --timeframe week   # weekly bars for an index
finyahoo profile AAPL                     # current fundamentals
finyahoo profile 005930.KS --json         # full snapshot as JSON
```

Both subcommands print a readable summary by default and the full result with
`--json`; `finyahoo history --help` / `finyahoo profile --help` list the flags.

## 7. Use it from an AI coding agent

This repo doubles as a plugin marketplace for Claude Code and Codex, exposing
`history` and `profile` as skills that shell out to the `finyahoo` command — so
install the package first (above); no key or login is involved.

### 7.1. Claude Code

```
/plugin marketplace add seokhoonj/finyahoo
/plugin install finyahoo@finyahoo
```

Then ask in plain words ("show AAPL's profile"), or invoke a skill explicitly —
`/finyahoo:history ^GSPC`, `/finyahoo:profile AAPL`.

### 7.2. Codex

```
codex plugin marketplace add seokhoonj/finyahoo
codex plugin add finyahoo@finyahoo
```

The `history` / `profile` skills trigger on a symbol, or run `finyahoo history <symbol>`
directly.

Prefer no plugin? Symlink a skill into your skills directory and call it bare (`/history`):

```sh
ln -s "$PWD/plugins/finyahoo/skills/history" ~/.claude/skills/history
```

## 8. License

MIT
