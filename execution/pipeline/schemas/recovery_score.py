"""Pydantic schema for recovery_score/latest.json — mirrors RecoveryScoreSnapshot in types.ts."""
from typing import Literal
from pydantic import BaseModel, Field


RecoveryScoreTier = Literal["critical", "behind_pace", "on_pace", "recovery_near"]


class RecoveryScoreSubscore(BaseModel):
    id: str
    label: str
    score: int
    weight: float
    value_text: str
    method: str


class RecoveryScoreSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    composite_score: int
    tier: RecoveryScoreTier
    headline: str
    subscores: list[RecoveryScoreSubscore]
