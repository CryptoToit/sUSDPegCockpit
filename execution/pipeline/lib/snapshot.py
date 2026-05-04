import json
import os
from pathlib import Path
from datetime import datetime, timezone

from .config import get as _config_get

# Path collectors write snapshots to. Default: the React client's public data
# directory in this repo (so `npm run dev` and `vite build` pick up local
# changes).
#
# Override via `SNAPSHOT_OUT_DIR` config value (real env var OR `.env` file
# entry — both work, real env wins) when running in deployed contexts. The
# VPS systemd-timer cron points this at the public-mirror clone's `data/`
# directory, so collectors write directly to the publish target without
# dirtying the source-repo working tree.
_DEFAULT_OUT_DIR = Path(__file__).resolve().parents[2] / "client" / "public" / "data"
_override = _config_get("SNAPSHOT_OUT_DIR")
CLIENT_DATA_DIR = Path(_override).resolve() if _override else _DEFAULT_OUT_DIR


def now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_snapshot(snapshot_name: str, data: dict) -> Path:
    """
    Write `data` as JSON to `<client>/public/data/<snapshot_name>/latest.json`.

    Uses an atomic rename so the React client never reads a half-written file.
    """
    target_dir = CLIENT_DATA_DIR / snapshot_name
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "latest.json"
    tmp = target.with_suffix(".json.tmp")

    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, target)
    return target
