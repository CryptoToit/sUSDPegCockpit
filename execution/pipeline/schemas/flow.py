"""Pydantic schema for flow/latest.json — mirrors FlowSnapshot in types.ts."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FlowNode(BaseModel):
    id: str
    label: str
    value: int


class FlowEdge(BaseModel):
    from_: str = Field(..., alias="from")  # `from` is reserved in Python
    to: str
    value: int

    model_config = {"populate_by_name": True}


class FlowSnapshot(BaseModel):
    as_of: str = Field(..., description="UTC ISO-8601 timestamp")
    total_supply_susd: int
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    delta_24h: dict[str, int]
    infinex_source: Optional[Literal["dune", "etl"]] = None
    treasury_address: Optional[str] = None
    dex_other_pools: Optional[list[str]] = None
