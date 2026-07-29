# pyyahoo

[![check](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml/badge.svg)](https://github.com/seokhoonj/pyyahoo/actions/workflows/check.yml)
[![PyPI](https://img.shields.io/pypi/v/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![Python](https://img.shields.io/pypi/pyversions/pyyahoo)](https://pypi.org/project/pyyahoo/)
[![License](https://img.shields.io/pypi/l/pyyahoo)](https://github.com/seokhoonj/pyyahoo/blob/main/LICENSE)

**English** | [한국어](README.ko.md)

Read prices and fundamentals from Yahoo Finance through one typed client.

OHLCV history, live quotes, fundamentals, options, and screeners — one client
reaches them all, each returned as a typed result.

```python
from datetime import date
from pyyahoo import YahooClient

with YahooClient() as yahoo:
    history = yahoo.fetch_history("AAPL", start=date(2020, 1, 1))
    print(history.bars[-1])        # PriceBar(trade_date=..., close=..., adj_close=..., volume=...)
    print(history.splits)          # (Split(ex_date=..., numerator=..., denominator=...), ...)

    profile = yahoo.fetch_profile("AAPL")
    print(profile.sector, profile.market_cap, profile.trailing_pe)
```

## Methods

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

Symbols are Yahoo tickers: a US stock is bare (`AAPL`), a Korean one carries the
market suffix (`005930.KS` KOSPI, `.KQ` KOSDAQ), an index is caret-prefixed
(`^GSPC`). A delisted or unknown ticker raises `YahooRequestError`, not an empty
result.

## Install

```sh
pip install pyyahoo
```

Requires Python 3.11+.

## License

MIT
