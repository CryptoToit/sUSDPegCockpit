"""Pydantic schema for pool_420/latest.json — mirrors Pool420Snapshot in types.ts."""
from typing import Optional
from pydantic import BaseModel, Field


class TreasuryBalance(BaseModel):
    address: str
    label: str
    susd_amount: int


class Pool420ChainBreakdown(BaseModel):
    chain: str
    treasuries: list[TreasuryBalance]
    susd_total: int
    snx_amount: Optional[float] = None
    snx_value_usd: Optional[int] = None


class Pool420Snapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    pool_id: int
    susd_total: int
    chains: list[Pool420ChainBreakdown]
