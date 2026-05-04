import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { PegSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import { ChainIcon, VenueGlyph, SUPPORTED_CHAINS } from '../components/Icons'
import { formatPrice, formatBp, formatUSD } from '../lib/format'

function venueDeviationBp(venue_price: number, ref: number): number {
  return Math.round(((venue_price - ref) / ref) * 10000)
}

export default function TradingVenues() {
  const [data, setData] = useState<PegSnapshot | null>(null)
  useEffect(() => {
    snapshots.peg().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading venues…</div>

  return (
    <section id="venues" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">Trading Venues</h2>
          <p className="text-text-dim text-sm">
            All DEX pools with ≥ $10K sUSD depth, sorted by TVL. Sub-$10K pools and lending /
            leverage markets are excluded (low arb capacity / different mechanic). Pairs marked{' '}
            <span className="text-text-muted">non-stable</span> (e.g. sUSD/SNX, sUSD/WETH) require
            counter-asset price conversion — their displayed sUSD price is approximate.{' '}
            <span className="text-text-muted">Turnover</span> (24h vol ÷ depth) flags whether
            depth is being used: <span className="text-ok">≥ 5%</span> active ·{' '}
            <span className="text-warn">1–5%</span> mild · <span className="text-danger">&lt; 1%</span>{' '}
            stale. sUSD price discovery is 100% on-chain — Binance's legacy sUSD pairs are halted
            (status <code className="text-text-muted">BREAK</code>) and other major CEXes hold zero.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={30} />
      </header>

      {/* Chain coverage — chains the venues span */}
      <div className="mb-5">
        <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-2">
          Chain coverage
        </div>
        <div className="flex flex-wrap gap-2">
          {SUPPORTED_CHAINS.map((c) => (
            <div
              key={c.slug}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded border border-ok/30 bg-ok/5 text-text text-xs"
            >
              <ChainIcon chain={c.label} size={16} />
              <span className="font-medium">{c.label}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-ok">Live</span>
            </div>
          ))}
        </div>
      </div>

      {/* Venue cards — sorted by depth desc */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {[...data.venues]
          .sort((a, b) => b.depth_usd - a.depth_usd)
          .map((v, i) => {
            const dev = venueDeviationBp(v.price_usd, data.reference.price_usd)
            const isNonStable = v.pair_kind === 'non-stable'
            const vol = v.volume_24h_usd
            const turnover = vol != null && v.depth_usd > 0 ? (vol / v.depth_usd) * 100 : null
            const turnoverColor =
              turnover == null
                ? 'text-text-dim'
                : turnover >= 5
                ? 'text-ok'
                : turnover >= 1
                ? 'text-warn'
                : 'text-danger'
            return (
              <div
                key={i}
                className="border border-border rounded-lg bg-surface-2 p-4 hover:border-border/80 transition"
              >
                <div className="flex items-start gap-3 mb-3">
                  <VenueGlyph dex={v.dex} chain={v.chain} size={36} />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-sm truncate">{v.name}</div>
                    <div className="flex items-center gap-1.5 text-text-dim text-xs mt-0.5">
                      <ChainIcon chain={v.chain} size={12} />
                      <span>{v.chain}</span>
                      {isNonStable && (
                        <span className="ml-1.5 px-1.5 py-0.5 rounded border border-warn/30 bg-warn/10 text-warn text-[9px] font-mono uppercase tracking-wider">
                          non-stable
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-baseline justify-between border-t border-border/50 pt-3">
                  <div>
                    <div className="num text-2xl font-semibold">${formatPrice(v.price_usd)}</div>
                    <div
                      className={`num text-[11px] mt-0.5 ${
                        dev < -100 ? 'text-danger' : dev < 0 ? 'text-warn' : 'text-ok'
                      }`}
                    >
                      {formatBp(dev)} vs ref
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
                      Depth
                    </div>
                    <div className="num text-sm text-text-muted mt-0.5">
                      ${formatUSD(v.depth_usd, { compact: true })}
                    </div>
                    <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mt-2">
                      Vol 24h
                    </div>
                    <div className="num text-xs text-text-muted mt-0.5">
                      {vol != null ? `$${formatUSD(vol, { compact: true })}` : '—'}
                      {turnover != null && (
                        <span className={`ml-1.5 ${turnoverColor}`}>{turnover.toFixed(2)}%</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
      </div>
    </section>
  )
}
