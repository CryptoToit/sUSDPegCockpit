# sUSD Peg Cockpit

A public-good monitoring dashboard for Synthetix's legacy sUSD peg recovery
program. Surfaces peg health, supply attribution, recovery-program progress,
sell-pressure, capital flow, trading venues, and stakeholder yield comparisons
— sourced from on-chain reads and free public APIs (DefiLlama, DexScreener,
public RPCs, TheGraph).

Ships under the maintainer pseudonym `0x_ct`. Donations:
`0xf5a6746765476e819c2efB0619cd578b4D95903A`.

## How it works

Two repos:

- **This repo** — code (React SPA + Python collectors + GitHub Actions cron)
- [`CryptoToit/susdpeg-data`](https://github.com/CryptoToit/susdpeg-data) —
  public mirror of fresh JSON snapshots written by the cron, served to the
  client via jsdelivr's GitHub proxy

```
external sources  →  collectors (Python)  →  this repo's main
                                             ↓
                                   public data mirror (susdpeg-data)
                                             ↓
                                          jsdelivr CDN
                                             ↓
                                         React SPA
```

Cron runs every 14 min via `workflow_dispatch` triggered by an external
scheduler (GitHub's built-in cron is too unreliable for the freshness
budget). The SPA resolves the latest data-mirror commit SHA on each page
load and pins all JSON fetches to that SHA — bypasses jsdelivr's `@main`
edge-cache propagation lag.

## Layout

```
execution/
  client/      React + Vite + Tailwind SPA — 10 panels
  pipeline/    Python collectors (httpx + Pydantic), 9 snapshots
  server/      reserved (currently empty — SPA is fully static)
  shared/      reserved
.github/
  workflows/
    collectors.yml   the cron + mirror push + jsdelivr purge
```

## Local development

```bash
# Frontend dev server
cd execution/client
npm install
npm run dev

# Run collectors locally (writes to execution/client/public/data/)
cd execution/pipeline
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # add your THEGRAPH_API_KEY
python -m scripts.run_all
```

Tests:
```bash
cd execution/pipeline
pytest
```

## Hosting

The dashboard is being moved to decentralized hosting:
[Cloudflare Pages](https://pages.cloudflare.com) (clearnet primary) +
[Pinata IPFS](https://pinata.cloud) mirror, addressable via
`susdpeg.eth` ENS contenthash. Until that lands, the project runs on
a centralized stop-gap host — see `CryptoToit/susdpeg-data` commits to
verify the data flow is live regardless.

## License

Not yet declared. Treat as "all rights reserved" until a license is added.
