import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { RecoveryScoreSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'

const TIER_STYLES: Record<
  RecoveryScoreSnapshot['tier'],
  { text: string; bg: string; border: string; bar: string; label: string }
> = {
  critical: {
    text: 'text-danger',
    bg: 'bg-danger/10',
    border: 'border-danger/40',
    bar: 'bg-danger',
    label: 'EARLY STAGE',
  },
  behind_pace: {
    text: 'text-warn',
    bg: 'bg-warn/10',
    border: 'border-warn/40',
    bar: 'bg-warn',
    label: 'BUILDING MOMENTUM',
  },
  on_pace: {
    text: 'text-ok',
    bg: 'bg-ok/10',
    border: 'border-ok/40',
    bar: 'bg-ok',
    label: 'ON PACE',
  },
  recovery_near: {
    text: 'text-ok',
    bg: 'bg-ok/10',
    border: 'border-ok/40',
    bar: 'bg-ok',
    label: 'NEAR RECOVERY',
  },
}

function subscoreColor(score: number): { bar: string; text: string } {
  if (score >= 65) return { bar: 'bg-ok', text: 'text-ok' }
  if (score >= 35) return { bar: 'bg-warn', text: 'text-warn' }
  return { bar: 'bg-danger', text: 'text-danger' }
}

export default function RecoveryScore() {
  const [data, setData] = useState<RecoveryScoreSnapshot | null>(null)
  useEffect(() => {
    snapshots.recoveryScore().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading recovery score…</div>

  const tier = TIER_STYLES[data.tier]

  return (
    <section id="recovery-score" className={`border ${tier.border} rounded-lg ${tier.bg} p-4 sm:p-6`}>
      <header className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Recovery Score
            <InfoPopover label="Recovery Score methodology">
              <p>
                Composite = Σ (subscore × weight). Each subscore is 0–100; composite is also
                0–100. Tiers:{' '}
                <span className="text-danger">&lt; 35 early stage</span>,{' '}
                <span className="text-warn">35–65 building momentum</span>,{' '}
                <span className="text-ok">65–85 on pace</span>,{' '}
                <span className="text-ok">85+ near recovery</span>. Heuristic, not a guarantee —
                helps frame the program's overall state, not predict outcomes.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Flow subscore (v2):</strong> reads the Unstake
                Queue's full exit funnel — queue inflow growth (35%) + processing backlog share
                (30%) + observed sell-through (35%). Replaces the prior radar traffic-light read,
                which was blind to building queue pressure. Sell-through is a lower bound — see
                the Unstake Queue panel for the underlying signals.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Jubilee subscore:</strong> 30% structural
                ($10M Phase 2 precondition) + 70% burning ($60M outcome). Burning is the
                actual driver of peg recovery — debt forgiveness reduces the sUSD overhang.
                Structural deposits are a precondition, not the recovery itself. The burn
                mechanic is gated on stakers being at 100% of their original debt
                collateralized in sUSD; most are nowhere near, so $0 cumulative burn is
                structurally expected — but it also means the recovery contribution from
                jubilee is essentially zero today.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Upcoming inflection points:</strong> the
                score may shift materially around (a) the SLP Vault launch (~end of Q2 2026 —
                a major sUSD sink) and (b) the 5M-SNX linear release window end (~2026-07-19 —
                stakers' financial incentive to delay exit ends). Movements around these dates
                are structurally driven and don't necessarily indicate program success or
                failure.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            Weighted composite of peg, SLP fill, jubilee, buy composition, and exit-pressure.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={60} />
      </header>

      {/* Composite score */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 sm:gap-6 mb-4 sm:mb-6 items-center">
        <div className="md:col-span-1">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Composite
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`num text-6xl sm:text-7xl font-semibold ${tier.text}`}>{data.composite_score}</span>
            <span className="num text-xl sm:text-2xl text-text-muted">/ 100</span>
          </div>
          <div
            className={`inline-flex items-center mt-2 px-2 py-0.5 rounded border ${tier.border} ${tier.bg} ${tier.text} text-xs font-mono uppercase tracking-wider`}
          >
            {tier.label}
          </div>
        </div>
        <div className="md:col-span-2">
          <p className="text-text leading-relaxed">{data.headline}</p>
          <div className="mt-4 relative">
            <div className="h-3 bg-bg rounded overflow-hidden border border-border">
              <div className={`h-full ${tier.bar}`} style={{ width: `${data.composite_score}%` }} />
            </div>
            {/* Tier-boundary tick marks at 35%, 65%, 85% (per methodology) */}
            <div
              className="absolute top-0 h-3 w-px bg-text-dim/50"
              style={{ left: '35%' }}
            />
            <div
              className="absolute top-0 h-3 w-px bg-text-dim/50"
              style={{ left: '65%' }}
            />
            <div
              className="absolute top-0 h-3 w-px bg-text-dim/50"
              style={{ left: '85%' }}
            />
          </div>
          <div className="relative h-4 mt-1.5 text-[10px] font-mono text-text-dim">
            <span className="absolute left-0">0 critical</span>
            <span
              className="absolute"
              style={{ left: '35%', transform: 'translateX(-50%)' }}
            >
              35
            </span>
            <span
              className="absolute"
              style={{ left: '65%', transform: 'translateX(-50%)' }}
            >
              65
            </span>
            <span
              className="absolute"
              style={{ left: '85%', transform: 'translateX(-50%)' }}
            >
              85
            </span>
            <span className="absolute right-0">100 recovered</span>
          </div>
        </div>
      </div>

      {/* Subscore grid */}
      <div className="border-t border-border pt-4">
        <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-3">
          Subscores (weighted)
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {data.subscores.map((s) => {
            const c = subscoreColor(s.score)
            return (
              <div key={s.id} className="border border-border rounded p-3 bg-surface">
                <div className="flex items-baseline justify-between gap-1 mb-1">
                  <span className="text-text-dim text-[10px] uppercase font-mono tracking-wider truncate">
                    {s.label}
                  </span>
                  <span className="num text-[10px] text-text-dim">{(s.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-baseline gap-1.5 mb-2">
                  <span className={`num text-2xl font-semibold ${c.text}`}>{s.score}</span>
                  <span className="num text-xs text-text-muted">/ 100</span>
                </div>
                <div className="h-1 bg-bg rounded overflow-hidden mb-2">
                  <div className={`h-full ${c.bar}`} style={{ width: `${s.score}%` }} />
                </div>
                <div className="text-[11px] text-text-muted leading-snug">{s.value_text}</div>
                <div className="text-[10px] text-text-dim mt-1.5 italic leading-snug">{s.method}</div>
              </div>
            )
          })}
        </div>
      </div>

    </section>
  )
}
