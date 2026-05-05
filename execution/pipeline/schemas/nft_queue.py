"""Pydantic schema for nft_queue/latest.json — mirrors NftQueueSnapshot in types.ts."""
from pydantic import BaseModel, Field


class ChainWindow(BaseModel):
    nfts_in_24h: int
    nfts_in_7d: int
    nfts_in_30d: int
    unique_addrs_24h: int
    unique_addrs_7d: int
    unique_addrs_30d: int


class InboundEvent(BaseModel):
    chain: str
    block_number: int
    tx_hash: str
    from_address: str
    token_id: str


class DisbursementStats(BaseModel):
    """Distribution of council outflows-to-users for a single token, over 180d.

    Internal Treasury shuffles (transfers between treasury wallets, transfers to
    the liquidator) are filtered out before computing these stats.
    """
    count: int = Field(..., description="Number of disbursement transactions")
    unique_recipients: int
    total: float = Field(..., description="Sum of all disbursed amounts (in token units)")
    mean: float
    median: float
    p25: float
    p75: float


class ChainValuation(BaseModel):
    """USD-value estimate for a chain's pending custody.

    Method: pending count split by historical SNX-vs-sUSD processing mix; each
    portion priced at the historical mean disbursement value × current spot price.
    Order-of-magnitude estimate, not a precise valuation.
    """
    estimated_usd: int
    estimated_snx_value_usd: int
    estimated_susd_value_usd: int
    sample_n: int = Field(..., description="Total disbursement count over 180d (SNX + sUSD)")
    snx_price_usd: float


class LagStats(BaseModel):
    """Per-EOA-paired processing lag distribution for a chain over the 180d window.

    Pairing: NFT[i] from EOA X is matched with the next council outflow to X at
    a later block; lag = (out_block - in_block) × block_time. Pending = inbounds
    with no later outflow yet.
    """
    sample_n: int = Field(..., description="Number of completed (paired) round-trips")
    pending_count: int = Field(..., description="Inbounds with no matching outflow yet")
    median_hours: float
    p25_hours: float
    p75_hours: float


class PostReleaseStats(BaseModel):
    """Observed post-disbursement DEX sell-through, per chain.

    For each council disbursement recipient, we scan their subsequent token
    transfers and tally any SNX/sUSD transfers to known DEX router/pool
    addresses. Lower bound on actual selling — misses private mempool,
    contract-wallet routing through unobserved swaps, and bridge-then-sell.
    """
    recipients_scanned: int
    snx_received: float
    snx_to_dex: float
    snx_sell_share: float = Field(..., description="snx_to_dex / snx_received")
    susd_received: float
    susd_to_dex: float
    susd_sell_share: float
    usd_received: int
    usd_to_dex: int
    usd_sell_share: float


class NftQueueSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    council_wallet: str
    sacct_address: str
    chains: dict[str, ChainWindow]
    total_nfts_in_24h: int
    total_nfts_in_7d: int
    total_nfts_in_30d: int
    custody_count: dict[str, int] = Field(
        ..., description="Per-chain count of SACCT NFTs currently held by the council wallet"
    )
    total_custody_count: int
    disbursements: dict[str, dict[str, DisbursementStats]] = Field(
        default_factory=dict,
        description="Per-chain, per-token (SNX/sUSD) historical disbursement stats over 180d",
    )
    valuation: dict[str, ChainValuation] = Field(
        default_factory=dict,
        description="Per-chain USD-value estimate for the pending custody",
    )
    total_estimated_usd: int = 0
    snx_price_usd: float = 0.0
    lag: dict[str, LagStats] = Field(
        default_factory=dict,
        description="Per-chain processing-lag distribution from EOA-pairing",
    )
    total_lag_sample_n: int = 0
    total_lag_pending_count: int = 0
    weighted_median_lag_hours: float = 0.0
    post_release: dict[str, PostReleaseStats] = Field(
        default_factory=dict,
        description="Per-chain observed sell-through after council disbursement",
    )
    total_usd_received: int = 0
    total_usd_to_dex: int = 0
    total_sell_share: float = 0.0
    recent_inbound: list[InboundEvent]
