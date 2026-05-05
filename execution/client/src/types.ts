export type Manifest = {
  generated_at: string
  snapshots: Record<string, { as_of: string; stale_after_min: number; ok: boolean }>
}

export type PegVenue = {
  name: string
  dex: string
  chain: string
  price_usd: number
  depth_usd: number
  pair_kind?: 'stable' | 'non-stable'
  pool_address?: string
  volume_24h_usd?: number
}

export type PegSnapshot = {
  as_of: string
  reference: { source: string; price_usd: number }
  venues: PegVenue[]
  weighted_avg_price_usd: number
  depeg_basis_points: number
}

export type SupplySnapshot = {
  as_of: string
  total_supply_susd: number
  supply_by_chain: Record<string, number>
}

export type TradeFlowVenue = {
  id: string
  dex: string
  label: string
  chain: string
  sell_susd: number
  buy_susd: number
}

export type TradeFlowWindow = {
  total: {
    sell_susd: number
    buy_susd: number
    net_susd: number
  }
  venues: TradeFlowVenue[]
  sell_counter_assets: Record<string, number>
  buy_counter_assets: Record<string, number>
  buy_split: {
    programmatic_susd: number
    organic_susd: number
    programmatic_share: number
  }
}

export type TradeFlowSnapshot = {
  as_of: string
  windows: {
    '24h': TradeFlowWindow
    '7d': TradeFlowWindow
  }
}

export type FlowSnapshot = {
  as_of: string
  total_supply_susd: number
  nodes: Array<{ id: string; label: string; value: number }>
  edges: Array<{ from: string; to: string; value: number }>
  delta_24h: Record<string, number>
  infinex_source?: 'dune' | 'etl'
}

export type KpiVelocity = {
  days_remaining: number
  required_daily_pace: number
  current_daily_pace: number
  tier: 'ahead' | 'on_track' | 'behind' | 'far_behind'
}

export type KpiStatus = 'verified' | 'stub' | 'closed' | 'context'

export type KpiItem = {
  id: string
  label: string
  actual: number | string
  target: number | string | null
  unit: string
  deadline?: string
  velocity?: KpiVelocity
  status?: KpiStatus
  note?: string
}

export type RecoveryScoreSubscore = {
  id: string
  label: string
  score: number
  weight: number
  value_text: string
  method: string
}

export type RecoveryScoreSnapshot = {
  as_of: string
  composite_score: number
  tier: 'critical' | 'behind_pace' | 'on_pace' | 'recovery_near'
  headline: string
  subscores: RecoveryScoreSubscore[]
}

export type ScorecardSnapshot = {
  as_of: string
  kpis: KpiItem[]
}

export type YieldStatus =
  | 'active'
  | 'closed'
  | 'vesting_only'
  | 'inactive_program'
  | 'theoretical'

export type YieldVenue = {
  id: string
  label: string
  apr_pct?: number
  apr_pct_implied?: number
  lock: string
  risk_note: string
  status?: YieldStatus
  audience?: string
}

export type YieldSnapshot = {
  as_of: string
  venues: YieldVenue[]
}

export type RadarSnapshot = {
  as_of: string
  days_since_unlock: number
  net_flow_24h: Record<string, number>
  net_flow_7d: Record<string, number>
  unlocked_susd_total: number
  unlocked_susd_left_protective_venues: number
  exit_ratio_pct: number
  alert_level: 'green' | 'amber' | 'red'
}

export type NftQueueChainWindow = {
  nfts_in_24h: number
  nfts_in_7d: number
  nfts_in_30d: number
  unique_addrs_24h: number
  unique_addrs_7d: number
  unique_addrs_30d: number
}

export type NftQueueInboundEvent = {
  chain: string
  block_number: number
  tx_hash: string
  from_address: string
  token_id: string
}

export type NftQueueSnapshot = {
  as_of: string
  council_wallet: string
  sacct_address: string
  chains: Record<string, NftQueueChainWindow>
  total_nfts_in_24h: number
  total_nfts_in_7d: number
  total_nfts_in_30d: number
  custody_count: Record<string, number>
  total_custody_count: number
  recent_inbound: NftQueueInboundEvent[]
}

export type EventItem = {
  date: string
  label: string
  kind: 'policy' | 'market'
  severity: 'high' | 'med' | 'low'
}
