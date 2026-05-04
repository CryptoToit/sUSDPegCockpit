"""Schema-conformance test for the scorecard snapshot."""
import json

from schemas.scorecard import ScorecardSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_scorecard_snapshot_validates():
    path = CLIENT_DATA_DIR / "scorecard" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    ScorecardSnapshot.model_validate(raw)


def test_scorecard_kpis_have_unique_ids():
    path = CLIENT_DATA_DIR / "scorecard" / "latest.json"
    raw = json.loads(path.read_text())
    snap = ScorecardSnapshot.model_validate(raw)
    ids = [kpi.id for kpi in snap.kpis]
    assert len(ids) == len(set(ids)), "duplicate KPI id in scorecard"
