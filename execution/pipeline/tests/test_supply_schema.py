"""Schema-conformance test for the supply snapshot."""
import json

from schemas.supply import SupplySnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_supply_snapshot_validates():
    path = CLIENT_DATA_DIR / "supply" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    snap = SupplySnapshot.model_validate(raw)
    assert snap.total_supply_susd == sum(snap.supply_by_chain.values()), \
        "total_supply_susd must equal sum of supply_by_chain"
