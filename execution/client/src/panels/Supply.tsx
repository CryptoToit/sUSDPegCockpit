import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { SupplySnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'
import { ChainIcon } from '../components/Icons'
import { formatUSD } from '../lib/format'

const CHAIN_LABELS: Record<string, string> = {
  ethereum: 'Ethereum',
  optimism: 'Optimism',
  base: 'Base',
  arbitrum: 'Arbitrum',
}

export default function Supply() {
  const [data, setData] = useState<SupplySnapshot | null>(null)
  useEffect(() => {
    snapshots.supply().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading supply…</div>

  const chains = Object.entries(data.supply_by_chain).sort((a, b) => b[1] - a[1])

  return (
    <section id="supply" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Issued Supply
            <InfoPopover label="Issued Supply methodology">
              <p>
                ERC-20 <code className="text-text-muted">totalSupply()</code> reads on the legacy
                Synthetix sUSD token, both Ethereum and Optimism deployments.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Scope note:</strong> Synthetix v3's native
                stable on Base / Arbitrum is a different token —{' '}
                <span className="text-text-muted">snxUSD / USDx</span> — and is NOT part of the
                peg recovery story tracked here.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">Legacy sUSD circulating across Ethereum + Optimism.</p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={60} />
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
        <div className="md:col-span-1">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Total issued
          </div>
          <div className="num text-4xl sm:text-5xl font-semibold mt-1">
            ${formatUSD(data.total_supply_susd, { compact: true })}
          </div>
          <div className="text-text-muted text-xs mt-1">
            across {chains.length} chain{chains.length === 1 ? '' : 's'}
          </div>
        </div>

        <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {chains.map(([slug, value]) => {
            const pct = (value / data.total_supply_susd) * 100
            return (
              <div key={slug} className="border border-border rounded p-3 bg-surface-2">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <ChainIcon chain={CHAIN_LABELS[slug] || slug} size={18} />
                    <span className="font-medium">{CHAIN_LABELS[slug] || slug}</span>
                  </div>
                  <span className="num text-text-dim text-xs">{pct.toFixed(0)}%</span>
                </div>
                <div className="num text-xl font-semibold">
                  ${formatUSD(value, { compact: true })}
                </div>
                <div className="h-1 bg-bg rounded mt-2 overflow-hidden">
                  <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
