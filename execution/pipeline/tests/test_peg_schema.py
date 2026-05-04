"""
Schema-conformance test for the peg snapshot.

Loads `client/public/data/peg/latest.json` from disk and validates it against
the Pydantic schema. If this fails after a collector run, either the collector
is producing malformed data or the schema has drifted from the React types.
"""
import json
from pathlib import Path

from schemas.peg import PegSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_peg_snapshot_validates():
    path = CLIENT_DATA_DIR / "peg" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    PegSnapshot.model_validate(raw)


def test_peg_venues_have_unique_pool_addresses():
    path = CLIENT_DATA_DIR / "peg" / "latest.json"
    raw = json.loads(path.read_text())
    snap = PegSnapshot.model_validate(raw)
    addrs = [v.pool_address.lower() for v in snap.venues if v.pool_address]
    assert len(addrs) == len(set(addrs)), "duplicate pool_address in venues"
