---
name: history
description: "Fetch a symbol's OHLCV price history (and its split/dividend events) from Yahoo Finance. Holds no logic of its own -- it calls the pyyahoo package's CLI (`pyyahoo history`) and shows the result to the user. Works for US stocks (AAPL), Korean tickers (005930.KS), and indices (^GSPC). Trigger phrases: price history, OHLCV, stock chart data, get prices for, 시세 가져와, 주가 이력, 차트 데이터."
---

# pyyahoo — price history

Take a ticker and print its OHLCV bars (with the split and dividend events over the
same span). The fetching and parsing live in the pyyahoo package (on PyPI); this skill
is a thin wrapper that calls its CLI and relays the result. A delisted ticker, a rate
block, and the like come back from the CLI as a one-line error -- relay that message
as-is rather than throwing a stack trace at the user.

## Prerequisite

This plugin calls the `pyyahoo` CLI, so the package must be installed first:

```
pipx install pyyahoo        # or: pip install pyyahoo
```

That puts the `pyyahoo` command on PATH. No API key or login is needed -- Yahoo's
endpoints are public and the client handles the session token itself.

## Running

```
pyyahoo history "<SYMBOL>" [options]
```

Options (`pyyahoo history --help` is the source of truth):
- `--start YYYY-MM-DD` — inclusive start date (default: Yahoo's earliest bar).
- `--end YYYY-MM-DD` — inclusive end date (default: the latest bar).
- `--timeframe day|week|month` — bar size (default: day).
- `--json` — full series as JSON instead of the text summary.

The text output is a one-line summary (symbol, bar count, split/dividend counts) plus
the most recent few bars. Use `--json` when the user wants the whole series or machine-
readable data.

## Procedure

1. **Get the symbol.** Find a Yahoo ticker in the user's message (US: `AAPL`; Korean:
   `005930.KS` / `.KQ`; index: `^GSPC`). If there is none, ask. Handle several one at a time.
2. **Run.** Call the CLI. Add `--start`/`--end`/`--timeframe` only when the user asked
   for a specific window or bar size; add `--json` when they want the full series.
   ```bash
   pyyahoo history "AAPL" --start 2024-01-01
   ```
3. **Relay the result.** Show the CLI's stdout to the user. You may trim a long series,
   but keep the summary line.
4. **Error handling.** When the CLI exits non-zero, relay the one-line `pyyahoo: <message>`
   from stderr as-is. Common ones:
   - `command not found: pyyahoo` -> the package is not installed; point the user at
     `pipx install pyyahoo`.
   - `Not Found` -> a delisted or unknown ticker (Yahoo has no data for it).
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry, or
     space requests out.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It is history only -- for the current fundamentals snapshot, use the `profile` skill.
