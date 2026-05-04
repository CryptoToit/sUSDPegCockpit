import { useEffect, useState, useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import { snapshots } from '../lib/snapshots'
import type { FlowSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
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
          <h2 className="text-lg font-semibold">Capital Flow Map</h2>
          <p className="text-text-dim text-sm">
            Where the {formatUSD(data.total_supply_susd, { compact: true })} sUSD supply currently
            sits. Sources: ERC-20 <code className="text-text-muted">totalSupply()</code> for total
            · live ERC-20 <code className="text-text-muted">balanceOf</code> on the two Synthetix
            Treasury wallets (<code className="text-text-muted">0xebAC8…d</code> NFT-custody +{' '}
            <code className="text-text-muted">0xFa1DF09…</code> aux-recipient, both chains) for the
            420 Pool · Dune <code className="text-text-muted">0xaugmented/infinex</code> for the
            Infinex bucket (daily) ·{' '}
            <a
              href="https://yields.llama.fi/pools"
              target="_blank"
              rel="noreferrer"
              className="text-accent hover:underline"
            >
              DefiLlama
            </a>{' '}
            for DEX pool TVLs. The DEX Liquidity sub-tree shows the top 5 pools by depth; the
            remaining smaller pools are grouped as <em>Other DEX</em>. The{' '}
            <em>Free-floating EOAs</em> residual is largely composed of Infinex user Safe smart
            accounts (Infinex deploys per-user Safes — they appear as unlabeled large EOAs on
            Etherscan); CEX exposure is negligible (~$138K Binance, &lt;0.3% of supply, all other
            major CEXes hold zero). The <em>420 Pool</em> bucket is the verified locked sUSD from
            the 5M SNX staking rewards program — pool 8 architecture holds SNX as collateral and
            sUSD is transferred directly to Treasury wallets, not held in v3 vault state. The{' '}
            <em>Treasury reserves (non-420)</em> bucket is what's left of Synthetix Treasury sUSD
            holdings after subtracting the 420 Pool aux-recipient leg — currently ~$0 because the
            tracked Treasury wallets only hold program-earmarked sUSD; this bucket grows if/when
            Treasury accumulates buyback or operational sUSD. The <em>SLP Vault</em> bucket is
            $0 — Synthetix confirmed it's in private/internal mode with no published TVL; public
            launch is planned for Q2 2026, official target $15M sUSD by 2026-06-30.
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
          return data.nodes
            .filter((n) => topLevel.has(n.id))
            .map((n) => {
              const delta = data.delta_24h[n.id] || 0
              return (
                <div key={n.id} className="border border-border/50 rounded p-2 bg-surface-2">
                  <div className="text-text-dim font-mono text-[10px] uppercase tracking-wider truncate">
                    {n.label}
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
