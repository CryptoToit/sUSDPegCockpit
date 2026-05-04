"""Schema-conformance test for the pool_420 snapshot."""
import json

from schemas.pool_420 import Pool420Snapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_pool_420_snapshot_validates():
    path = CLIENT_DATA_DIR / "pool_420" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    snap = Pool420Snapshot.model_validate(raw)

    assert snap.pool_id == 8, "420 Pool is pool ID 8 in v3 Core Proxy"
    assert {c.chain for c in snap.chains} == {"ethereum", "optimism"}
    assert snap.susd_total == sum(c.susd_total for c in snap.chains), \
        "susd_total must equal sum of per-chain totals"
    for c in snap.chains:
        assert c.susd_total == sum(t.susd_amount for t in c.treasuries), \
            f"{c.chain} susd_total must equal sum of its treasury balances"
        assert len(c.treasuries) == 2, \
            f"{c.chain} must report both Treasury wallets (NFT-custody + aux-recipient)"
