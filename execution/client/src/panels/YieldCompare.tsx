import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { YieldSnapshot, YieldStatus, YieldVenue } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'

const STATUS_STYLES: Record<
  YieldStatus,
  { text: string; bg: string; border: string; label: string; barOpacity: string }
> = {
  active: {
    text: 'text-ok',
    bg: 'bg-ok/10',
    border: 'border-ok/40',
    label: 'LIVE',
    barOpacity: 'opacity-100',
  },
  theoretical: {
    text: 'text-accent',
    bg: 'bg-accent/10',
    border: 'border-accent/40',
    label: 'IMPLIED',
    barOpacity: 'opacity-90',
  },
  closed: {
    text: 'text-warn',
    bg: 'bg-warn/10',
    border: 'border-warn/40',
    label: 'CLOSED',
    barOpacity: 'opacity-50',
  },
  vesting_only: {
    text: 'text-text-dim',
    bg: 'bg-surface-2',
    border: 'border-border',
    label: 'VESTING',
    barOpacity: 'opacity-30',
  },
  inactive_program: {
    text: 'text-text-dim',
    bg: 'bg-surface-2',
    border: 'border-border',
    label: 'ENDED',
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
                Status legend: <span className="text-ok">LIVE</span> taking deposits ·{' '}
                <span className="text-accent">IMPLIED</span> theoretical model ·{' '}
                <span className="text-warn">CLOSED</span> not taking new deposits ·{' '}
                <span className="text-text-dim">VESTING</span> ended with rewards still
                unlocking · <span className="text-text-dim">ENDED</span> program complete.
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
                    className={`h-full ${isImplied ? 'bg-accent/40 border-r border-accent' : 'bg-accent/70'} ${styles.barOpacity}`}
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
                      </>
                    ) : (
                      <span className="text-text-muted text-[10px] uppercase tracking-wider font-mono">
                        APR not announced
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="md:col-span-2 text-text-dim text-xs">{v.risk_note}</div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
