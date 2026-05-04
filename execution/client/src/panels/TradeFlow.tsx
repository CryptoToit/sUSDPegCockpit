import { useEffect, useState } from 'react'
import { snapshots } from '../lib/snapshots'
import type { TradeFlowSnapshot } from '../types'
import FreshnessBadge from '../components/FreshnessBadge'
import { ChainIcon, VenueGlyph } from '../components/Icons'
import { formatUSD } from '../lib/format'

type Period = '24h' | '7d'

const COUNTER_ASSET_COLORS: Record<string, string> = {
  sUSDe: 'bg-violet-500',
  SNX: 'bg-indigo-500',
  USDC: 'bg-blue-500',
  USDT: 'bg-emerald-500',
  DAI: 'bg-amber-500',
  WETH: 'bg-slate-500',
  Other: 'bg-zinc-500',
}

function CounterAssetTable({
  title,
  data,
  totalLabel,
}: {
  title: string
  data: Record<string, number>
  totalLabel: string
}) {
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1])
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-text-dim text-[10px] uppercase font-mono tracking-wider">{title}</span>
        <span className="num text-text-muted text-xs">{totalLabel}</span>
      </div>
      <div className="space-y-1.5">
        {sorted.map(([asset, share]) => (
          <div key={asset} className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-sm ${COUNTER_ASSET_COLORS[asset] || 'bg-text-dim'}`} />
            <span className="font-mono text-text-muted text-xs w-12">{asset}</span>
            <div className="flex-1 h-2 bg-surface-2 rounded overflow-hidden border border-border">
              <div
                className={`h-full ${COUNTER_ASSET_COLORS[asset] || 'bg-text-dim'}`}
                style={{ width: `${share * 100}%` }}
              />
            </div>
            <span className="num text-xs text-text-muted w-10 text-right">
              {(share * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TradeFlow() {
  const [data, setData] = useState<TradeFlowSnapshot | null>(null)
  const [period, setPeriod] = useState<Period>('24h')
  useEffect(() => {
    snapshots.tradeFlow().then(setData).catch(() => setData(null))
  }, [])

  if (!data) return <div className="text-text-dim p-6">Loading trade flow…</div>

  const w = data.windows[period]
  const totalFlow = w.total.sell_susd + w.total.buy_susd
  const sellPct = totalFlow > 0 ? (w.total.sell_susd / totalFlow) * 100 : 0
  const buyPct = totalFlow > 0 ? (w.total.buy_susd / totalFlow) * 100 : 0
  const isNetSelling = w.total.net_susd < 0

  // Buy-composition health logic — organic share drives the color
  const organicShare = 1 - w.buy_split.programmatic_share
  const tier: 'good' | 'mixed' | 'fragile' =
    organicShare > 0.7 ? 'good' : organicShare >= 0.4 ? 'mixed' : 'fragile'
  const organicStyles = {
    good: {
      border: 'border-ok/30',
      bg: 'bg-ok/5',
      text: 'text-ok',
      bar: 'bg-ok',
      label: 'Strong market-led recovery',
    },
    mixed: {
      border: 'border-warn/30',
      bg: 'bg-warn/5',
      text: 'text-warn',
      bar: 'bg-warn',
      label: 'Mixed signal',
    },
    fragile: {
      border: 'border-danger/30',
      bg: 'bg-danger/5',
      text: 'text-danger',
      bar: 'bg-danger',
      label: 'Protocol-carried recovery',
    },
  }[tier]

  // Trend arrow: 24h organic share vs 7d organic share
  const orgShare24h = 1 - data.windows['24h'].buy_split.programmatic_share
  const orgShare7d = 1 - data.windows['7d'].buy_split.programmatic_share
  const trendDelta = orgShare24h - orgShare7d
  const trendIsFlat = Math.abs(trendDelta) < 0.005
  const trendArrow = trendIsFlat ? '→' : trendDelta > 0 ? '↑' : '↓'
  const trendColor = trendIsFlat
    ? 'text-text-dim'
    : trendDelta > 0
    ? 'text-ok'
    : 'text-danger'

  return (
    <section id="tradeflow" className="border border-border rounded-lg bg-surface p-4 sm:p-6">
      <header className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold">Trade Flow</h2>
          <p className="text-text-dim text-sm">
            Bidirectional sUSD swap volume across the top 5 trading venues by depth (Curve
            sUSD/sUSDe dominates ~70% of the action). Programmatic buybacks are identified by
            transactions originating from the Synthetix Treasury (
            <code className="text-text-muted">0xFa1DF09…</code>); everything else is organic.{' '}
            <span className="text-warn">Note:</span> per-venue 24h volume totals are real
            (DexScreener), but the sell/buy split, counter-asset attribution, and
            programmatic/organic ratios are illustrative — true direction and Treasury-origin
            attribution requires per-DEX subgraph queries (Phase B ETL).
          </p>
        </div>
        <FreshnessBadge as_of={data.as_of} budget_min={45} />
      </header>

      {/* Period tabs */}
      <div className="inline-flex border border-border rounded p-0.5 bg-surface-2 mb-5">
        {(['24h', '7d'] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1 text-xs font-mono uppercase tracking-wider rounded transition ${
              period === p ? 'bg-accent/20 text-accent' : 'text-text-dim hover:text-text'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Aggregate flow */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-3">
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Sells (sUSD out)
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1 text-danger">
            ${formatUSD(w.total.sell_susd, { compact: true })}
          </div>
        </div>
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Buys (sUSD in)
          </div>
          <div className="num text-2xl sm:text-3xl font-semibold mt-1 text-ok">
            ${formatUSD(w.total.buy_susd, { compact: true })}
          </div>
        </div>
        <div>
          <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Net flow
          </div>
          <div className={`num text-2xl sm:text-3xl font-semibold mt-1 ${isNetSelling ? 'text-danger' : 'text-ok'}`}>
            {isNetSelling ? '−' : '+'}${formatUSD(Math.abs(w.total.net_susd), { compact: true })}
          </div>
          <div className="text-text-muted text-xs mt-1">
            {isNetSelling ? 'sell-pressure dominant' : 'buy-pressure dominant'}
          </div>
        </div>
      </div>

      {/* Aggregate balance bar */}
      <div className="h-3 bg-surface-2 rounded overflow-hidden flex border border-border mb-2">
        <div className="bg-danger" style={{ width: `${sellPct}%` }} />
        <div className="bg-ok" style={{ width: `${buyPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] font-mono mb-6">
        <span className="text-danger">SELLS {sellPct.toFixed(0)}%</span>
        <span className="text-ok">BUYS {buyPct.toFixed(0)}%</span>
      </div>

      {/* Per-venue breakdown */}
      <div className="mb-6 border-t border-border pt-4">
        <div className="text-text-dim text-[10px] uppercase font-mono tracking-wider mb-3">
          Per-venue flow ({period})
        </div>
        <div className="space-y-3">
          {w.venues.map((v) => {
            const venueTotal = v.sell_susd + v.buy_susd
            const vSellPct = venueTotal > 0 ? (v.sell_susd / venueTotal) * 100 : 0
            const vBuyPct = venueTotal > 0 ? (v.buy_susd / venueTotal) * 100 : 0
            return (
              <div key={v.id} className="grid grid-cols-12 gap-3 items-center">
                <div className="col-span-12 md:col-span-3 flex items-center gap-2">
                  <VenueGlyph dex={v.dex} chain={v.chain} size={26} />
                  <div className="min-w-0">
                    <div className="text-sm truncate">{v.label}</div>
                    <div className="flex items-center gap-1 text-text-dim text-[10px]">
                      <ChainIcon chain={v.chain} size={10} />
                      <span>{v.chain}</span>
                    </div>
                  </div>
                </div>
                <div className="col-span-12 md:col-span-9">
                  <div className="h-6 bg-surface-2 rounded overflow-hidden flex border border-border">
                    <div className="bg-danger/70" style={{ width: `${vSellPct}%` }} />
                    <div className="bg-ok/70" style={{ width: `${vBuyPct}%` }} />
                  </div>
                  <div className="flex justify-between text-[10px] num mt-1">
                    <span className="text-danger">
                      ${formatUSD(v.sell_susd, { compact: true })} sells
                    </span>
                    <span className="text-text-dim">
                      total ${formatUSD(venueTotal, { compact: true })}
                    </span>
                    <span className="text-ok">
                      ${formatUSD(v.buy_susd, { compact: true })} buys
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Counter-asset breakdowns */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 border-t border-border pt-4">
        <CounterAssetTable
          title="Sells went to"
          data={w.sell_counter_assets}
          totalLabel={`$${formatUSD(w.total.sell_susd, { compact: true })}`}
        />
        <CounterAssetTable
          title="Buys came from"
          data={w.buy_counter_assets}
          totalLabel={`$${formatUSD(w.total.buy_susd, { compact: true })}`}
        />
      </div>

      {/* Programmatic vs organic */}
      <div className="border-t border-border pt-4">
        <div className="flex items-baseline justify-between gap-2 mb-3">
          <span className="text-text-dim text-[10px] uppercase font-mono tracking-wider">
            Buy composition — protocol vs organic
          </span>
          <span className={`text-[10px] uppercase font-mono tracking-wider ${organicStyles.text}`}>
            {organicStyles.label}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          {/* Programmatic — always neutral */}
          <div className="border border-border bg-surface-2 rounded p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs uppercase tracking-wider font-mono text-text-muted">
                Programmatic
              </span>
              <span className="num text-xs text-text-muted">
                {(w.buy_split.programmatic_share * 100).toFixed(1)}%
              </span>
            </div>
            <div className="num text-xl font-semibold mt-1">
              ${formatUSD(w.buy_split.programmatic_susd, { compact: true })}
            </div>
            <div className="text-text-dim text-[11px] mt-1">
              Synthetix Treasury fee-router buybacks (Perps revenue 50/50 split). Baseline — happens
              regardless of market sentiment.
            </div>
          </div>

          {/* Organic — color tier driven by share */}
          <div className={`border ${organicStyles.border} ${organicStyles.bg} rounded p-3`}>
            <div className="flex items-baseline justify-between gap-2">
              <span className={`text-xs uppercase tracking-wider font-mono ${organicStyles.text}`}>
                Organic
              </span>
              <span className="num text-xs text-text-muted">
                {(organicShare * 100).toFixed(1)}%
                <span className={`ml-1.5 ${trendColor}`} title="24h vs 7d">
                  {trendArrow}
                  {!trendIsFlat && (
                    <span className="ml-0.5">{Math.abs(trendDelta * 100).toFixed(1)}pp</span>
                  )}
                </span>
              </span>
            </div>
            <div className="num text-xl font-semibold mt-1">
              ${formatUSD(w.buy_split.organic_susd, { compact: true })}
            </div>
            <div className="text-text-dim text-[11px] mt-1">
              Peg arbitrageurs, debt burners, speculative bidders. The voluntary peg-defense signal.
            </div>
          </div>
        </div>

        {/* Bar — programmatic neutral on left, organic tier-colored on right */}
        <div className="h-2 bg-surface-2 rounded overflow-hidden flex border border-border">
          <div
            className="bg-text-dim/40"
            style={{ width: `${w.buy_split.programmatic_share * 100}%` }}
          />
          <div className={organicStyles.bar} style={{ width: `${organicShare * 100}%` }} />
        </div>

        {/* Threshold legend */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[10px] font-mono text-text-dim">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-ok" /> &gt; 70% organic — market-led
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-warn" /> 40–70% — mixed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-danger" /> &lt; 40% — protocol-carried
          </span>
          <span className="inline-flex items-center gap-1.5 ml-auto">
            <span className={trendColor}>↑/↓</span> 24h vs 7d trend
          </span>
        </div>
      </div>
    </section>
  )
}
