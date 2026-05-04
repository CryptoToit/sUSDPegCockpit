"""Pydantic schema for yield/latest.json — mirrors YieldSnapshot in types.ts."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


YieldStatus = Literal["active", "closed", "vesting_only", "inactive_program", "theoretical"]


class YieldVenue(BaseModel):
    id: str
    label: str
    apr_pct: Optional[float] = None
    apr_pct_implied: Optional[float] = None
    lock: str
    risk_note: str
    status: Optional[YieldStatus] = None
    audience: Optional[str] = None


class YieldSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    venues: list[YieldVenue]
