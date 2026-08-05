---
name: news
description: "Fetch recent related news for one symbol from Yahoo Finance -- each item's timestamp, source, headline, and link, newest first. Holds no logic of its own -- it calls the finyahoo package's CLI (`finyahoo news`) and shows the result to the user. Works for US stocks (AAPL), Korean tickers (005930.KS), and indices (^GSPC). Trigger phrases: news, headlines, latest news, any news on, news about, 뉴스, 소식, 헤드라인, 관련 뉴스, 관련 소식, 최신 뉴스."
---

# finyahoo — related news

Take one ticker and print recent related news -- each item's timestamp, source,
headline, and URL, newest first. Default is 4 items; `--count` requests more. The
fetching and parsing live in the finyahoo package (on PyPI); this skill is a thin wrapper
that calls its CLI and relays the result. An unknown ticker or a rate block comes back as
a one-line error -- relay it as-is. For the live price use `quote`, for fundamentals use
`profile`.

## Prerequisite

This plugin calls the `finyahoo` CLI, so the package must be installed first:

```
pipx install finyahoo        # or: pip install finyahoo
```

That puts the `finyahoo` command on PATH. No API key or login is needed.

## Running

```
finyahoo news "<SYMBOL>" [-n COUNT] [--json]
```

- Default prints up to 4 items, each a `YYYY-MM-DD HH:MM  (source) headline` line
  followed by its URL line.
- `-n` / `--count N` requests more items; `--json` emits the full records.

This is Yahoo's related-news feed **as of now** -- ordered newest first, aggregated
across publishers, so relevance and quality vary. For prices use `quote` / `history`, for
analyst targets use `consensus`.

## Procedure

1. **Get the symbol.** Find a Yahoo ticker (US `AAPL`; Korean `005930.KS` / `.KQ`;
   index `^GSPC`). If there is none, ask. Handle several requested symbols one at a time.
2. **Run.**
   ```bash
   finyahoo news MU
   ```
   Add `-n 10` for more items; `--json` for machine-readable data.
3. **Relay the result.** Show the CLI's stdout as-is -- do not drop, condense, or rewrite
   items. If the user asked about a specific event, you may point to the matching headline,
   but keep every item with its timestamp and link intact.
4. **Error handling.** When the CLI exits non-zero, relay the one-line
   `finyahoo: <message>` from stderr as-is:
   - `command not found: finyahoo` -> not installed; point the user at `pipx install finyahoo`.
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry.

   Note: an unknown or misspelled symbol does NOT error -- `news` exits 0 and returns
   unrelated general-market headlines. If a symbol is uncertain, resolve it with `match`
   first rather than trusting a clean-looking but off-topic feed.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It does not rank, verify, or analyze the news beyond Yahoo's newest-first ordering -- it
  relays the feed; the headlines are Yahoo's aggregation, not vetted.
