"""Schema-conformance test for the recovery_score snapshot."""
import json

from schemas.recovery_score import RecoveryScoreSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_recovery_score_snapshot_validates():
    path = CLIENT_DATA_DIR / "recovery_score" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    RecoveryScoreSnapshot.model_validate(raw)


def test_recovery_score_composite_is_weighted_sum():
    path = CLIENT_DATA_DIR / "recovery_score" / "latest.json"
    raw = json.loads(path.read_text())
    snap = RecoveryScoreSnapshot.model_validate(raw)
    weighted = sum(s.score * s.weight for s in snap.subscores)
    assert abs(snap.composite_score - round(weighted)) <= 1, \
        f"composite_score {snap.composite_score} != round(weighted_sum {weighted:.2f})"


def test_recovery_score_subscore_weights_sum_to_one():
    path = CLIENT_DATA_DIR / "recovery_score" / "latest.json"
    raw = json.loads(path.read_text())
    snap = RecoveryScoreSnapshot.model_validate(raw)
    total_weight = sum(s.weight for s in snap.subscores)
    assert abs(total_weight - 1.0) < 0.001, f"subscore weights must sum to 1.0, got {total_weight}"
