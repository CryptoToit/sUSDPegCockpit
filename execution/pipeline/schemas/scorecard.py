"""Pydantic schema for scorecard/latest.json — mirrors ScorecardSnapshot in types.ts."""
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


KpiStatus = Literal["verified", "stub", "closed", "context"]


class KpiVelocity(BaseModel):
    days_remaining: int
    required_daily_pace: float
    current_daily_pace: float
    tier: Literal["ahead", "on_track", "behind", "far_behind"]


class KpiItem(BaseModel):
    id: str
    label: str
    actual: Union[int, float, str]
    target: Union[int, float, str, None]
    unit: str
    deadline: Optional[str] = None
    velocity: Optional[KpiVelocity] = None
    status: Optional[KpiStatus] = None
    note: Optional[str] = None


class ScorecardSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    kpis: list[KpiItem]
