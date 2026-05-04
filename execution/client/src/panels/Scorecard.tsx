import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { KpiStatus, ScorecardSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import KpiCard from '../components/KpiCard'

const STATUS_ORDER: KpiStatus[] = ['verified', 'stub', 'closed', 'context']

export default function Scorecard() {
  const [data, setData] = useState<ScorecardSnapshot | null>(null)
  useEffect(() => {
    snapshots.scorecard().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading scorecard…</div>

  const sorted = [...data.kpis].sort((a, b) => {
    const aIdx = STATUS_ORDER.indexOf(a.status ?? 'stub')
    const bIdx = STATUS_ORDER.indexOf(b.status ?? 'stub')
    return aIdx - bIdx
  })

  return (
    <section id="scorecard" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">Recovery Program Scorecard</h2>
          <p className="text-text-dim text-sm">
            Synthetix recovery KPIs vs published targets (
            <a href="https://blog.synthetix.io/2026-roadmap/" className="text-accent hover:underline" target="_blank" rel="noreferrer">
              2026 Roadmap
            </a>{' '}
            +{' '}
            <a href="https://blog.synthetix.io/rebuilding-susd/" className="text-accent hover:underline" target="_blank" rel="noreferrer">
              Rebuilding sUSD
            </a>
            ). Sorted by data confidence — <span className="text-ok">VERIFIED</span> first, then{' '}
            <span className="text-warn">STUB</span>, paused programs last. Status chips on each card
            indicate which figures are on-chain anchored vs. plausible placeholders pending real
            ETL.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {sorted.map((kpi) => (
          <KpiCard key={kpi.id} kpi={kpi} />
        ))}
      </div>
    </section>
  )
}
