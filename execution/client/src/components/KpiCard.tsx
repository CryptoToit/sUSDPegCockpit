import type { KpiItem, KpiStatus } from '../types'
import { formatUSD } from '../lib/format'

const VELOCITY_STYLES: Record<
  NonNullable<KpiItem['velocity']>['tier'],
  { text: string; bg: string; border: string; label: string }
> = {
  ahead: { text: 'text-ok', bg: 'bg-ok/10', border: 'border-ok/30', label: 'AHEAD' },
  on_track: { text: 'text-ok', bg: 'bg-ok/10', border: 'border-ok/30', label: 'ON TRACK' },
  behind: { text: 'text-warn', bg: 'bg-warn/10', border: 'border-warn/30', label: 'BEHIND' },
  far_behind: { text: 'text-danger', bg: 'bg-danger/10', border: 'border-danger/30', label: 'FAR BEHIND' },
}

const STATUS_STYLES: Record<
  KpiStatus,
  { text: string; bg: string; border: string; label: string }
> = {
  verified: { text: 'text-ok', bg: 'bg-ok/10', border: 'border-ok/40', label: 'VERIFIED' },
  stub: { text: 'text-warn', bg: 'bg-warn/10', border: 'border-warn/40', label: 'STUB' },
  closed: { text: 'text-text-dim', bg: 'bg-surface-2', border: 'border-border', label: 'BETWEEN SEASONS' },
  context: { text: 'text-text-muted', bg: 'bg-surface-2', border: 'border-border', label: 'CONTEXT' },
}

export default function KpiCard({ kpi }: { kpi: KpiItem }) {
  const isNumeric = typeof kpi.actual === 'number' && (typeof kpi.target === 'number' || kpi.target === null)
  const pct =
    isNumeric && typeof kpi.target === 'number' && kpi.target > 0
      ? Math.min(100, ((kpi.actual as number) / (kpi.target as number)) * 100)
      : null

  const showVelocity = kpi.velocity && kpi.status !== 'closed'
  const v = showVelocity ? kpi.velocity : null
  const vStyles = v ? VELOCITY_STYLES[v.tier] : null
  const paceRatio =
    v && v.required_daily_pace > 0 ? (v.current_daily_pace / v.required_daily_pace) * 100 : null

  const sStyles = kpi.status ? STATUS_STYLES[kpi.status] : null

  return (
    <div className="border border-border rounded p-4 bg-surface-2">
      <div className="flex items-start justify-between gap-2 mb-1">
        <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider flex-1 min-w-0">
          {kpi.label}
        </div>
        {sStyles && (
          <span
            className={`shrink-0 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${sStyles.text} ${sStyles.bg} ${sStyles.border}`}
          >
            {sStyles.label}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <div className="num text-2xl font-semibold text-text">
          {kpi.unit === 'USD' && typeof kpi.actual === 'number' ? '$' : ''}
          {typeof kpi.actual === 'number' ? formatUSD(kpi.actual, { compact: true }) : kpi.actual}
        </div>
        {typeof kpi.target === 'number' && (
          <div className="text-text-muted text-xs num">/ ${formatUSD(kpi.target, { compact: true })}</div>
        )}
        {typeof kpi.target === 'string' && kpi.target !== kpi.actual && (
          <div className="text-text-muted text-xs">/ {kpi.target}</div>
        )}
      </div>
      {pct !== null && (
        <>
          <div className="h-1 bg-bg rounded overflow-hidden mb-1">
            <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
          <div className="flex justify-between text-[10px] text-text-muted font-mono">
            <span>{pct.toFixed(0)}% complete</span>
            {kpi.deadline && <span>by {kpi.deadline}</span>}
          </div>
        </>
      )}
      {v && vStyles && (
        <div className="mt-3 pt-3 border-t border-border/60">
          <div className="flex items-baseline justify-between mb-1.5 gap-2">
            <span
              className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${vStyles.text} ${vStyles.bg} ${vStyles.border}`}
            >
              {vStyles.label}
            </span>
            <span className="text-[10px] num text-text-dim">{v.days_remaining}d remaining</span>
          </div>
          <div className="text-[11px] num text-text-muted leading-relaxed">
            <div className="flex justify-between">
              <span>need:</span>
              <span className="text-text">${formatUSD(v.required_daily_pace, { compact: true })}/day</span>
            </div>
            <div className="flex justify-between">
              <span>current:</span>
              <span className={vStyles.text}>
                ${formatUSD(v.current_daily_pace, { compact: true })}/day
                {paceRatio !== null && ` (${paceRatio.toFixed(0)}%)`}
              </span>
            </div>
          </div>
        </div>
      )}
      {kpi.note && (
        <div className="mt-2 pt-2 border-t border-border/40 text-[10px] text-text-dim italic leading-snug">
          {kpi.note}
        </div>
      )}
    </div>
  )
}
