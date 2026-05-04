"""Schema-conformance + invariant tests for the flow snapshot."""
import json

from schemas.flow import FlowSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_flow_snapshot_validates():
    path = CLIENT_DATA_DIR / "flow" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    FlowSnapshot.model_validate(raw)


def test_top_level_buckets_sum_to_total_supply():
    """Sum of edges from `supply` must equal total_supply_susd."""
    path = CLIENT_DATA_DIR / "flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = FlowSnapshot.model_validate(raw)
    top_level_total = sum(e.value for e in snap.edges if e.from_ == "supply")
    assert top_level_total == snap.total_supply_susd, (
        f"top-level edges sum to ${top_level_total:,} but total_supply_susd is ${snap.total_supply_susd:,}"
    )


def test_dex_subtree_sums_to_dex_liquidity():
    """Sum of edges from `dex_liquidity` must equal the dex_liquidity node value."""
    path = CLIENT_DATA_DIR / "flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = FlowSnapshot.model_validate(raw)
    dex_node = next(n for n in snap.nodes if n.id == "dex_liquidity")
    subtree_total = sum(e.value for e in snap.edges if e.from_ == "dex_liquidity")
    assert subtree_total == dex_node.value, (
        f"dex_liquidity sub-tree edges sum to ${subtree_total:,} but node value is ${dex_node.value:,}"
    )


def test_node_ids_are_unique():
    path = CLIENT_DATA_DIR / "flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = FlowSnapshot.model_validate(raw)
    ids = [n.id for n in snap.nodes]
    assert len(ids) == len(set(ids)), "duplicate node id in flow snapshot"
