---
name: match
description: "Look up matching Yahoo Finance symbols for a company name or partial ticker -- each match's symbol, quote type (EQUITY/ETF/...), exchange, sector, and full name. Use it to resolve a name to the right ticker before quote/profile/history/consensus/news. Holds no logic of its own -- it calls the finyahoo package's CLI (`finyahoo match`) and shows the result to the user. Trigger phrases: find ticker, symbol lookup, what's the ticker for, search symbol, resolve symbol, 티커 찾기, 종목 코드, 심볼 검색, 티커가 뭐야, 종목코드 알려줘."
---

# finyahoo — symbol match

Take a company name or partial ticker and print the matching Yahoo symbols -- each
match's symbol, quote type (EQUITY / ETF / ...), exchange, sector, and full name. Default
is 6 matches; `--count` requests more. Use it to resolve a name to the right ticker
before `quote` / `profile` / `history` / `consensus` / `news`. The fetching and parsing
live in the finyahoo package (on PyPI); this skill is a thin wrapper that calls its CLI
and relays the result. A no-match or rate block comes back as a one-line error -- relay
it as-is.

## Prerequisite

This plugin calls the `finyahoo` CLI, so the package must be installed first:

```
pipx install finyahoo        # or: pip install finyahoo
```

That puts the `finyahoo` command on PATH. No API key or login is needed.

## Running

```
finyahoo match "<QUERY>" [-n COUNT] [--json]
```

- `QUERY` is a company name or ticker fragment (`SK hynix`, `MU`) -- unlike the other
  skills this takes a free-text query, not a strict symbol.
- Default prints up to 6 matches as `symbol  type  exchange  sector  name`.
- `-n` / `--count N` requests more; `--json` emits the full records.

This resolves a name to candidate tickers **as of now**. The same company often returns
several listings -- watch for the intended one (e.g. `000660.KS` is SK hynix's Korean
primary, `SKHY` a US listing, `SKDD` / `SKHX` leveraged ETFs). Read the `type` /
`exchange` columns to tell them apart and prefer the primary listing unless the user
wants a specific market.

## Procedure

1. **Get the query.** A company name or ticker fragment. (This takes a QUERY, not a
   strict symbol -- so a plain company name is fine.)
2. **Run.**
   ```bash
   finyahoo match "SK hynix"
   ```
   Add `-n 10` for more matches; `--json` for machine-readable data.
3. **Relay the result.** Show the CLI's stdout as-is; you may point out the primary
   listing vs ADRs / leveraged ETFs, and hand the chosen symbol on to `quote` /
   `profile` / `history` / `consensus` / `news`.
4. **Error handling.** When the CLI exits non-zero, relay the one-line
   `finyahoo: <message>` from stderr as-is:
   - `command not found: finyahoo` -> not installed; point the user at `pipx install finyahoo`.
   - a 429 / refusing-this-client message -> Yahoo is rate-limiting; wait and retry.

   A query with no match is NOT an error -- `match` exits 0 and prints `(no matches)` to
   stdout; relay that and suggest a different spelling.

## What this skill does not do

- It does not re-implement fetching or parsing (the package does); it always calls the CLI.
- It only lists candidate symbols -- it does not fetch prices or fundamentals; chain into
  `quote` / `profile` / `history` / `consensus` / `news` with the chosen symbol.
