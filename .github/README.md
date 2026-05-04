# GitHub Actions — sUSDPegCockpit

## `collectors.yml`

Runs the full Python collector pipeline and commits any updated
`execution/client/public/data/**.json` snapshots back to `main`, then
mirrors them to the public data repo (`CryptoToit/susdpeg-data`) and
purges jsdelivr's CDN cache for those paths.

Runs on `workflow_dispatch` only — fired externally every 14 min by a
scheduler-as-a-service that hits this workflow's dispatch API. Manual
runs are also supported via the Actions UI ("Run workflow" button).

### One-time setup

1. **Repository secrets** — Settings → Secrets and variables → Actions:
   - `THEGRAPH_API_KEY` — TheGraph gateway API key (32 hex chars)
   - `DATA_REPO_DEPLOY_KEY` — ed25519 private key with write access to
     the `susdpeg-data` mirror repo (public key sits on that repo as a
     deploy key)
2. The workflow needs `permissions: contents: write` (already declared)
   so the `github-actions[bot]` user can push refreshed snapshots back.

### Cron cadence

Each tick runs all 9 collectors. With ~5 outbound API calls per
collector, every tick uses ~50 outbound queries. Daily total:
50 × ~100 ticks ≈ 5,000 queries — well inside TheGraph free tier
(100k/mo) and DefiLlama's free public-API expectations. Public-repo
GitHub Actions minutes are unmetered.

### Why an external scheduler

GitHub's built-in cron triggers are best-effort with documented drift
of 7–30 min on `*/15` and occasional silent skips. For a dashboard
freshness budget of 45 min, that drift is too tight. Firing
`workflow_dispatch` from an external scheduler that runs reliably gives
us deterministic 14-min cadence on free infrastructure.

### Smoke-test

After setting both secrets, trigger a manual run:
1. GitHub → Actions → "Refresh data snapshots" → "Run workflow"
2. Wait ~2–3 min for completion
3. Latest commit on `main` should be `auto: refresh snapshots [...]`
4. Check `CryptoToit/susdpeg-data` — its `main` should also have a
   matching `auto: refresh snapshots [...]` commit
