"""Schema-conformance + invariant tests for the nft_queue snapshot."""
import json

from schemas.nft_queue import NftQueueSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_nft_queue_snapshot_validates():
    path = CLIENT_DATA_DIR / "nft_queue" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    NftQueueSnapshot.model_validate(raw)


def test_nft_queue_window_monotonicity():
    """24h count ≤ 7d count ≤ 30d count, per chain and aggregate."""
    path = CLIENT_DATA_DIR / "nft_queue" / "latest.json"
    raw = json.loads(path.read_text())
    snap = NftQueueSnapshot.model_validate(raw)

    assert snap.total_nfts_in_24h <= snap.total_nfts_in_7d <= snap.total_nfts_in_30d, (
        f"window monotonicity violated: 24h={snap.total_nfts_in_24h} "
        f"7d={snap.total_nfts_in_7d} 30d={snap.total_nfts_in_30d}"
    )

    for chain, window in snap.chains.items():
        assert window.nfts_in_24h <= window.nfts_in_7d <= window.nfts_in_30d, (
            f"{chain}: 24h={window.nfts_in_24h} 7d={window.nfts_in_7d} 30d={window.nfts_in_30d}"
        )
        assert window.unique_addrs_24h <= window.unique_addrs_7d <= window.unique_addrs_30d, (
            f"{chain} unique addrs: 24h={window.unique_addrs_24h} 7d={window.unique_addrs_7d} "
            f"30d={window.unique_addrs_30d}"
        )


def test_nft_queue_aggregate_consistency():
    """Aggregate totals equal the sum of per-chain windows."""
    path = CLIENT_DATA_DIR / "nft_queue" / "latest.json"
    raw = json.loads(path.read_text())
    snap = NftQueueSnapshot.model_validate(raw)

    sum_24h = sum(w.nfts_in_24h for w in snap.chains.values())
    sum_7d = sum(w.nfts_in_7d for w in snap.chains.values())
    sum_30d = sum(w.nfts_in_30d for w in snap.chains.values())

    assert snap.total_nfts_in_24h == sum_24h, f"{snap.total_nfts_in_24h} != Σ {sum_24h}"
    assert snap.total_nfts_in_7d == sum_7d, f"{snap.total_nfts_in_7d} != Σ {sum_7d}"
    assert snap.total_nfts_in_30d == sum_30d, f"{snap.total_nfts_in_30d} != Σ {sum_30d}"

    sum_custody = sum(snap.custody_count.values())
    assert snap.total_custody_count == sum_custody, (
        f"{snap.total_custody_count} != Σ {sum_custody}"
    )


def test_nft_queue_custody_at_least_30d_inflow():
    """Custody count should be ≥ 30d inflow (council holds at least everything that
    arrived in the last 30d, plus any older NFTs still pending)."""
    path = CLIENT_DATA_DIR / "nft_queue" / "latest.json"
    raw = json.loads(path.read_text())
    snap = NftQueueSnapshot.model_validate(raw)

    assert snap.total_custody_count >= snap.total_nfts_in_30d, (
        f"custody {snap.total_custody_count} < 30d inflow {snap.total_nfts_in_30d} — "
        f"either council releases NFTs (we don't think so) or there's a counting bug"
    )
