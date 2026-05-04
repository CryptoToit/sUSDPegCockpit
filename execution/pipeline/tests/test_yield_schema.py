"""Schema-conformance test for the yield snapshot."""
import json

from schemas.yield_compare import YieldSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_yield_snapshot_validates():
    path = CLIENT_DATA_DIR / "yield" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    YieldSnapshot.model_validate(raw)


def test_yield_venues_have_unique_ids():
    path = CLIENT_DATA_DIR / "yield" / "latest.json"
    raw = json.loads(path.read_text())
    snap = YieldSnapshot.model_validate(raw)
    ids = [v.id for v in snap.venues]
    assert len(ids) == len(set(ids)), "duplicate yield venue id"
