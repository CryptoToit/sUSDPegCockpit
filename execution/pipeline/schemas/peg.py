"""
Pydantic schema for peg/latest.json — mirrors PegSnapshot in client/src/types.ts.

Keep these in lock-step with the TS types. When fields are added to one side,
update the other and run the test suite to confirm.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class PegReference(BaseModel):
    source: str
    price_usd: float


class PegVenue(BaseModel):
    name: str
    dex: str
    chain: str
    price_usd: float
    depth_usd: int
    pair_kind: Optional[Literal["stable", "non-stable"]] = None
    pool_address: Optional[str] = None
    volume_24h_usd: Optional[int] = None


class PegSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    reference: PegReference
    venues: list[PegVenue]
    weighted_avg_price_usd: float
    depeg_basis_points: int
