---
name: consensus
description: "Fetch one symbol's sell-side analyst consensus from Yahoo Finance -- target price (high/low/mean/median), the recommendation rating (strong_buy..strong_sell) and its numeric mean, the analyst count, and the buy/hold/sell distribution over recent months. Holds no logic of its own -- it calls the finyahoo package's CLI (`finyahoo consensus`) and shows the result to the user. Works for any US or Korean equity Yahoo covers with analysts (AAPL, 005930.KS); indices and thinly-covered names have no consensus and return a 404. For the live price use the `quote` skill; for fundamentals use `profile`. Trigger phrases: analyst target, price target, consensus, sell-side, rating, buy hold sell, 목표주가, 목표가, 애널리스트, 컨센서스, 투자의견, 셀사이드."
---

# finyahoo — analyst consensus

Take one ticker and print its sell-side analyst consensus -- target price high / low /
mean / median, the recommendation (strong_buy / buy / hold / sell / strong_sell) and its
numeric mean, the analyst count, and the rating distribution across the last few months.
The fetching and parsing live in the finyahoo package (on PyPI); this skill is a thin
wrapper that calls its CLI and relays the result. An unknown ticker or a rate block comes
back as a one-line error -- relay it as-is. For the live price use `quote`, for the
fundamentals snapshot use `profile`.

## Prerequisite

This plugin calls the `finyahoo` CLI, so the package must be installed first:

```
pipx install finyahoo        # or: pip install finyahoo
```

That puts the `finyahoo` command on PATH. No API key or login is needed.

## Running

```
finyahoo consensus "<SYMBOL>" [--json]
```

- Default output prints the consensus as aligned `name  value` (symbol, target_high/low/
  mean/median, recommendation_mean, recommendation, analyst_count), then a short rating
  distribution -- this month (`0m`) back to `-3m`, counting strong_buy / buy / hold /
  sell / strong_sell.
- `--json` emits the full record.

This is the current sell-side consensus **as of now** -- targets and ratings aggregated
by Yahoo across the covering analysts. Note the target range can be very wide (a single
outlier high or low); the mean/median are the center, and `recommendation_mean` runs
1=strong_buy .. 5=strong_sell. For dated prices use `history`.

## Procedure

1. **Get the symbol.** Find a Yahoo ticker (US `AAPL`; Korean `005930.KS` / `.KQ`).
   Indices and names with no analyst coverage return a 404 -- consensus is equities-only
   in practice. If there is no symbol, ask. Handle several requested symbols one at a time.
2. **Run.**
   ```bash
   finyahoo consensus MU
   ```
   Add `--json` when the user wants every field or machine-readable data.
3. **Relay the result.** Show the CLI's stdout as-is -- do not drop, reorder, or rewrite
   rows. You may point to a field already in the output (the mean/median target, the
   rating, `recommendation_mean`, the analyst count, or the drift across the `0m`..`-3m`
   distribution rows). To compare a target against the live price, run `quote` -- the
   price is not in this command's output.
4. **Error handling.** When the CLI exits non-zero, relay the one-line
   `finyahoo: <message>` from stderr as-is:
   - `command not found: finyahoo` -> not installed; point the user at `pipx install finyahoo`.
   - a `...quoteSummary/<sym> returned 404` message -> a delisted/unknown ticker, an
     index, or a symbol with no analyst coverage (consensus is equities-only).
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It is sell-side estimates, not fundamentals or price -- use `profile` for the
  fundamentals snapshot and `quote` for the live price.
