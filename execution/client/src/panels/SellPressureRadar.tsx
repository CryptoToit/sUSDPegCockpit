import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { RadarSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'
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
  const isInterim = data.phase === 'interim'
  // Stored convention: net_flow values are NEGATIVE for outflows. We label the
  // tile "sUSD released" so display the absolute value — a release should read
  // as a positive number even though it represents lock→circulation movement.
  // Sign-driven coloring stays: red when any outflow has occurred, ok when none.
  const totalNetFlow24h = Object.values(data.net_flow_24h).reduce((a, b) => a + b, 0)
  const totalNetFlow7d = Object.values(data.net_flow_7d).reduce((a, b) => a + b, 0)
  const released24h = Math.abs(totalNetFlow24h)
  const released7d = Math.abs(totalNetFlow7d)
  const had_release_24h = totalNetFlow24h < 0
  const had_release_7d = totalNetFlow7d < 0

  return (
    <section id="radar" className={`border ${alert.border} rounded-lg ${alert.bg} p-4 sm:p-6`}>
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Sell-Pressure Radar
            <InfoPopover label="Sell-Pressure Radar methodology">
              <p>
                Tracks completed sUSD outflows from the council/Treasury wallets — the moment
                locked sUSD becomes circulating supply. Scans ERC-20{' '}
                <code className="text-text-muted">Transfer</code> events from{' '}
                <code className="text-text-muted">0xebAC8…d</code> (council wallet) and{' '}
                <code className="text-text-muted">0xFa1DF09…</code> (omnibus aux-recipient),
                across both chains, in 24h and 7d windows.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Scope note:</strong> this signal captures
                only the <strong>420 Pool jubilee exit path</strong> — stakers receiving back
                their sUSD principal. It does NOT capture general v2x SNX-side exits, which
                return SNX (not sUSD) and therefore never appear as a sUSD outflow. Those
                exits — and the queue of pending NFTs that will eventually trigger them —
                are tracked on the Unstake Queue panel below.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Exit ratio</strong> = 7d sUSD outflow ÷
                420 Pool locked total. Alert: <span className="text-ok">GREEN</span> &lt; 0.5%,{' '}
                <span className="text-warn">AMBER</span> &lt; 2%,{' '}
                <span className="text-danger">RED</span> ≥ 2%.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Phase qualifier:</strong>{' '}
                <span className="text-danger">INTERIM</span> means the alert level isn't
                fully meaningful yet — the mechanisms that would produce sUSD flow (jubilee
                burning, SLP Vault, scaled manual processing) haven't fired. Without those
                inputs, GREEN is structural, not a sign of health. <span className="text-text">
                ACTIVE</span> means at least one mechanism has started producing flow and
                the alert level becomes a real-time signal.
              </p>
              <p className="mt-2">
                This is a <em>lagging</em> indicator — it sees what's been processed, not
                what's queued. For the leading-edge view of intent + queue depth + processing
                lag, see the Unstake Queue panel below; the Recovery Score's flow subscore
                reads from there too.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            sUSD released from the 420 Pool since unlock (
            <span className="num">2026-04-19</span> · {data.days_since_unlock} days). Lagging
            indicator — leading-edge view: Unstake Queue below.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div
          className={`${alert.bg} rounded p-4 ${
            isInterim
              ? 'border-2 border-danger/60 ring-1 ring-danger/30'
              : `border ${alert.border}`
          }`}
        >
          <div className="flex items-baseline justify-between gap-2">
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
              Alert level
            </div>
            {isInterim && (
              <span className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border border-danger/60 bg-danger/15 text-danger">
                Interim
              </span>
            )}
          </div>
          <div className={`${alert.text} text-2xl sm:text-3xl font-semibold mt-1 num`}>{alert.label}</div>
          <div className="text-text-muted text-xs mt-1 num">Exit ratio: {exitPct.toFixed(1)}%</div>
        </div>
        <div className="border border-border rounded p-4 bg-surface">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            420 Pool locked sUSD
          </div>
          <div className="num text-2xl font-semibold mt-1">${formatUSD(data.unlocked_susd_total, { compact: true })}</div>
          <div className="text-text-muted text-xs mt-1">
            ≈ ${formatUSD(data.unlocked_susd_left_protective_venues, { compact: true })} projected
            in 7d at current pace
          </div>
        </div>
        <div className="border border-border rounded p-4 bg-surface">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            sUSD released (jubilee path)
          </div>
          <div className={`num text-2xl font-semibold mt-1 ${had_release_7d ? 'text-danger' : 'text-ok'}`}>
            7d: ${formatUSD(released7d, { compact: true })}
          </div>
          <div className={`text-xs mt-1 num ${had_release_24h ? 'text-danger' : 'text-ok'}`}>
            24h: ${formatUSD(released24h, { compact: true })}
          </div>
        </div>
      </div>

      {isInterim && (
        <div className="mb-4 border-2 border-danger/40 bg-danger/5 rounded px-3 py-2.5 text-xs leading-relaxed">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-danger font-semibold">
              ⚠ Interim phase — read GREEN with care
            </span>
          </div>
          <p className="text-text">
            The alert is GREEN because <strong>~$0 sUSD has flowed out</strong>. But that's
            not because the system is healthy — it's because the mechanisms that would
            <em> produce</em> flow haven't fired yet:
          </p>
          <ul className="mt-1.5 space-y-0.5 text-text-dim list-disc list-inside">
            <li>
              <strong className="text-text-muted">Jubilee burning:</strong> $0 cumulative —
              gated on stakers reaching 100% of original-debt sUSD coverage. Almost no one
              is there.
            </li>
            <li>
              <strong className="text-text-muted">SLP Vault:</strong> not yet live — opens
              ~end of Q2 2026 as a sUSD sink.
            </li>
            <li>
              <strong className="text-text-muted">Manual jubilee processing:</strong> ~$1.5K
              of sUSD released across 180 days — minimal throughput so far.
            </li>
          </ul>
          <p className="mt-1.5 text-text-dim">
            Treat the GREEN reading as <em>"no flow yet"</em>, not <em>"all clear"</em>. The
            radar will switch to <strong className="text-text">ACTIVE</strong> phase once any
            of these mechanisms starts producing meaningful sUSD movement.
          </p>
        </div>
      )}

      <div className="h-3 bg-surface-2 rounded overflow-hidden flex border border-border">
        <div className="bg-ok/70" style={{ width: `${remainingPct}%` }} />
        <div className={alert.text === 'text-danger' ? 'bg-danger' : 'bg-warn'} style={{ width: `${exitPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-text-muted font-mono mt-1">
        <span>STILL LOCKED IN 420 POOL: {remainingPct.toFixed(1)}%</span>
        <span>RELEASED (7d): {exitPct.toFixed(1)}%</span>
      </div>
    </section>
  )
}
