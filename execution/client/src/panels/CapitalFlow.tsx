import { useEffect, useState, useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import { snapshots } from '../lib/snapshots'
import type { FlowSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'
import ChartFrame from '../components/ChartFrame'
import { formatUSD } from '../lib/format'

export default function CapitalFlow() {
  const [data, setData] = useState<FlowSnapshot | null>(null)
  useEffect(() => {
    snapshots.flow().then(setData).catch(() => setData(null))
  }, [])

  const option = useMemo<EChartsOption | null>(() => {
    if (!data) return null
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          const p = params as { value?: number; name?: string }
          return `${p.name || ''}<br/>$${formatUSD(p.value ?? 0, { compact: true })}`
        },
      },
      series: [
        {
          type: 'sankey',
          nodeAlign: 'left',
          nodeGap: 14,
          nodeWidth: 12,
          layoutIterations: 64,
          data: data.nodes.map((n) => ({ name: n.label, value: n.value })),
          links: data.edges.map((e) => ({
            source: data.nodes.find((n) => n.id === e.from)?.label || e.from,
            target: data.nodes.find((n) => n.id === e.to)?.label || e.to,
            value: e.value,
          })),
          emphasis: { focus: 'adjacency' },
          lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
          label: { color: '#f4f4f5', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
          itemStyle: { color: '#4ade80', borderColor: '#2a2a30' },
        },
      ],
    }
  }, [data])

  if (!data || !option) return <div className="text-text-dim p-6">Loading capital flow…</div>

  return (
    <section id="flow" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Capital Flow Map
            <InfoPopover label="Capital Flow methodology">
              <p>
                <strong className="text-text-muted">Sources:</strong> ERC-20{' '}
                <code className="text-text-muted">totalSupply()</code> for the headline · live{' '}
                <code className="text-text-muted">balanceOf</code> on Synthetix Treasury wallets
                for the 420 Pool bucket · Dune for the Infinex bucket (daily) ·{' '}
                <a
                  href="https://yields.llama.fi/pools"
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent hover:underline"
                >
                  DefiLlama
                </a>{' '}
                for DEX pool TVLs.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">DEX Liquidity</strong> shows the top 5 pools
                by depth; smaller pools group into <em>Other DEX</em>.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Free-floating EOAs</strong> residual is mostly
                Infinex per-user Safe smart accounts (unlabeled on Etherscan). Major CEX exposure
                is negligible (~$138K Binance, &lt; 0.3% of supply).
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">420 Pool</strong>: verified locked sUSD from
                the 5M SNX staking rewards program — pool 8 holds SNX as collateral; sUSD is
                transferred directly to Treasury wallets, not held in v3 vault state. Note: a
                portion of this bucket (~$4M, see Unstake Queue) is currently in-transit at
                the council wallet, awaiting manual processing — when processed, that value
                flips to "Free-floating EOAs."
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Treasury reserves (non-420)</strong>:
                currently ~$0 because the tracked Treasury wallets only hold program-earmarked
                sUSD. Grows if/when Treasury accumulates buyback or operational sUSD.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">SLP Vault</strong>: $0 — contract not yet
                public. Synthetix contributor confirmed 2026-05-05 that it opens this quarter
                (~end of Q2), accepts sUSD only, locks deposits (no new minting), and the
                team's intent is for "most of the sUSD supply to go here." Published target:
                $15M by 2026-06-30; actual ambition appears materially higher.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            Where the {formatUSD(data.total_supply_susd, { compact: true })} sUSD supply currently
            sits.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      <ChartFrame option={option} height={380} />

      {/* Top-level bucket cards — derived from edges where the source is `supply` */}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
        {(() => {
          const topLevel = new Set(
            data.edges.filter((e) => e.from === 'supply').map((e) => e.to),
          )
          // Buckets without an on-chain source — value is a hardcoded best-
          // effort estimate. Visually annotate with "approx" so viewers don't
          // read it as live-measured.
          const APPROX_BUCKET_IDS = new Set(['infinex'])
          return data.nodes
            .filter((n) => topLevel.has(n.id))
            .map((n) => {
              const delta = data.delta_24h[n.id] || 0
              const isApprox = APPROX_BUCKET_IDS.has(n.id)
              return (
                <div key={n.id} className="border border-border/50 rounded p-2 bg-surface-2">
                  <div className="flex items-baseline justify-between gap-1">
                    <div className="text-text-dim font-mono text-[10px] uppercase tracking-wider truncate">
                      {n.label}
                    </div>
                    {isApprox && (
                      <span
                        className="shrink-0 text-[9px] font-mono uppercase tracking-wider px-1 py-0.5 rounded border border-warn/40 bg-warn/10 text-warn"
                        title="Hardcoded best-effort estimate — no live source. Variance is absorbed by the Free-floating EOAs residual."
                      >
                        Approx
                      </span>
                    )}
                  </div>
                  <div className="num font-semibold mt-1">
                    ${formatUSD(n.value, { compact: true })}
                  </div>
                  <div
                    className={`num text-[11px] mt-0.5 ${
                      delta < 0 ? 'text-danger' : delta > 0 ? 'text-ok' : 'text-text-muted'
                    }`}
                  >
                    {delta >= 0 ? '+' : ''}${formatUSD(delta, { compact: true })} 24h
                  </div>
                </div>
              )
            })
        })()}
      </div>
    </section>
  )
}
