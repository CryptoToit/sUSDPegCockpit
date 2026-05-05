"""
Recovery Score collector.

Derives a composite 0-100 score from 5 weighted subscores. Reads upstream
snapshots from disk (peg, scorecard, pool_420, trade_flow, nft_queue, radar)
— must run AFTER those collectors so it sees fresh values.

Weights and tier boundaries match the methodology footer on the panel UI:
  peg                   weight 0.35
  slp                   weight 0.20
  jubilee               weight 0.15
  buy_comp              weight 0.15
  flow                  weight 0.15

Phase 5 (2026-05-05): flow subscore redesigned. Was a thin wrapper around the
radar's green/amber/red traffic light (which only saw COMPLETED Treasury
outflows — a lagging indicator that's blind to building queue pressure).
Now reads the Unstake Queue's full exit funnel: queue inflow growth +
processing-backlog share + observed post-disbursement sell-through. Falls
back to the legacy radar read if the nft_queue snapshot is unavailable.

Tier boundaries (composite):
  < 35           critical          (EARLY STAGE)
  35–65          behind_pace       (BUILDING MOMENTUM)
  65–85          on_pace           (ON PACE)
  85+            recovery_near     (NEAR RECOVERY)

Run:
  python -m collectors.recovery_score
"""
from __future__ import annotations

import json
import sys

from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.recovery_score import (
    RecoveryScoreSnapshot,
    RecoveryScoreSubscore,
    RecoveryScoreTier,
)


# Tier boundaries, mirroring the methodology footer on the panel
TIER_BOUNDARIES: list[tuple[int, RecoveryScoreTier]] = [
    (35, "critical"),
    (65, "behind_pace"),
    (85, "on_pace"),
    (101, "recovery_near"),  # 85+
]


def load_snapshot(name: str) -> dict:
    path = CLIENT_DATA_DIR / name / "latest.json"
    if not path.exists():
        raise RuntimeError(f"missing upstream snapshot: {path}")
    return json.loads(path.read_text())


def tier_from_score(score: int) -> RecoveryScoreTier:
    for boundary, label in TIER_BOUNDARIES:
        if score < boundary:
            return label
    return "recovery_near"


def peg_subscore(peg: dict) -> tuple[int, str]:
    """Linear scale from $0.66 (depeg low) → $0.98 (staking-ratchet halt) → 100."""
    price = float(peg["reference"]["price_usd"])
    raw = (price - 0.66) / (0.98 - 0.66) * 100
    score = max(0, min(100, int(round(raw))))
    return score, f"${price:.4f} vs $0.98 recovery threshold"


def slp_subscore(scorecard: dict) -> tuple[int, str]:
    """SLP fill = actual / target × 100."""
    kpi = next((k for k in scorecard["kpis"] if k["id"] == "slp_fill"), None)
    if not kpi:
        return 0, "SLP KPI missing"
    actual = float(kpi["actual"])
    target = float(kpi["target"])
    raw = actual / target * 100 if target > 0 else 0
    score = max(0, min(100, int(round(raw))))
    return score, f"${actual / 1_000_000:.2f}M / ${target / 1_000_000:.0f}M by {kpi.get('deadline', 'TBD')}"


# Phase 2 sUSD-staking target per Synthetix team (2026-05-04 Q&A round 5).
JUBILEE_PHASE_2_TARGET_USD = 10_000_000


def jubilee_subscore(scorecard: dict, pool_420: dict) -> tuple[int, str]:
    """
    Composite of two on-chain signals, weighted 30% structural / 70% burning.

      (a) Structural (30%): total sUSD staked vs Phase 2 $10M target (capped 100).
          Precondition — reflects whether participants have entered the program.
      (b) Burning (70%): cumulative jubilee_burned vs $60M target.
          Outcome — reflects whether the debt-forgiveness mechanism has fired.
          This is what actually reduces the sUSD debt overhang and contributes
          to peg recovery; structural deposits are a prerequisite, not the
          recovery itself.

    Weighting history:
      - v1 (50/50): treated $0 burning as recovery failure, when really it's
        gated on stakers reaching 100% of original debt (per Synthetix
        contributor 2026-05-05). Misleadingly pessimistic.
      - v2 (80/20): over-corrected — credited "people showed up" at 80%
        when that's a precondition, not recovery. Score implied "on pace"
        even though the actual debt-forgiveness mechanism hadn't fired.
      - v3 (30/70, current): outcome-weighted. Structural still rewards the
        Phase 2 target being hit, but burning dominates because it's what
        actually drives peg recovery.
    """
    susd_staked = float(pool_420.get("susd_total", 0))
    structural_score = max(0, min(100, int(round(susd_staked / JUBILEE_PHASE_2_TARGET_USD * 100))))

    burned_kpi = next((k for k in scorecard["kpis"] if k["id"] == "jubilee_burned"), None)
    if burned_kpi:
        burned_actual = float(burned_kpi.get("actual") or 0)
        burned_target = float(burned_kpi.get("target") or 60_000_000) or 60_000_000
        burning_score = max(0, min(100, int(round(burned_actual / burned_target * 100))))
    else:
        burning_score = 0

    composite = int(round(0.3 * structural_score + 0.7 * burning_score))
    return composite, f"{structural_score}% structural · {burning_score}% burning"


def buy_comp_subscore(trade_flow: dict) -> tuple[int, str]:
    """Buy composition health = organic share × 100 from Trade Flow's 24h window."""
    w24 = trade_flow.get("windows", {}).get("24h", {})
    prog_share = float(w24.get("buy_split", {}).get("programmatic_share", 0))
    organic_share = 1 - prog_share
    score = max(0, min(100, int(round(organic_share * 100))))
    return score, f"{score}% organic (24h)"


def flow_subscore(radar: dict) -> tuple[int, str]:
    """
    Legacy v1 flow subscore — radar traffic light only.

    Retained as a fallback path. The active subscore is `flow_subscore_v2`
    below, which incorporates the Unstake Queue's full exit-pressure picture
    (queue inflow growth, backlog share, observed sell-through).
    """
    alert = (radar.get("alert_level") or "").lower()
    mapping = {"green": (90, "Green"), "amber": (50, "Amber"), "red": (20, "Red")}
    score, label_word = mapping.get(alert, (50, "Unknown"))
    exit_pct = radar.get("exit_ratio_pct", 0)
    return score, f"{label_word}: post-unlock outflow at {exit_pct}% exit ratio"


def flow_subscore_v2(nft_queue: dict) -> tuple[int, str]:
    """
    Phase-5 redesigned flow subscore: a value-weighted blend of three signals
    from the Unstake Queue panel that together capture the full exit funnel.

    Components (all 0–1 stress contributions, higher = more pressure):
      • growth_stress  (35%): 7d inflow rate / 30d baseline rate. 1.0× = 0,
        2.0× = 1.0 (clamped). Detects acceleration in unstake intent.
      • backlog_stress (30%): pending share among observed inbound+outbound
        pairs. 70% backlog = 0 (a normal-ish steady state for a manual-
        processing queue), 100% = 1.0. Detects processing bottlenecks.
      • sell_stress    (35%): observed sell-through to known sell routes —
        directly capped to [0, 1]. This is a LOWER BOUND on actual selling
        (we can't see private mempool / OTC / smaller venues), so the score
        may understate true exit pressure.

    composite_pressure = 0.35*growth + 0.30*backlog + 0.35*sell
    flow_subscore      = 100 * (1 − composite_pressure)
    """
    in_7d = float(nft_queue.get("total_nfts_in_7d") or 0)
    in_30d = float(nft_queue.get("total_nfts_in_30d") or 0)
    rate_7d = in_7d / 7 if in_7d else 0.0
    rate_30d = in_30d / 30 if in_30d else 0.0
    growth_ratio = (rate_7d / rate_30d) if rate_30d > 0 else 1.0
    growth_stress = max(0.0, min(1.0, (growth_ratio - 1.0) / 1.0))

    pending = float(nft_queue.get("total_lag_pending_count") or 0)
    completed = float(nft_queue.get("total_lag_sample_n") or 0)
    observed_total = pending + completed
    backlog_share = (pending / observed_total) if observed_total > 0 else 0.0
    backlog_stress = max(0.0, min(1.0, (backlog_share - 0.7) / 0.3))

    sell_share = float(nft_queue.get("total_sell_share") or 0.0)
    sell_stress = max(0.0, min(1.0, sell_share))

    pressure = 0.35 * growth_stress + 0.30 * backlog_stress + 0.35 * sell_stress
    score = max(0, min(100, int(round((1.0 - pressure) * 100))))

    value_text = (
        f"growth {growth_ratio:.2f}× · backlog {backlog_share * 100:.0f}% · "
        f"sell {sell_share * 100:.2f}%"
    )
    return score, value_text


def collect() -> RecoveryScoreSnapshot:
    print("[recovery_score] reading upstream snapshots…")
    peg = load_snapshot("peg")
    scorecard = load_snapshot("scorecard")
    radar = load_snapshot("radar")
    trade_flow = load_snapshot("trade_flow")
    pool_420 = load_snapshot("pool_420")

    peg_score, peg_value = peg_subscore(peg)
    slp_score, slp_value = slp_subscore(scorecard)
    jubilee_score, jubilee_value = jubilee_subscore(scorecard, pool_420)
    buy_comp_score, buy_comp_value = buy_comp_subscore(trade_flow)

    # Phase 5: flow subscore now reads the Unstake Queue's full exit-pressure
    # picture (growth + backlog + sell-through). Falls back to the legacy
    # radar-traffic-light read if the nft_queue snapshot is missing for any
    # reason — keeps the composite score producible during partial outages.
    flow_method = (
        "exit-pressure index: growth (35%) + backlog (30%) + sell-through (35%) "
        "— from Unstake Queue panel"
    )
    try:
        nft_queue = load_snapshot("nft_queue")
        flow_score, flow_value = flow_subscore_v2(nft_queue)
    except RuntimeError as exc:
        print(f"[recovery_score] WARN nft_queue missing — falling back to v1: {exc}")
        flow_score, flow_value = flow_subscore(radar)
        flow_method = (
            "fallback v1: radar alert level → green=90 / amber=50 / red=20 "
            "(nft_queue snapshot unavailable)"
        )

    subscores = [
        RecoveryScoreSubscore(
            id="peg",
            label="Peg restoration",
            score=peg_score,
            weight=0.35,
            value_text=peg_value,
            method="scaled from $0.66 (depeg low) → $0.98 (staking-ratchet halt, per SIP-420)",
        ),
        RecoveryScoreSubscore(
            id="slp",
            label="SLP fill",
            score=slp_score,
            weight=0.20,
            value_text=slp_value,
            method="actual / target × 100",
        ),
        RecoveryScoreSubscore(
            id="jubilee",
            label="Jubilee progress",
            score=jubilee_score,
            weight=0.15,
            value_text=jubilee_value,
            method="30% structural (Phase 2 $10M precondition) + 70% burning ($60M outcome) — burning is the actual recovery driver; structural deposits are a precondition, not the recovery itself",
        ),
        RecoveryScoreSubscore(
            id="buy_comp",
            label="Buy composition health",
            score=buy_comp_score,
            weight=0.15,
            value_text=buy_comp_value,
            method="organic share × 100 — market belief signal",
        ),
        RecoveryScoreSubscore(
            id="flow",
            label="Exit-pressure index",
            score=flow_score,
            weight=0.15,
            value_text=flow_value,
            method=flow_method,
        ),
    ]

    composite_raw = sum(s.score * s.weight for s in subscores)
    composite = int(round(composite_raw))
    tier = tier_from_score(composite)

    headline_by_tier = {
        "critical": "Recovery still in early stage. Peg restoration and program participation lagging.",
        "behind_pace": (
            f"Recovery actively underway. Jubilee scoring {jubilee_score}/100 and market signal is "
            f"{'supportive' if buy_comp_score >= 70 else 'mixed' if buy_comp_score >= 40 else 'fragile'} "
            f"({buy_comp_score}% organic buying), with peg restoration and SLP fill as the primary "
            "near-term milestones."
        ),
        "on_pace": "Recovery on pace. Multiple subscores in healthy range; peg approaching target.",
        "recovery_near": "Near full recovery. Peg restored or close to it; program metrics in green.",
    }

    return RecoveryScoreSnapshot(
        as_of=now_iso(),
        composite_score=composite,
        tier=tier,
        headline=headline_by_tier[tier],
        subscores=subscores,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("recovery_score", snapshot.model_dump(mode="json"))
    print(f"[recovery_score] wrote {path}")
    print(f"[recovery_score]   composite: {snapshot.composite_score} / 100  tier: {snapshot.tier}")
    for s in snapshot.subscores:
        print(f"[recovery_score]   {s.id:10} {s.score:>3}  weight {s.weight:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
