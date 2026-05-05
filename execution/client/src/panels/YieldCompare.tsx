import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { YieldSnapshot, YieldStatus, YieldVenue } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'

// Distinct color per status so the chip and APR bar tell the same story at a
// glance. Bar fill uses `barClass` (matched to the chip color); `barOpacity`
// modulates how prominent the row reads relative to active programs.
const STATUS_STYLES: Record<
  YieldStatus,
  {
    text: string
    bg: string
    border: string
    label: string
    barClass: string
    barOpacity: string
  }
> = {
  active: {
    // Green — actually-realized yields (Infinex, Curve LP).
    text: 'text-ok',
    bg: 'bg-ok/10',
    border: 'border-ok/40',
    label: 'LIVE',
    barClass: 'bg-ok/70',
    barOpacity: 'opacity-100',
  },
  theoretical: {
    // Blue — theoretical / model-implied yields (buy-and-hold-to-peg, burn-to-debt).
    // Distinct from green (realized) and from violet (in-release) so the viewer
    // can tell at a glance which rows are "real returns" vs "if-X-then-Y" math.
    text: 'text-sky-300',
    bg: 'bg-sky-500/10',
    border: 'border-sky-400/50',
    label: 'IMPLIED',
    barClass: 'bg-sky-500/60',
    barOpacity: 'opacity-100',
  },
  closed: {
    // Amber — program is closed but still relevant.
    text: 'text-warn',
    bg: 'bg-warn/10',
    border: 'border-warn/40',
    label: 'CLOSED',
    barClass: 'bg-warn/70',
    barOpacity: 'opacity-60',
  },
  vesting_only: {
    // Violet — actively distributing rewards in a time-bounded release window.
    // Distinct from green (open-ended live) and amber (closed) — reads as
    // "live but time-limited."
    text: 'text-violet-300',
    bg: 'bg-violet-500/15',
    border: 'border-violet-400/50',
    label: 'IN RELEASE',
    barClass: 'bg-violet-500/70',
    barOpacity: 'opacity-100',
  },
  inactive_program: {
    // Gray — fully wound down.
    text: 'text-text-dim',
    bg: 'bg-surface-2',
    border: 'border-border',
    label: 'ENDED',
    barClass: 'bg-text-dim/40',
    barOpacity: 'opacity-30',
  },
}

const STATUS_ORDER: YieldStatus[] = [
  'active',
  'theoretical',
  'closed',
  'vesting_only',
  'inactive_program',
]

function venueApr(v: YieldVenue): number {
  return v.apr_pct ?? v.apr_pct_implied ?? 0
}

export default function YieldCompare() {
  const [data, setData] = useState<YieldSnapshot | null>(null)
  useEffect(() => {
    snapshots.yields().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading yields…</div>

  const sorted = [...data.venues].sort((a, b) => {
    const aIdx = STATUS_ORDER.indexOf(a.status ?? 'active')
    const bIdx = STATUS_ORDER.indexOf(b.status ?? 'active')
    if (aIdx !== bIdx) return aIdx - bIdx
    return venueApr(b) - venueApr(a)
  })

  const max = Math.max(...sorted.map(venueApr))

  return (
    <section id="yield" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold flex items-center">
            Stakeholder Yield Compare
            <InfoPopover label="Yield Compare methodology">
              <p>
                Where sUSD holders can park, earn, or otherwise benefit — sorted by program
                status (active first).
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Implied yields</strong> (e.g. buy &amp; hold
                to peg, debt-burn) are model outputs, not realized returns.
              </p>
              <p className="mt-2">
                Status legend:{' '}
                <span className="text-ok">LIVE</span> realized yield, open ·{' '}
                <span className="text-sky-300">IMPLIED</span> theoretical model ·{' '}
                <span className="text-violet-300">IN RELEASE</span> live distribution in a
                time-bounded window ·{' '}
                <span className="text-warn">CLOSED</span> not taking new deposits ·{' '}
                <span className="text-text-dim">ENDED</span> program complete.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            Where sUSD holders can park, earn, or benefit — sorted by status.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={60} />
      </header>

      <div className="space-y-3">
        {sorted.map((v) => {
          const apr = venueApr(v)
          const aprAvailable = v.apr_pct !== undefined || v.apr_pct_implied !== undefined
          const pct = max > 0 && aprAvailable ? (apr / max) * 100 : 0
          const isImplied = v.apr_pct_implied !== undefined
          const status = v.status ?? 'active'
          const styles = STATUS_STYLES[status]
          return (
            <div key={v.id} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
              <div className="md:col-span-3">
                <div className="font-medium leading-snug">{v.label}</div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span
                    className={`shrink-0 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${styles.text} ${styles.bg} ${styles.border}`}
                  >
                    {styles.label}
                  </span>
                  {v.audience && (
                    <span className="text-text-muted text-[10px] font-mono uppercase tracking-wider truncate">
                      {v.audience}
                    </span>
                  )}
                </div>
                <div className="text-text-dim text-xs mt-1">{v.lock}</div>
              </div>
              <div className="md:col-span-7">
                <div className="h-7 bg-surface-2 rounded overflow-hidden relative border border-border">
                  <div
                    className={`h-full ${styles.barClass} ${styles.barOpacity}`}
                    style={{ width: `${pct}%` }}
                  />
                  <div className="absolute inset-0 flex items-center px-3 text-xs">
                    {aprAvailable ? (
                      <>
                        <span className="num font-semibold">{apr.toFixed(1)}%</span>
                        {isImplied && (
                          <span className="ml-2 text-[10px] uppercase tracking-wider text-text-muted font-mono">
                            implied
                          </span>
                        )}
                        {v.apr_unverified && (
                          <span className="ml-2 text-[10px] uppercase tracking-wider text-warn font-mono border border-warn/40 bg-warn/10 px-1 rounded">
                            stub
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-text-muted text-[10px] uppercase tracking-wider font-mono">
                        APR not announced
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="md:col-span-2 text-text-dim text-xs flex items-start gap-1 leading-snug">
                <span className="flex-1 min-w-0">{v.summary ?? v.risk_note}</span>
                <InfoPopover
                  label={`${v.label} — methodology`}
                  align="right"
                  size="sm"
                >
                  <p className="font-semibold text-text mb-1.5">{v.label}</p>
                  <p>{v.risk_note}</p>
                </InfoPopover>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
