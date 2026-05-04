import { staleClass, timeAgo } from '../lib/format'

export default function FreshnessBadge({ as_of, budget_min }: { as_of: string; budget_min: number }) {
  const cls = staleClass(as_of, budget_min)
  const color =
    cls === 'fresh'
      ? 'text-ok bg-ok/10 border-ok/30'
      : cls === 'stale'
      ? 'text-warn bg-warn/10 border-warn/30'
      : 'text-danger bg-danger/10 border-danger/30'
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${color}`}
    >
      <span className="inline-block w-1.5 h-1.5 rounded-full bg-current"></span>
      {timeAgo(as_of)}
    </span>
  )
}
