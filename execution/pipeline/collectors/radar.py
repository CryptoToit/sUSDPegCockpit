"""
Sell-Pressure Radar collector.

Tracks sUSD flow OUT of the 420 Pool program by scanning ERC-20 `Transfer` events
from the two Synthetix Treasury wallets that hold the program's locked sUSD. Both
chains, 24h + 7d windows.

Why outflows from Treasury (and not v3 Account NFT transfers, as originally planned):
  Investigation 2026-05-04 found the v3 architecture is essentially dormant for the
  420 Pool — Mainnet uses legacy v2x (no v3 NFTs at all), and Optimism's v3 pool 8
  has zero SNX delegated and zero AccountNFT activity. So the only architecture-
  agnostic signal is `sUSD leaves the Treasury wallets` — that's when locked sUSD
  becomes circulating supply, regardless of which contract path the user took to
  unstake. See project memory `project_susd_phase4_todo.md` for the full reasoning.

What stays the same:
  - days_since_unlock: live from the 2026-04-19 anchor

Live (this collector now):
  - net_flow_24h, net_flow_7d: per-chain Treasury outflows (negative = outflow)
  - unlocked_susd_total: pool_420 current locked balance (high-water proxy)
  - unlocked_susd_left_protective_venues: pool_420 minus 7d outflows
  - exit_ratio_pct: 7d outflow / total * 100 (a "weekly exit pulse" framing)
  - alert_level: green <0.5%, amber <2%, red ≥2% — heuristic until tuned

Run:
  python -m collectors.radar
"""
from __future__ import annotations

import json
import sys
from datetime import date

from lib.rpc import (
    RPC_MAINNET,
    RPC_OPTIMISM,
    eth_block_number,
    eth_get_logs,
)
from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.radar import RadarSnapshot


UNLOCK_DATE = date(2026, 4, 19)

# sUSD ERC-20 addresses
SUSD_MAINNET = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51"
SUSD_OPTIMISM = "0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9"

# ERC-20 Transfer event topic
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# The two Synthetix Treasury wallets holding 420 Pool sUSD (both chains)
TREASURIES = [
    "0xebAC8Fc8752A267A36cE683A867000F69Fd0e73d",
    "0xFa1DF09D8d09D6E8FAB2a6C4712fEa02ce203e99",
]

# Internal addresses to exclude when classifying outflows. A `Transfer` from
# one Treasury to another (or to the liquidator) is NOT a real outflow into
# circulating supply — it's just internal-balance shuffling. Filter these out
# so the radar only counts true releases. Currently no such activity is
# observed but this keeps the metric clean if the Treasury starts shuffling.
TREASURY_INTERNAL = {addr.lower() for addr in TREASURIES} | {
    "0x9daffb42b60bb14d8ee80b503aafc312dcbaf552",  # treasury liquidator
}

# Approximate block times — used to convert "X seconds ago" → block range to scan.
# Mainnet ~12s, OP ~2s (post-Bedrock).
BLOCK_TIME_S = {"ethereum": 12, "optimism": 2}

# Time windows
SECONDS_24H = 24 * 60 * 60
SECONDS_7D = 7 * 24 * 60 * 60


def _topic_from_addr(addr: str) -> str:
    """Convert a 20-byte address to a 32-byte left-padded topic for filtering Transfer.from."""
    return "0x000000000000000000000000" + addr[2:].lower()


def _scan_outflows(chain: str, rpc: str, susd_token: str) -> tuple[float, float]:
    """
    Returns (outflow_24h_susd, outflow_7d_susd) — sum of sUSD `Transfer` event values
    where `from` is one of the Treasury wallets.

    Scans the last 7d of blocks once and partitions logs into 24h vs 7d buckets by
    block number (faster than querying twice).
    """
    blk_per_s = BLOCK_TIME_S[chain]
    head = eth_block_number(rpc)
    blocks_7d = SECONDS_7D // blk_per_s
    blocks_24h = SECONDS_24H // blk_per_s
    threshold_24h = head - blocks_24h
    from_block = head - blocks_7d

    total_24h = 0.0
    total_7d = 0.0
    n_24h = 0
    n_7d = 0

    skipped_internal = 0
    for treasury in TREASURIES:
        from_topic = _topic_from_addr(treasury)
        logs = eth_get_logs(
            rpc,
            address=susd_token,
            topics=[TRANSFER_TOPIC, from_topic],
            from_block=from_block,
            to_block=head,
        )
        for log in logs:
            # Exclude internal Treasury-to-Treasury / Treasury-to-liquidator
            # moves — those aren't real outflows into circulating supply.
            to_addr = "0x" + log["topics"][2][26:].lower()
            if to_addr in TREASURY_INTERNAL:
                skipped_internal += 1
                continue
            value = int(log["data"], 16) / 1e18
            block_num = int(log["blockNumber"], 16)
            total_7d += value
            n_7d += 1
            if block_num >= threshold_24h:
                total_24h += value
                n_24h += 1
    if skipped_internal:
        print(f"[radar]   {chain:8} skipped {skipped_internal} internal Treasury moves")

    print(f"[radar]   {chain:8} outflows: 24h ${total_24h:>12,.2f} ({n_24h} txs)  "
          f"·  7d ${total_7d:>12,.2f} ({n_7d} txs)")
    return total_24h, total_7d


def _load_pool_420_total() -> int:
    path = CLIENT_DATA_DIR / "pool_420" / "latest.json"
    if not path.exists():
        raise RuntimeError(f"missing upstream snapshot: {path} — run pool_420 first")
    return int(json.loads(path.read_text())["susd_total"])


def _load_jubilee_burned() -> float:
    """Read cumulative jubilee_burned from the scorecard snapshot."""
    path = CLIENT_DATA_DIR / "scorecard" / "latest.json"
    if not path.exists():
        return 0.0
    raw = json.loads(path.read_text())
    for kpi in raw.get("kpis", []):
        if kpi.get("id") == "jubilee_burned":
            return float(kpi.get("actual") or 0)
    return 0.0


def _classify_alert(exit_ratio_pct: float) -> str:
    if exit_ratio_pct < 0.5:
        return "green"
    if exit_ratio_pct < 2.0:
        return "amber"
    return "red"


def _classify_phase(jubilee_burned: float, exit_ratio_pct: float) -> str:
    """
    Determine program phase based on observable mechanism activity.

      - interim: cumulative jubilee burning is $0 AND no meaningful exit-ratio
                 outflow yet. Reflects the pre-activation state where alerts
                 are GREEN by default because the mechanisms gating sUSD release
                 haven't fired (100% original-debt threshold for jubilee burn,
                 SLP Vault not yet live, manual NFT processing not at scale).
      - active:  jubilee burning has started OR exit ratio is materially
                 non-zero. Alert level becomes meaningful as a real-time signal.
      - post_program: TBD — placeholder for after the 5M-SNX release window
                 closes (~2026-07-19) and the program winds down.

    For now we don't auto-detect post_program; that's a future enhancement.
    """
    if jubilee_burned <= 0 and exit_ratio_pct < 0.1:
        return "interim"
    return "active"


def collect() -> RadarSnapshot:
    today = date.today()
    days_since_unlock = (today - UNLOCK_DATE).days
    print(f"[radar] days since unlock ({UNLOCK_DATE.isoformat()}): {days_since_unlock}")

    locked_total = _load_pool_420_total()
    print(f"[radar] 420 Pool locked total (from pool_420 snapshot): ${locked_total:,}")

    print("[radar] scanning Treasury sUSD outflows on Mainnet…")
    eth_24h, eth_7d = _scan_outflows("ethereum", RPC_MAINNET, SUSD_MAINNET)
    print("[radar] scanning Treasury sUSD outflows on Optimism…")
    op_24h, op_7d = _scan_outflows("optimism", RPC_OPTIMISM, SUSD_OPTIMISM)

    total_outflow_24h = eth_24h + op_24h
    total_outflow_7d = eth_7d + op_7d

    left_protective = max(0, locked_total - int(round(total_outflow_7d)))
    exit_ratio_pct = round((total_outflow_7d / locked_total * 100.0), 2) if locked_total > 0 else 0.0
    alert_level = _classify_alert(exit_ratio_pct)

    jubilee_burned = _load_jubilee_burned()
    phase = _classify_phase(jubilee_burned, exit_ratio_pct)
    print(f"[radar] phase: {phase} (jubilee burned: ${jubilee_burned:,.0f}, exit ratio: {exit_ratio_pct}%)")

    return RadarSnapshot(
        as_of=now_iso(),
        days_since_unlock=days_since_unlock,
        # Negative = outflow (consistent with prior schema convention)
        net_flow_24h={"ethereum": -round(eth_24h, 2), "optimism": -round(op_24h, 2)},
        net_flow_7d={"ethereum": -round(eth_7d, 2), "optimism": -round(op_7d, 2)},
        unlocked_susd_total=locked_total,
        unlocked_susd_left_protective_venues=left_protective,
        exit_ratio_pct=exit_ratio_pct,
        alert_level=alert_level,
        phase=phase,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("radar", snapshot.model_dump(mode="json"))
    print(f"[radar] wrote {path}")
    print(f"[radar]   alert: {snapshot.alert_level.upper()} (exit ratio 7d: {snapshot.exit_ratio_pct}%)")
    print(f"[radar]   total locked: ${snapshot.unlocked_susd_total:,}  ·  "
          f"left after 7d outflows: ${snapshot.unlocked_susd_left_protective_venues:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
