import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { PegSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'
import { formatPrice, formatBp } from '../lib/format'

export default function PegTracker() {
  const [data, setData] = useState<PegSnapshot | null>(null)
  useEffect(() => {
    snapshots.peg().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading peg data…</div>

  const refTo98Bp = Math.round(((0.98 - data.reference.price_usd) / data.reference.price_usd) * 10000)

  return (
    <section id="peg" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Peg Tracker
            <InfoPopover label="Peg Tracker methodology">
              <p>
                Where sUSD trades against $1.00 right now.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Reference price:</strong> cross-venue
                aggregator (DefiLlama). The Chainlink sUSD/USD Mainnet aggregator was
                decommissioned and there's no Chainlink sUSD feed on Optimism, so DefiLlama is
                the most reliable single source.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Weighted avg:</strong> depth-weighted across
                tracked DEX pools (see Trading Venues panel for the constituent set).
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Recovery threshold:</strong> $0.98 — the
                price level at which the sUSD-staking ratchet halts per SIP-420.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            Where sUSD trades against $1.00 right now.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={30} />
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Reference price
          </div>
          <div className="num text-3xl sm:text-5xl font-semibold mt-1">
            ${formatPrice(data.reference.price_usd)}
          </div>
          <div className="text-text-muted text-sm mt-1">via {data.reference.source}</div>
        </div>
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Weighted avg (venues)
          </div>
          <div className="num text-3xl sm:text-5xl font-semibold mt-1">
            ${formatPrice(data.weighted_avg_price_usd)}
          </div>
          <div className="text-warn text-sm mt-1 num">{formatBp(data.depeg_basis_points)} from peg</div>
        </div>
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Recovery threshold
          </div>
          <div className="num text-3xl sm:text-5xl font-semibold mt-1 text-text-muted">$0.9800</div>
          <div className="text-text-muted text-sm mt-1 num">
            {formatBp(refTo98Bp)} away · sUSD-staking ratchet halts at peg ≥ $0.98 (SIP-420)
          </div>
        </div>
      </div>
    </section>
  )
}
