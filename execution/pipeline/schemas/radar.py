"""Pydantic schema for radar/latest.json — mirrors RadarSnapshot in types.ts."""
from typing import Literal
from pydantic import BaseModel, Field


AlertLevel = Literal["green", "amber", "red"]


class RadarSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    days_since_unlock: int
    net_flow_24h: dict[str, float]
    net_flow_7d: dict[str, float]
    unlocked_susd_total: int
    unlocked_susd_left_protective_venues: int
    exit_ratio_pct: float
    alert_level: AlertLevel
