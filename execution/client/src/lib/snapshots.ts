import type {
  Manifest,
  PegSnapshot,
  SupplySnapshot,
  FlowSnapshot,
  TradeFlowSnapshot,
  ScorecardSnapshot,
  YieldSnapshot,
  RadarSnapshot,
  NftQueueSnapshot,
  RecoveryScoreSnapshot,
  EventItem,
} from '../types'

// In production, fetch JSONs from jsdelivr's GitHub-mirroring CDN so data
// updates flow through without rebuilding/redeploying the container. The
// cron workflow mirrors fresh snapshots from the (private) source repo to
// the (public) `CryptoToit/susdpeg-data` repo every ~14 minutes.
//
// jsdelivr's GitHub proxy only serves public repos — that's why a separate
// public mirror exists. Source code stays private; just the data is open.
//
// Cache strategy: jsdelivr's `@main` URLs and query-param cache-busting are
// both unreliable on the gh proxy (verified empirically — purges accepted
// but edge propagation can stay stale for hours; query params are ignored).
// What DOES work: `@<commit-sha>` URLs are immediately fresh because each
// commit produces a unique URL with no aliasing.
//
// So on app load we resolve the latest data-repo commit SHA via GitHub's
// REST API (one call per session, cached in memory), then pin every JSON
// fetch to that SHA. CORS works from any origin; rate limit is 60/hr per
// client IP — plenty for a normal browsing session, since we cache after
// the first call. Falls back to `@main` if the API is rate-limited or
// unreachable, so the dashboard degrades gracefully instead of breaking.
//
// In dev (npm run dev), keep relative paths so local edits to public/data/
// are picked up immediately without a network round-trip.
const CDN_BASE = 'https://cdn.jsdelivr.net/gh/CryptoToit/susdpeg-data'
const SHA_API = 'https://api.github.com/repos/CryptoToit/susdpeg-data/commits/main'
const SHA_FETCH_TIMEOUT_MS = 5_000

let shaPromise: Promise<string> | null = null

function resolveLatestSha(): Promise<string> {
  if (shaPromise) return shaPromise
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), SHA_FETCH_TIMEOUT_MS)
  shaPromise = fetch(SHA_API, { signal: controller.signal })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`SHA lookup ${r.status}`))))
    .then((d: { sha?: string }) => (d.sha ? d.sha.slice(0, 7) : 'main'))
    .catch((err) => {
      // Rate-limited / offline / aborted — fall back to @main (might be stale,
      // but the dashboard still works).
      console.warn('[snapshots] SHA lookup failed, falling back to @main:', err)
      return 'main'
    })
    .finally(() => clearTimeout(timer))
  return shaPromise
}

async function fetchJson<T>(path: string): Promise<T> {
  let url: string
  if (import.meta.env.PROD) {
    const sha = await resolveLatestSha()
    // path arrives as `/data/<snapshot>/latest.json`; strip leading `/data` so
    // we don't double up against the CDN base.
    const tail = path.replace(/^\/data/, '')
    url = `${CDN_BASE}@${sha}/data${tail}`
  } else {
    url = `${path}?t=${Date.now()}`
  }
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`)
  return res.json()
}

export const snapshots = {
  manifest: () => fetchJson<Manifest>('/data/manifest.json'),
  recoveryScore: () => fetchJson<RecoveryScoreSnapshot>('/data/recovery_score/latest.json'),
  peg: () => fetchJson<PegSnapshot>('/data/peg/latest.json'),
  supply: () => fetchJson<SupplySnapshot>('/data/supply/latest.json'),
  flow: () => fetchJson<FlowSnapshot>('/data/flow/latest.json'),
  tradeFlow: () => fetchJson<TradeFlowSnapshot>('/data/trade_flow/latest.json'),
  scorecard: () => fetchJson<ScorecardSnapshot>('/data/scorecard/latest.json'),
  yields: () => fetchJson<YieldSnapshot>('/data/yield/latest.json'),
  radar: () => fetchJson<RadarSnapshot>('/data/radar/latest.json'),
  nftQueue: () => fetchJson<NftQueueSnapshot>('/data/nft_queue/latest.json'),
  events: () => fetchJson<{ events: EventItem[] }>('/data/events.json'),
}
