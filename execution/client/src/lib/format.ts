export function formatUSD(n: number, opts: { compact?: boolean; decimals?: number } = {}): string {
  const { compact = false, decimals = 0 } = opts
  if (compact) {
    return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
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
