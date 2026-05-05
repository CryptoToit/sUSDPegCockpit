import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { NftQueueSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'

const ETHERSCAN_TX = (chain: string, hash: string) =>
  chain === 'ethereum'
    ? `https://etherscan.io/tx/${hash}`
    : `https://optimistic.etherscan.io/tx/${hash}`

const ETHERSCAN_ADDR = (chain: string, addr: string) =>
  chain === 'ethereum'
    ? `https://etherscan.io/address/${addr}`
    : `https://optimistic.etherscan.io/address/${addr}`

export default function UnstakeQueue() {
  const [data, setData] = useState<NftQueueSnapshot | null>(null)
  const [showRecent, setShowRecent] = useState(false)
  useEffect(() => {
    snapshots.nftQueue().then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="text-text-dim p-6">Loading unstake queue…</div>

  const eth = data.chains.ethereum
  const op = data.chains.optimism
  const ethCustody = data.custody_count.ethereum ?? 0
  const opCustody = data.custody_count.optimism ?? 0
  const rate7d = data.total_nfts_in_7d / 7
  const rate24h = data.total_nfts_in_24h
  const accelerating = rate24h > rate7d * 1.25
  const decelerating = rate24h < rate7d * 0.75

  return (
    <section id="queue" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">Unstake Queue</h2>
          <p className="text-text-dim text-sm">
            Live count of Synthetix Account NFTs (<code className="text-text-muted">SACCT</code>)
            currently held by the council/Treasury wallet at{' '}
            <code className="text-text-muted">0xebAC8…d</code>. Stakers transfer their Account NFT
            to the council to unstake; the council manually returns SNX/sUSD off-chain. Custody is
            the live snapshot via{' '}
            <code className="text-text-muted">SACCT.balanceOf(council)</code>; inflow is from
            Transfer-event scans. USD valuation requires v2x integration — these positions return
            zero on v3 collateral reads, confirming legacy v2x staking. Order-of-magnitude estimate
            ~$0.5M–1M based on average Synthetix v2x position size.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-accent/40 rounded p-4 bg-accent/5">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Council custody (now)
          </div>
          <div className="num text-3xl sm:text-4xl font-semibold mt-1">
            {data.total_custody_count}
          </div>
          <div className="text-text-muted text-xs mt-1">
            ETH {ethCustody} · OP {opCustody}
            <span className="block mt-0.5 text-text-dim">NFTs awaiting manual processing</span>
          </div>
        </div>
        <div className="border border-border rounded p-4 bg-surface-2">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            7-day inflow
          </div>
          <div className="num text-3xl font-semibold mt-1">{data.total_nfts_in_7d}</div>
          <div className="text-text-muted text-xs mt-1">
            ETH {eth.nfts_in_7d} · OP {op.nfts_in_7d}
            <span className="block mt-0.5 num">≈ {rate7d.toFixed(1)} / day</span>
          </div>
        </div>
        <div className="border border-border rounded p-4 bg-surface-2">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            24-hour inflow
          </div>
          <div
            className={`num text-3xl font-semibold mt-1 ${
              accelerating ? 'text-warn' : decelerating ? 'text-ok' : ''
            }`}
          >
            {data.total_nfts_in_24h}
          </div>
          <div className="text-text-muted text-xs mt-1">
            ETH {eth.nfts_in_24h} · OP {op.nfts_in_24h}
            <span className="block mt-0.5">
              {accelerating
                ? 'pace accelerating vs 7d avg'
                : decelerating
                ? 'pace easing vs 7d avg'
                : 'pace in line with 7d avg'}
            </span>
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setShowRecent((v) => !v)}
        className="mt-4 text-[11px] font-mono uppercase tracking-wider text-text-muted hover:text-accent transition flex items-center gap-1.5"
        aria-expanded={showRecent}
      >
        <span>{showRecent ? '▾' : '▸'}</span>
        {showRecent ? 'Hide' : 'Show'} recent inbound ({data.recent_inbound.length})
      </button>

      {showRecent && (
        <div className="border border-border rounded bg-surface-2 overflow-hidden mt-2">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-text-dim font-mono uppercase tracking-wider text-[10px]">
                <tr className="border-b border-border">
                  <th className="text-left px-3 py-2">Chain</th>
                  <th className="text-left px-3 py-2">Block</th>
                  <th className="text-left px-3 py-2">From</th>
                  <th className="text-left px-3 py-2">Token ID</th>
                  <th className="text-left px-3 py-2">Tx</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_inbound.map((e) => (
                  <tr key={e.tx_hash} className="border-b border-border/50 last:border-0">
                    <td className="px-3 py-1.5 num">
                      {e.chain === 'ethereum' ? 'ETH' : 'OP'}
                    </td>
                    <td className="px-3 py-1.5 num text-text-muted">
                      {e.block_number.toLocaleString()}
                    </td>
                    <td className="px-3 py-1.5 num">
                      <a
                        href={ETHERSCAN_ADDR(e.chain, e.from_address)}
                        target="_blank"
                        rel="noopener"
                        className="hover:text-accent transition"
                      >
                        {e.from_address.slice(0, 6)}…{e.from_address.slice(-4)}
                      </a>
                    </td>
                    <td className="px-3 py-1.5 num text-text-muted">
                      {e.token_id.length > 10 ? `${e.token_id.slice(0, 10)}…` : e.token_id}
                    </td>
                    <td className="px-3 py-1.5">
                      <a
                        href={ETHERSCAN_TX(e.chain, e.tx_hash)}
                        target="_blank"
                        rel="noopener"
                        className="text-accent hover:underline num"
                      >
                        {e.tx_hash.slice(0, 10)}…
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
