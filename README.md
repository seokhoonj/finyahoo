# finyahoo

[![check](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/finyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/finyahoo)](https://pypi.org/project/finyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/finyahoo)](https://pypi.org/project/finyahoo/)
[![License](https://img.shields.io/pypi/l/finyahoo)](https://github.com/seokhoonj/finyahoo/blob/main/LICENSE)

**English** | [한국어](README.ko.md)

Read prices and fundamentals from Yahoo Finance.

Daily, weekly, and monthly open/high/low/close and volume, the adjusted close,
dividends and splits, company fundamentals (sector, market cap, valuation, ...),
the sell-side analyst consensus, live quotes, options, screeners, and news.

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
| `fetch_profile(symbol)` | `Profile` — current fundamentals snapshot for one symbol |
| `fetch_quotes(symbols)` | `tuple[Quote]` — live price snapshot per symbol |
| `fetch_search(query, *, quotes_count, news_count)` | `Search` — symbol matches + related news |
| `fetch_timeseries(symbol, metric_types, *, start, end)` | `tuple[FinancialSeries]` — dated financial line items |
| `fetch_spark(symbols, *, period, interval)` | `tuple[Spark]` — compact close series per symbol |
| `fetch_options(symbol, *, expiration)` | `OptionChain` — calls/puts for one expiration |
| `fetch_recommendations(symbol)` | `tuple[Recommendation]` — similar symbols |
| `fetch_insights(symbol)` | `Insights` — a third-party (Trading Central) target and rating, valuation, outlooks, reports |
| `fetch_consensus(symbol)` | `Consensus` — the sell-side target range, mean rating, and monthly rating trend |
| `fetch_screener(screen_id, *, page_size)` | `Screen` — a predefined screen's members (as `Quote`s) |

### The two core reads

- `fetch_history` — a `PriceHistory`: OHLCV bars (`close` split-adjusted,
  `adj_close` also dividend-adjusted), plus the `Split` and `Dividend` events that
  fell in the same span, carried as data. Both bounds inclusive; both default to
  the widest window Yahoo has.
- `fetch_profile` — a `Profile`: one symbol's fundamentals (sector, size, valuation,
  growth, margins). A snapshot as of now, not history; every numeric field is
  optional and a missing one is `None`, never `0`. The analyst view is its own read,
  `fetch_consensus`.

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
finyahoo quote MU                         # live price snapshot for one symbol
finyahoo news MSFT                        # related news headlines for one symbol
finyahoo match Microsoft                  # Yahoo symbols matching a name or ticker
```

Each subcommand prints a readable summary by default and the full result with `--json`;
`--help` on any of them (`finyahoo quote --help`) lists the flags. `quote` takes one
symbol and prints its live price snapshot; `profile` prints that symbol's fundamentals;
`news` lists a symbol's related headlines and `match` resolves a name or ticker to Yahoo
symbols (both take `-n/--count`).

### Example output

`finyahoo history AAPL` -- a one-line summary then the most recent bars:

```
AAPL  11498 bars  (5 splits, 91 dividends)
  2026-07-23  close     321.6600  adj     321.6600  vol 40,840,800
  2026-07-24  close     333.0200  adj     333.0200  vol 47,489,400
  2026-07-27  close     336.9100  adj     336.9100  vol 49,604,300
  2026-07-28  close     340.0800  adj     340.0800  vol 51,859,000
  2026-07-29  close     338.1900  adj     338.1900  vol 55,929,000
```

`finyahoo profile AAPL` -- the company fundamentals:

```
symbol               AAPL
name                 Apple Inc.
sector               Technology
industry             Consumer Electronics
currency             USD
market_cap           4967117094912
shares_outstanding   14687356000
trailing_pe          40.99273
forward_pe           35.059658
price_to_book        46.58264
trailing_eps         8.25
revenue_growth       0.166
earnings_growth      0.218
profit_margin        0.27152002
operating_margin     0.32275
return_on_equity     1.4147099
fifty_two_week_high  344.57
fifty_two_week_low   201.5
beta                 1.097
```

`finyahoo consensus AAPL` -- the sell-side analyst view (target range, rating, and the recent rating trend):

```
symbol               AAPL
target_high_price    400.0
target_low_price     215.0
target_mean_price    323.28195
target_median_price  330.0
recommendation_mean  2.04348
recommendation       buy
analyst_count        41
    0m  strong_buy 6  buy 22  hold 14  sell 2  strong_sell 2
   -1m  strong_buy 6  buy 22  hold 16  sell 1  strong_sell 2
   -2m  strong_buy 7  buy 23  hold 15  sell 1  strong_sell 2
```

`finyahoo quote AAPL` -- the live price snapshot:

```
symbol                     AAPL
name                       Apple Inc.
quote_type                 EQUITY
exchange                   NasdaqGS
currency                   USD
market_state               PRE
price                      338.19
previous_close             340.08
change                     -1.88998
change_percent             -0.555747
day_open                   339.69
day_high                   344.5699
day_low                    337.3501
volume                     48852885
market_time                2026-07-29 20:00:01+00:00
pre_market_price           336.21
pre_market_change          -1.980011
pre_market_change_percent  -0.58547294
pre_market_time            2026-07-30 13:20:11+00:00
fifty_day_average          308.5888
two_hundred_day_average    277.21344
```

`finyahoo news MSFT` -- related headlines, most recent first (`-n` caps how many):

```
2026-07-30 17:30  (Yahoo Finance Video) Meta's & Microsoft's massive AI spending: Why only one is getting rewarded
  https://finance.yahoo.com/video/metas-microsofts-massive-ai-spending-173000471.html
2026-07-30 17:29  (MT Newswires) OpenAI Reducing Price of GPT-5.6 Luna Model by 80%
  https://finance.yahoo.com/technology/ai/articles/openai-reducing-price-gpt-5-172908415.html
2026-07-30 17:28  (MT Newswires) Sector Update: Tech Stocks Sharply Higher Thursday Afternoon
  https://finance.yahoo.com/markets/stocks/articles/sector-tech-stocks-sharply-higher-172836223.html
```

`finyahoo match Microsoft` -- the Yahoo symbols a name or ticker resolves to, ranked:

```
MSFT       EQUITY          NASDAQ     Technology  Microsoft Corporation
MSF.DE     EQUITY          XETRA      Technology  MICROSOFT CORP.               R
MSF.F      EQUITY          Frankfurt  Technology  MICROSOFT CORP.               R
MSFTX-USD  CRYPTOCURRENCY  CCC        None        Microsoft tokenized stock (xStock) USD
MSFT34.SA  EQUITY          São Paulo  Technology  MICROSOFT   DRN
MSFT01.BK  EQUITY          SET        Technology  MSFT01_DR MSFT#BLS
```

## 7. Use it from an AI coding agent

This repo doubles as a plugin marketplace for Claude Code and Codex, exposing
`history`, `profile`, and `quote` as skills that shell out to the `finyahoo` command —
so install the package first (above); no key or login is involved.

### 7.1. Claude Code

```
/plugin marketplace add seokhoonj/finyahoo
/plugin install finyahoo@finyahoo
```

Then ask in plain words ("show AAPL's profile", "what's MU trading at?"), or invoke a
skill explicitly — `/finyahoo:history ^GSPC`, `/finyahoo:profile AAPL`,
`/finyahoo:quote MU`.

### 7.2. Codex

```
codex plugin marketplace add seokhoonj/finyahoo
codex plugin add finyahoo@finyahoo
```

The `history` / `profile` / `quote` skills trigger on a symbol, or run
`finyahoo quote <symbol>` directly.

Prefer no plugin? Symlink a skill into your skills directory and call it bare (`/history`):

```sh
ln -s "$PWD/plugins/finyahoo/skills/history" ~/.claude/skills/history
```

## 8. License

MIT
