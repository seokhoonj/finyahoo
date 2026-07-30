---
name: quote
description: "Fetch one symbol's live price snapshot (current price, change, day range, market state, and pre/post-market price) from Yahoo Finance. Holds no logic of its own -- it calls the finyahoo package's CLI (`finyahoo quote`) and shows the result to the user. Works for US stocks (AAPL), Korean tickers (005930.KS), and indices (^GSPC). Trigger phrases: current price, quote, live price, what's it trading at, how much is, 현재가, 시세, 실시간 시세, 지금 얼마, 호가, 현재 시세."
---

# finyahoo — live quote

Take one ticker and print its live price snapshot -- current price, previous close,
change and change percentage, the day's open/high/low, volume, market state and time,
pre-market and post-market price/change, and 50- and 200-day averages. The fetching and
parsing live in the finyahoo package (on PyPI); this skill is a thin wrapper that calls
its CLI and relays the result. An unknown ticker or a rate block comes back as a one-line
error -- relay it as-is.

## Prerequisite

This plugin calls the `finyahoo` CLI, so the package must be installed first:

```
pipx install finyahoo        # or: pip install finyahoo
```

That puts the `finyahoo` command on PATH. No API key or login is needed.

## Running

```
finyahoo quote "<SYMBOL>" [--json]
```

- Default output prints the live price snapshot as aligned `name  value` (absent
  fields are skipped -- an index carries only a few).
- `--json` emits the full record, including valuation fields omitted by the text view
  (Nones included).

This is the live snapshot **as of now** -- the current price when the market is open,
the last close otherwise; `market_state` (REGULAR / PRE / POST / CLOSED / ...) tells
which. It also carries pre-market and post-market price/change fields, reflecting the
current price during those sessions when `market_state` is PRE or POST. For dated bars
use the `history` skill; for fundamentals use `profile`.

## Procedure

1. **Get the symbol.** Find a Yahoo ticker (US `AAPL`; Korean `005930.KS` / `.KQ`;
   index `^GSPC`). If there is none, ask. Handle several requested symbols one at a time.
2. **Run.**
   ```bash
   finyahoo quote MU
   ```
   Add `--json` when the user wants every field or machine-readable data.
3. **Relay the result.** Show the CLI's stdout as-is; you may highlight the field the
   user asked about (e.g. just the price and change).
4. **Error handling.** When the CLI exits non-zero, relay the one-line
   `finyahoo: <message>` from stderr as-is:
   - `command not found: finyahoo` -> not installed; point the user at `pipx install finyahoo`.
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry.
   - the quote endpoint needs a session token (crumb) the client mints itself; a
     persistent block is Yahoo throttling this client, not a missing symbol.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It is a current snapshot only -- for dated prices use the `history` skill, and for the
  fundamentals snapshot (sector, margins, valuation) use the `profile` skill.
