# sUSDPegCockpit — Pipeline

Python collectors that fetch live data from public sources and write JSON snapshots consumed by the React client.

## Layout

```
pipeline/
├── collectors/   one .py per snapshot type (peg.py, supply.py, …)
├── schemas/      Pydantic models mirroring client/src/types.ts
├── lib/          shared HTTP + atomic-write helpers
└── tests/        pytest
```

Output destination: `execution/client/public/data/{snapshot}/latest.json` (the same files the React client already reads).

## Setup

```bash
cd execution/pipeline
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
# from execution/pipeline/ with .venv active
python -m collectors.peg
```

This refreshes `execution/client/public/data/peg/latest.json` from live sources.

## Sources

Free, public, no auth required for the first round of collectors:

- **DefiLlama** — sUSD reference price (`coins.llama.fi`), per-venue depth (`yields.llama.fi`)
- **DexScreener** — per-pool 24h volume + spot price (`api.dexscreener.com`)
- **Curve API** — fallback for pools DexScreener doesn't index, e.g. Curve sUSD/3CRV (Optimism) (`api.curve.finance`)

For Phase 2 collectors that need swap-event indexing (Trade Flow, Capital Flow), TheGraph gateway API key + free Dune account will be added. See `directions/proposal/07-external-data-sources.md` for the full source catalog.

## Conventions

- **Atomic writes:** collectors write to `*.tmp` then atomically rename — prevents the React client from reading a half-written file mid-refresh.
- **Hard-fail on missing required data:** for the first iteration, if a source is unreachable the collector exits non-zero. Fallback / last-good-value caching is a Phase 2 polish item.
- **Schema validation:** every snapshot is validated against its Pydantic schema before write.
- **Pinned dependency versions:** per the project standard — never use caret/tilde ranges.
