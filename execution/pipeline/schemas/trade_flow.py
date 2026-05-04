"""Pydantic schema for trade_flow/latest.json — mirrors TradeFlowSnapshot in types.ts."""
from pydantic import BaseModel, Field


class TradeFlowVenue(BaseModel):
    id: str
    dex: str
    label: str
    chain: str
    sell_susd: int
    buy_susd: int


class TradeFlowTotals(BaseModel):
    sell_susd: int
    buy_susd: int
    net_susd: int


class TradeFlowBuySplit(BaseModel):
    programmatic_susd: int
    organic_susd: int
    programmatic_share: float


class TradeFlowWindow(BaseModel):
    total: TradeFlowTotals
    venues: list[TradeFlowVenue]
    sell_counter_assets: dict[str, float]
    buy_counter_assets: dict[str, float]
    buy_split: TradeFlowBuySplit


class TradeFlowSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    windows: dict[str, TradeFlowWindow]  # keys: "24h", "7d"
