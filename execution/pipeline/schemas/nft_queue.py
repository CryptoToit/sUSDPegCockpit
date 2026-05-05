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


class NftQueueSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    council_wallet: str
    sacct_address: str
    chains: dict[str, ChainWindow]
    total_nfts_in_24h: int
    total_nfts_in_7d: int
    total_nfts_in_30d: int
    recent_inbound: list[InboundEvent]
