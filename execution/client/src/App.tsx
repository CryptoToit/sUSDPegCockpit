import { useEffect, useState } from 'react'
import StagingBanner from './components/StagingBanner'
import GoToTopButton from './components/GoToTopButton'
import RecoveryScore from './panels/RecoveryScore'
import Supply from './panels/Supply'
import PegTracker from './panels/PegTracker'
import TradingVenues from './panels/TradingVenues'
import CapitalFlow from './panels/CapitalFlow'
import TradeFlow from './panels/TradeFlow'
import Maintainer from './panels/Maintainer'
import Scorecard from './panels/Scorecard'
import YieldCompare from './panels/YieldCompare'
import SellPressureRadar from './panels/SellPressureRadar'
import { snapshots } from './lib/snapshots'
import type { Manifest } from './types'

export default function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null)
  useEffect(() => {
    snapshots.manifest().then(setManifest).catch(() => setManifest(null))
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <StagingBanner />

      <header className="border-b border-border bg-surface px-4 sm:px-6 py-4 sm:py-5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-baseline justify-between gap-3 sm:gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">
              <span className="text-accent">{'{'}</span>sUSD<span className="text-accent">{'}'}</span> Peg Cockpit
            </h1>
            <p className="text-text-dim text-xs sm:text-sm mt-1 leading-snug">
              Real-time scoring and monitoring of Synthetix's sUSD peg recovery program against its
              own published KPIs.
            </p>
          </div>
          {manifest && (
            <div className="text-text-dim text-[11px] sm:text-xs font-mono">
              ETL last run: {new Date(manifest.generated_at).toUTCString()}
            </div>
          )}
        </div>
      </header>

      <nav className="border-b border-border bg-surface-2/95 sticky top-0 z-10 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2 overflow-x-auto scrollbar-hide">
          <div className="flex gap-4 sm:gap-5 text-xs font-mono uppercase tracking-wider whitespace-nowrap">
            <a href="#recovery-score" className="text-text-muted hover:text-accent transition py-1">Score</a>
            <a href="#supply" className="text-text-muted hover:text-accent transition py-1">Supply</a>
            <a href="#peg" className="text-text-muted hover:text-accent transition py-1">Peg</a>
            <a href="#radar" className="text-text-muted hover:text-accent transition py-1">Radar</a>
            <a href="#scorecard" className="text-text-muted hover:text-accent transition py-1">Scorecard</a>
            <a href="#flow" className="text-text-muted hover:text-accent transition py-1">Flow</a>
            <a href="#venues" className="text-text-muted hover:text-accent transition py-1">Venues</a>
            <a href="#tradeflow" className="text-text-muted hover:text-accent transition py-1">Trades</a>
            <a href="#yield" className="text-text-muted hover:text-accent transition py-1">Yield</a>
            <a href="#maintainer" className="text-text-muted hover:text-accent transition py-1">Maintainer</a>
          </div>
        </div>
      </nav>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-8 space-y-4 sm:space-y-6">
        <RecoveryScore />
        <Supply />
        <PegTracker />
        <SellPressureRadar />
        <Scorecard />
        <CapitalFlow />
        <TradingVenues />
        <TradeFlow />
        <YieldCompare />
        <Maintainer />
      </main>

      <footer className="border-t border-border bg-surface px-4 sm:px-6 py-5 sm:py-6 mt-6 sm:mt-8">
        <div className="max-w-7xl mx-auto text-text-dim text-[11px] sm:text-xs leading-relaxed">
          <p>Read-only public-good dashboard. Not a price oracle. Not financial advice.</p>
          <p className="mt-1">
            Sources: DefiLlama, DexScreener, Curve API, public RPCs (Ethereum + Optimism),
            Etherscan, Ethplorer, Synthetix open data. Most panels are driven by a live Python
            collector pipeline; Trade Flow swap attribution remains interim pending DEX-subgraph
            integration. Several KPIs (jubilee progress, SLP fill, Infinex AUM) are stubbed
            pending Synthetix team confirmation — see panel notes for which. Data is served
            via a CDN pinned to the latest commit hash on each page load — refresh to pull
            fresh values; freshness badges show the snapshot's own timestamp, not the moment
            your browser fetched it.
          </p>
        </div>
      </footer>

      <GoToTopButton />
    </div>
  )
}
