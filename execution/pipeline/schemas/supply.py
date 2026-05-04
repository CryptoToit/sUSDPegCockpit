"""Pydantic schema for supply/latest.json — mirrors SupplySnapshot in types.ts."""
from pydantic import BaseModel, Field


class SupplySnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    total_supply_susd: int
    supply_by_chain: dict[str, int]
