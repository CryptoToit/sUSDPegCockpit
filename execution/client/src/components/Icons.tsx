/**
 * Brand icons for chains and DEXes.
 * Sources: DefiLlama icon CDN (https://icons.llamao.fi/), bundled to /public/icons/
 * so the dashboard stays self-contained for Phase C (IPFS deploy).
 */

const CHAIN_LABELS: Record<string, string> = {
  ethereum: 'Ethereum',
  optimism: 'Optimism',
}

const DEX_LABELS: Record<string, string> = {
  curve: 'Curve',
  velodrome: 'Velodrome',
  uniswap: 'Uniswap',
  balancer: 'Balancer',
  sushiswap: 'Sushiswap',
}

function chainSlug(chain: string): string | null {
  const k = chain.toLowerCase()
  return CHAIN_LABELS[k] ? k : null
}

function dexSlug(dex: string): string | null {
  const k = dex.toLowerCase()
  return DEX_LABELS[k] ? k : null
}

export function ChainIcon({
  chain,
  size = 16,
  className = '',
}: {
  chain: string
  size?: number
  className?: string
}) {
  const slug = chainSlug(chain)
  if (!slug) return null
  return (
    <img
      src={`/icons/chains/${slug}.webp`}
      alt={CHAIN_LABELS[slug]}
      width={size}
      height={size}
      loading="lazy"
      className={`inline-block rounded-full bg-white/5 ${className}`}
    />
  )
}

export function DexIcon({
  dex,
  size = 20,
  className = '',
}: {
  dex: string
  size?: number
  className?: string
}) {
  const slug = dexSlug(dex)
  if (!slug) return null
  return (
    <img
      src={`/icons/protocols/${slug}.webp`}
      alt={DEX_LABELS[slug]}
      width={size}
      height={size}
      loading="lazy"
      className={`inline-block rounded ${className}`}
    />
  )
}

/**
 * Stacked glyph: DEX icon with a small chain badge in the bottom-right corner.
 * Matches the standard DeFi UI pattern (DefiLlama, Etherscan, etc.).
 */
export function VenueGlyph({
  dex,
  chain,
  size = 32,
}: {
  dex: string
  chain: string
  size?: number
}) {
  const badge = Math.max(12, Math.round(size * 0.42))
  return (
    <div className="relative inline-block flex-shrink-0" style={{ width: size, height: size }}>
      <DexIcon dex={dex} size={size} />
      <span
        className="absolute -right-1 -bottom-1 ring-2 ring-surface rounded-full bg-surface"
        style={{ width: badge, height: badge }}
      >
        <ChainIcon chain={chain} size={badge} />
      </span>
    </div>
  )
}

/**
 * Chains where the legacy Synthetix sUSD ERC-20 has meaningful supply.
 * Note: Synthetix v3 deployments to Base/Arbitrum use a different token
 * (snxUSD / USDx), NOT legacy sUSD — and this dashboard tracks legacy
 * sUSD only (the depegged one). Source of truth for chain set:
 * https://stablecoins.llama.fi/stablecoin/22 (DefiLlama sUSD).
 */
export const SUPPORTED_CHAINS: Array<{ slug: string; label: string }> = [
  { slug: 'ethereum', label: 'Ethereum' },
  { slug: 'optimism', label: 'Optimism' },
]
