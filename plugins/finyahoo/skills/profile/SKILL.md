---
name: profile
description: "Fetch a company's current fundamentals snapshot (sector, size, valuation, growth, margins) from Yahoo Finance. Holds no logic of its own -- it calls the finyahoo package's CLI (`finyahoo profile`) and shows the result to the user. Works for US stocks (AAPL), Korean tickers (005930.KS), and indices (^GSPC, limited fields). Trigger phrases: company profile, fundamentals, valuation, market cap, PE ratio, 기업정보, 펀더멘털, 프로파일, 시가총액."
---

# finyahoo — company profile

Take a ticker and print its current fundamentals -- sector, market cap, valuation
multiples, growth, margins. The fetching and parsing live in the finyahoo package (on
PyPI); this skill is a thin wrapper that calls its CLI and relays the result. An unknown
ticker or a rate block comes back as a one-line error -- relay it as-is.

## Prerequisite

This plugin calls the `finyahoo` CLI, so the package must be installed first:

```
pipx install finyahoo        # or: pip install finyahoo
```

That puts the `finyahoo` command on PATH. No API key or login is needed.

## Running

```
finyahoo profile "<SYMBOL>" [--json]
```

- Default output is the populated fields as aligned `name: value` (absent fields are
  skipped -- an index like `^GSPC` carries only a few).
- `--json` emits the full snapshot including the `null` fields.

This is a snapshot **as of now**, not history; for dated prices use the `history` skill.
Every numeric field is optional -- a missing one is null, never `0`.

## Procedure

1. **Get the symbol.** Find a Yahoo ticker (US `AAPL`; Korean `005930.KS`; index `^GSPC`).
   If there is none, ask. Handle several one at a time.
2. **Run.**
   ```bash
   finyahoo profile "AAPL"
   ```
   Add `--json` when the user wants every field (including the empty ones) or machine-
   readable data.
3. **Relay the result.** Show the CLI's stdout as-is; you may highlight the fields the
   user asked about (e.g. just market cap and PE).
4. **Error handling.** When the CLI exits non-zero, relay the one-line `finyahoo: <message>`
   from stderr as-is:
   - `command not found: finyahoo` -> not installed; point the user at `pipx install finyahoo`.
   - `Not Found` -> a delisted or unknown ticker.
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It is a current snapshot only -- for dated financial history use the library's
  `YahooClient.fetch_timeseries(...)`, or the `history` skill for prices.
