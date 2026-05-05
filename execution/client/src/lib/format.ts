/**
 * USD formatter.
 *
 *   `compact: true` → Intl compact notation (e.g. "$1.5K", "$2.3M").
 *     `compactDigits` controls fraction digits; default 1 (e.g. "$14.1K"). Use
 *     2 (e.g. "$14.08K") when displaying multiple values that should visibly
 *     sum to a precise total — at 1 decimal each, rounded values drift and
 *     readers see (e.g.) "14.1K + 4.0K + 9.8K + 2.5K + 2.0K = 32.4K" against
 *     a "32.3K" headline.
 *
 *   `compact: false` (default) → fixed-decimal formatted with thousands
 *     separators (e.g. "$14,082").
 */
export function formatUSD(
  n: number,
  opts: { compact?: boolean; decimals?: number; compactDigits?: number } = {},
): string {
  const { compact = false, decimals = 0, compactDigits = 1 } = opts
  if (compact) {
    return new Intl.NumberFormat('en-US', {
      notation: 'compact',
      maximumFractionDigits: compactDigits,
    }).format(n)
  }
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function formatPrice(n: number): string {
  return n.toFixed(4)
}

export function formatBp(n: number): string {
  const sign = n >= 0 ? '+' : ''
  return `${sign}${n} bp`
}

export function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const min = Math.floor(ms / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

export function staleClass(asOf: string, budgetMin: number): 'fresh' | 'stale' | 'dead' {
  const min = (Date.now() - new Date(asOf).getTime()) / 60000
  if (min < budgetMin) return 'fresh'
  if (min < budgetMin * 2) return 'stale'
  return 'dead'
}
