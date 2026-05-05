import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { NftQueueSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import InfoPopover from '../components/InfoPopover'
import { formatUSD } from '../lib/format'

const ETHERSCAN_TX = (chain: string, hash: string) =>
  chain === 'ethereum'
    ? `https://etherscan.io/tx/${hash}`
    : `https://optimistic.etherscan.io/tx/${hash}`

const ETHERSCAN_ADDR = (chain: string, addr: string) =>
  chain === 'ethereum'
    ? `https://etherscan.io/address/${addr}`
    : `https://optimistic.etherscan.io/address/${addr}`

// === Time anchors that frame the Unstake Queue ===
// Lockup ended on 2026-04-19 (5M-SNX rewards program). Before this, stakers
// could not unstake — queue was structurally near-zero. Today's custody is
// post-unlock accumulation working through manual processing.
const LOCKUP_END = new Date('2026-04-19T00:00:00Z')
// Linear release of 5M SNX rewards runs 3 months from lockup-end. Stakers
// have a financial incentive to delay exit until the window closes.
const RELEASE_END = new Date('2026-07-19T00:00:00Z')
// SLP Vault expected launch (Synthetix team confirmed Q2 2026). New sUSD sink
// — may absorb stakers exiting the 420 Pool rather than them selling on market.
const SLP_LAUNCH_TARGET = new Date('2026-06-30T00:00:00Z')

function daysBetween(from: Date, to: Date): number {
  return Math.round((to.getTime() - from.getTime()) / (24 * 60 * 60 * 1000))
}

function relativeDays(target: Date): { days: number; phrase: string } {
  const now = new Date()
  const days = daysBetween(now, target)
  if (days < 0) return { days, phrase: `${-days} days ago` }
  if (days === 0) return { days, phrase: 'today' }
  return { days, phrase: `~${days} days from now` }
}

function fmtDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

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
  const ethValuation = data.valuation?.ethereum
  const opValuation = data.valuation?.optimism
  const ethValueUsd = ethValuation?.estimated_usd ?? 0
  const opValueUsd = opValuation?.estimated_usd ?? 0
  const totalValueUsd = data.total_estimated_usd ?? 0
  const ethDisbSnx = data.disbursements?.ethereum?.SNX
  const opDisbSnx = data.disbursements?.optimism?.SNX
  const ethDisbSusd = data.disbursements?.ethereum?.sUSD
  const valuationAvailable = totalValueUsd > 0
  const ethLag = data.lag?.ethereum
  const opLag = data.lag?.optimism
  const lagAvailable = (data.total_lag_sample_n ?? 0) > 0
  const ethPendingShare =
    ethLag && ethLag.sample_n + ethLag.pending_count > 0
      ? ethLag.pending_count / (ethLag.sample_n + ethLag.pending_count)
      : 0
  const opPendingShare =
    opLag && opLag.sample_n + opLag.pending_count > 0
      ? opLag.pending_count / (opLag.sample_n + opLag.pending_count)
      : 0
  const formatHours = (h: number) =>
    h >= 24 ? `${(h / 24).toFixed(1)}d` : `${h.toFixed(1)}h`
  const sellShare = data.total_sell_share ?? 0
  const sellShareAvailable =
    (data.total_usd_received ?? 0) > 0 || Object.keys(data.post_release ?? {}).length > 0
  const ethPost = data.post_release?.ethereum
  const opPost = data.post_release?.optimism

  // Time-anchor context (computed at render so the "Day N of M" counters tick
  // forward without needing to redeploy or re-snapshot).
  const now = new Date()
  const releaseWindowDays = daysBetween(LOCKUP_END, RELEASE_END)
  const dayInRelease = Math.max(0, daysBetween(LOCKUP_END, now))
  const inReleaseWindow = now >= LOCKUP_END && now <= RELEASE_END
  const lockupRel = relativeDays(LOCKUP_END)
  const releaseRel = relativeDays(RELEASE_END)
  const slpRel = relativeDays(SLP_LAUNCH_TARGET)

  return (
    <section id="queue" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold flex items-center">
            Unstake Queue
            <InfoPopover label="Unstake Queue methodology">
              <p>
                Stakers transfer their Synthetix Account NFT (SACCT) to the council/Treasury wallet
                at <code className="text-text-muted">0xebAC8…d</code> to exit; the council manually
                returns SNX/sUSD off-chain.
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Custody:</strong> live{' '}
                <code className="text-text-muted">SACCT.balanceOf(council)</code> on both chains.{' '}
                <strong className="text-text-muted">Inflow:</strong> SACCT Transfer-event scans
                (24h / 7d / 30d windows).
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Estimated value:</strong> per-chain pending
                count split by historical SNX-vs-sUSD processing mix (180d, internal Treasury
                shuffles filtered), priced at mean disbursement × current SNX spot (DefiLlama).
                Order-of-magnitude only — precise per-NFT value would need v2x state reads.
              </p>
            </InfoPopover>
          </h2>
          <p className="text-text-dim text-sm">
            Stakers' positions queued for manual processing by the Synthetix council.
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      {/* Time-anchor context strip — kept compact: just the headline regime line
          + a compact dates row, with full anchor descriptions behind the (i). */}
      <div className="mb-4 border border-accent/30 bg-accent/5 rounded px-3 py-2 flex items-baseline justify-between gap-3 flex-wrap">
        <div className="text-sm leading-snug">
          {inReleaseWindow ? (
            <>
              <span className="font-semibold num">
                Day {dayInRelease} of ~{releaseWindowDays}
              </span>{' '}
              in the 5M-SNX linear release window
              <InfoPopover label="Time-anchor context" align="left">
                <div className="text-sm font-semibold text-text mb-1.5">
                  Why these dates matter
                </div>
                <ul className="space-y-2 num">
                  <li>
                    <span className="text-text-muted">Lockup ended:</span>{' '}
                    <span className="text-text">{fmtDate(LOCKUP_END)}</span>{' '}
                    <span className="text-text-dim">({lockupRel.phrase})</span>
                    <div className="text-text-dim mt-0.5">
                      Before this, stakers couldn't unstake — queue was near-zero by design.
                    </div>
                  </li>
                  <li>
                    <span className="text-text-muted">Release window ends:</span>{' '}
                    <span className="text-text">~{fmtDate(RELEASE_END)}</span>{' '}
                    <span className="text-text-dim">({releaseRel.phrase})</span>
                    <div className="text-text-dim mt-0.5">
                      The 5M SNX rewards distribute linearly over 3 months. Stakers have a
                      financial incentive to delay exit; inflow may accelerate as the window
                      closes.
                    </div>
                  </li>
                  <li>
                    <span className="text-text-muted">SLP Vault expected:</span>{' '}
                    <span className="text-text">~{fmtDate(SLP_LAUNCH_TARGET)}</span>{' '}
                    <span className="text-text-dim">({slpRel.phrase})</span>
                    <div className="text-text-dim mt-0.5">
                      A new sUSD sink contract. Potential re-absorption path: 420 Pool exits
                      may migrate to SLP rather than become market sell pressure.
                    </div>
                  </li>
                </ul>
              </InfoPopover>
            </>
          ) : now < LOCKUP_END ? (
            <span>5M-SNX program lockup hasn't ended yet — queue near-zero by design.</span>
          ) : (
            <span>5M-SNX release window has ended.</span>
          )}
        </div>
        <div className="text-[11px] num text-text-dim flex flex-wrap gap-x-3">
          <span>
            unlock <span className="text-text-muted">{fmtDate(LOCKUP_END)}</span>
          </span>
          <span>
            release end <span className="text-text-muted">~{fmtDate(RELEASE_END)}</span>
          </span>
          <span>
            SLP <span className="text-text-muted">~{fmtDate(SLP_LAUNCH_TARGET)}</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4">
        <div className="border border-accent/40 rounded p-4 bg-accent/5">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Council custody (now)
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1">
            {data.total_custody_count}
          </div>
          <div className="text-text-muted text-xs mt-1">
            ETH {ethCustody} · OP {opCustody}
            <span className="block mt-0.5 text-text-dim">NFTs pending</span>
          </div>
        </div>
        <div className="border border-accent/40 rounded p-4 bg-accent/5">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Estimated value
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1">
            {valuationAvailable ? `$${formatUSD(totalValueUsd, { compact: true })}` : '—'}
          </div>
          <div className="text-text-muted text-xs mt-1">
            {valuationAvailable ? (
              <>
                ETH ${formatUSD(ethValueUsd, { compact: true })} · OP $
                {formatUSD(opValueUsd, { compact: true })}
                <span className="block mt-0.5 text-text-dim num">
                  @ SNX ${data.snx_price_usd.toFixed(3)}
                </span>
              </>
            ) : (
              <span className="text-text-dim">awaiting disbursement-history scan</span>
            )}
          </div>
        </div>
        <div className="border border-accent/40 rounded p-4 bg-accent/5">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Median processing lag
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1">
            {lagAvailable ? formatHours(data.weighted_median_lag_hours) : '—'}
          </div>
          <div className="text-text-muted text-xs mt-1">
            {lagAvailable ? (
              <>
                ETH {ethLag ? formatHours(ethLag.median_hours) : '—'} · OP{' '}
                {opLag ? formatHours(opLag.median_hours) : '—'}
                <span className="block mt-0.5 num">
                  n={data.total_lag_sample_n} pairs · {data.total_lag_pending_count} pending
                </span>
              </>
            ) : (
              <span className="text-text-dim">awaiting EOA pairing scan</span>
            )}
          </div>
        </div>
        <div className="border border-border rounded p-4 bg-surface-2">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            7-day inflow
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1">{data.total_nfts_in_7d}</div>
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
            className={`num text-2xl sm:text-3xl font-semibold mt-1 ${
              accelerating ? 'text-warn' : decelerating ? 'text-ok' : ''
            }`}
          >
            {data.total_nfts_in_24h}
          </div>
          <div className="text-text-muted text-xs mt-1">
            ETH {eth.nfts_in_24h} · OP {op.nfts_in_24h}
            <span className="block mt-0.5">
              {accelerating
                ? 'accelerating vs 7d'
                : decelerating
                ? 'easing vs 7d'
                : 'in line with 7d'}
            </span>
          </div>
        </div>
        <div
          className={`border rounded p-4 ${
            sellShare >= 0.3
              ? 'border-danger/40 bg-danger/5'
              : sellShare >= 0.1
              ? 'border-warn/40 bg-warn/5'
              : 'border-ok/40 bg-ok/5'
          }`}
        >
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Observed sell-through
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1">
            {sellShareAvailable ? `${(sellShare * 100).toFixed(1)}%` : '—'}
          </div>
          <div className="text-text-muted text-xs mt-1">
            {sellShareAvailable ? (
              <>
                ${formatUSD(data.total_usd_to_dex, { compact: true })} of $
                {formatUSD(data.total_usd_received, { compact: true })}
                <span className="block mt-0.5 text-text-dim">to known sell routes (180d)</span>
              </>
            ) : (
              <span className="text-text-dim">awaiting recipient scan</span>
            )}
          </div>
        </div>
      </div>

      {sellShareAvailable && (
        <div className="mt-4 border border-border rounded p-3 bg-surface-2 text-xs">
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1 flex items-baseline">
            Post-release sell-through (180d)
            <InfoPopover label="Sell-through methodology" align="right">
              <p>
                For each council disbursement recipient, we scan their subsequent token transfers
                and tally any SNX/sUSD outflows to known sell-route addresses (DEX routers + major
                sUSD/SNX pools + tagged CEX hot wallets + bridges).
              </p>
              <p className="mt-2">
                <strong className="text-text-muted">Lower bound caveat:</strong> we miss outflows
                to smaller exchanges, OTC desks, untagged CEX wallets, contract-wallet swaps, and
                bridge-then-sell flows. A near-zero reading means "no observed dump via curated
                routes" — it does NOT prove holding. Read directionally over time.
              </p>
            </InfoPopover>
          </div>
          <div className="num text-text">
            ETH: ${formatUSD(ethPost?.usd_to_dex ?? 0, { compact: true })} of $
            {formatUSD(ethPost?.usd_received ?? 0, { compact: true })}{' '}
            <span className="text-text-dim">
              ({ethPost?.recipients_scanned ?? 0} recipients)
            </span>
            <span className="mx-2 text-text-dim">·</span>
            OP: ${formatUSD(opPost?.usd_to_dex ?? 0, { compact: true })} of $
            {formatUSD(opPost?.usd_received ?? 0, { compact: true })}{' '}
            <span className="text-text-dim">
              ({opPost?.recipients_scanned ?? 0} recipients)
            </span>
          </div>
        </div>
      )}

      {lagAvailable && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
          <div
            className={`border rounded p-3 ${
              ethPendingShare >= 0.85
                ? 'border-danger/40 bg-danger/5'
                : ethPendingShare >= 0.6
                ? 'border-warn/40 bg-warn/5'
                : 'border-border bg-surface-2'
            }`}
          >
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Mainnet — processing distribution (180d)
            </div>
            {ethLag && (
              <div className="num leading-relaxed">
                <span className="font-semibold">{ethLag.sample_n}</span> completed pairs ·{' '}
                <span className="font-semibold">{ethLag.pending_count}</span> pending
                <span className="text-text-muted">
                  {' '}({(ethPendingShare * 100).toFixed(0)}% backlog)
                </span>
                <span className="block mt-0.5 text-text-muted">
                  median {formatHours(ethLag.median_hours)} · p25 {formatHours(ethLag.p25_hours)}{' '}
                  · p75 {formatHours(ethLag.p75_hours)}
                </span>
              </div>
            )}
          </div>
          <div
            className={`border rounded p-3 ${
              opPendingShare >= 0.85
                ? 'border-danger/40 bg-danger/5'
                : opPendingShare >= 0.6
                ? 'border-warn/40 bg-warn/5'
                : 'border-border bg-surface-2'
            }`}
          >
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Optimism — processing distribution (180d)
            </div>
            {opLag && (
              <div className="num leading-relaxed">
                <span className="font-semibold">{opLag.sample_n}</span> completed pairs ·{' '}
                <span className="font-semibold">{opLag.pending_count}</span> pending
                <span className="text-text-muted">
                  {' '}({(opPendingShare * 100).toFixed(0)}% backlog)
                </span>
                <span className="block mt-0.5 text-text-muted">
                  median {formatHours(opLag.median_hours)} · p25 {formatHours(opLag.p25_hours)}{' '}
                  · p75 {formatHours(opLag.p75_hours)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {valuationAvailable && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="border border-border rounded p-3 bg-surface-2">
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Mainnet — 180d disbursements
            </div>
            {ethDisbSnx && (
              <div className="num">
                SNX: <span className="font-semibold">{ethDisbSnx.count}</span> txs ·{' '}
                avg <span className="num">{ethDisbSnx.mean.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span> SNX ·{' '}
                <span className="text-text-muted">{ethDisbSnx.unique_recipients} recipients</span>
              </div>
            )}
            {ethDisbSusd && (
              <div className="num mt-1">
                sUSD: <span className="font-semibold">{ethDisbSusd.count}</span> txs ·{' '}
                avg ${ethDisbSusd.mean.toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
            )}
          </div>
          <div className="border border-border rounded p-3 bg-surface-2">
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Optimism — 180d disbursements
            </div>
            {opDisbSnx ? (
              <div className="num">
                SNX: <span className="font-semibold">{opDisbSnx.count}</span> txs ·{' '}
                avg <span className="num">{opDisbSnx.mean.toLocaleString('en-US', { maximumFractionDigits: 0 })}</span> SNX ·{' '}
                <span className="text-text-muted">{opDisbSnx.unique_recipients} recipients</span>
              </div>
            ) : (
              <div className="text-text-dim">no SNX disbursements in window</div>
            )}
            <div className="text-text-dim text-[10px] mt-1">
              No sUSD disbursements observed on OP — jubilee processing is Mainnet-only.
            </div>
          </div>
          <div className="border border-border rounded p-3 bg-surface-2">
            <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-1">
              Caveats
            </div>
            <div className="text-text-dim text-[11px] leading-snug">
              Estimate assumes pending NFTs reflect the same SNX-vs-sUSD mix as historical
              processing. Sample sizes vary (ETH n={ethValuation?.sample_n ?? 0}, OP n=
              {opValuation?.sample_n ?? 0}). Values shift with SNX price.
            </div>
          </div>
        </div>
      )}

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
