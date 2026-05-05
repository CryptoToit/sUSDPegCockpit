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
    # Short one-liner shown inline in the right column. Should fit ~80 chars.
    summary: Optional[str] = None
    # Long-form methodology / caveats. Shown in an (i) popover. Always present.
    risk_note: str
    status: Optional[YieldStatus] = None
    audience: Optional[str] = None
    # Set true when the displayed APR is a placeholder pending verification
    # (e.g., Infinex's hardcoded 12% — we'd like to refresh from an API but
    # don't have one). The panel renders a "stub" badge next to the APR.
    apr_unverified: Optional[bool] = None


class YieldSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    venues: list[YieldVenue]
