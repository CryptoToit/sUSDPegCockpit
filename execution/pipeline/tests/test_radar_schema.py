"""Schema-conformance test for the radar snapshot."""
import json

from schemas.radar import RadarSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_radar_snapshot_validates():
    path = CLIENT_DATA_DIR / "radar" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    RadarSnapshot.model_validate(raw)


def test_radar_exit_ratio_consistency():
    """unlocked_susd_left + (unlocked_susd_total * exit_ratio_pct/100) ≈ unlocked_susd_total."""
    path = CLIENT_DATA_DIR / "radar" / "latest.json"
    raw = json.loads(path.read_text())
    snap = RadarSnapshot.model_validate(raw)
    if snap.unlocked_susd_total > 0:
        implied_exit = (1 - snap.unlocked_susd_left_protective_venues / snap.unlocked_susd_total) * 100
        assert abs(implied_exit - snap.exit_ratio_pct) < 1.0, (
            f"exit_ratio_pct ({snap.exit_ratio_pct}%) inconsistent with "
            f"left/total ratio (implies {implied_exit:.1f}%)"
        )
