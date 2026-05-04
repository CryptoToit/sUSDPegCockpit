import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { RadarSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import { formatUSD } from '../lib/format'

const ALERT = {
  green: { bg: 'bg-ok/10', border: 'border-ok/40', text: 'text-ok', label: 'GREEN' },
  amber: { bg: 'bg-warn/10', border: 'border-warn/40', text: 'text-warn', label: 'AMBER' },
  red: { bg: 'bg-danger/10', border: 'border-danger/40', text: 'text-danger', label: 'RED' },
}

export default function SellPressureRadar() {
  const [data, setData] = useState<RadarSnapshot | null>(null)
  useEffect(() => {
    snapshots.radar().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading sell-pressure radar…</div>

  const alert = ALERT[data.alert_level]
  const exitPct = data.exit_ratio_pct
  const remainingPct = 100 - exitPct
  const totalNetFlow24h = Object.values(data.net_flow_24h).reduce((a, b) => a + b, 0)
  const totalNetFlow7d = Object.values(data.net_flow_7d).reduce((a, b) => a + b, 0)

  return (
    <section id="radar" className={`border ${alert.border} rounded-lg ${alert.bg} p-4 sm:p-6`}>
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">Sell-Pressure Radar</h2>
          <p className="text-text-dim text-sm">
            Live sUSD outflows from the 420 Pool program since the post-unlock window opened on{' '}
            <span className="num">2026-04-19</span> ({data.days_since_unlock} days). Methodology:
            scan ERC-20 <code className="text-text-muted">Transfer</code> events from the two
            Synthetix Treasury wallets (<code className="text-text-muted">0xebAC8…d</code>{' '}
            NFT-custody + <code className="text-text-muted">0xFa1DF09…</code> aux-recipient), both
            chains, 24h + 7d windows. Outflows = locked sUSD becoming circulating supply. Exit
            ratio = 7d outflow ÷ locked total — alert{' '}
            <span className="text-ok">GREEN</span> &lt;0.5%, <span className="text-warn">AMBER</span>{' '}
            &lt;2%, <span className="text-danger">RED</span> ≥2%.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div className={`${alert.bg} ${alert.border} border rounded p-4`}>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">Alert level</div>
          <div className={`${alert.text} text-2xl sm:text-3xl font-semibold mt-1 num`}>{alert.label}</div>
          <div className="text-text-muted text-xs mt-1 num">Exit ratio: {exitPct.toFixed(1)}%</div>
        </div>
        <div className="border border-border rounded p-4 bg-surface">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">420 Pool locked</div>
          <div className="num text-2xl font-semibold mt-1">${formatUSD(data.unlocked_susd_total, { compact: true })}</div>
          <div className="text-text-muted text-xs mt-1">
            ${formatUSD(data.unlocked_susd_left_protective_venues, { compact: true })} after 7d
            outflows
          </div>
        </div>
        <div className="border border-border rounded p-4 bg-surface">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">Net outflow</div>
          <div className={`num text-2xl font-semibold mt-1 ${totalNetFlow7d < 0 ? 'text-danger' : 'text-ok'}`}>
            7d: ${formatUSD(totalNetFlow7d, { compact: true })}
          </div>
          <div className={`text-xs mt-1 num ${totalNetFlow24h < 0 ? 'text-danger' : 'text-ok'}`}>
            24h: ${formatUSD(totalNetFlow24h, { compact: true })}
          </div>
        </div>
      </div>

      <div className="h-3 bg-surface-2 rounded overflow-hidden flex border border-border">
        <div className="bg-ok/70" style={{ width: `${remainingPct}%` }} />
        <div className={alert.text === 'text-danger' ? 'bg-danger' : 'bg-warn'} style={{ width: `${exitPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-text-muted font-mono mt-1">
        <span>STAYED: {remainingPct.toFixed(1)}%</span>
        <span>EXITED: {exitPct.toFixed(1)}%</span>
      </div>
    </section>
  )
}
