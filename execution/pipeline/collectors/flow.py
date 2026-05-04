"""
Capital Flow Map collector.

Builds the Sankey for `where the $52.5M sUSD supply currently sits`. Reads
upstream snapshots (peg, supply, scorecard) so it must run AFTER those — see
`scripts/run_all.py` for the ordering.

Bucket sources:
  supply (root)        ← supply/latest.json (DefiLlama)
  infinex              ← stubbed $11.3M  (gap §4 #2)
  dex_liquidity        ← sum of peg/latest.json venue depths
  treasury             ← `scorecard.treasury_reserves.actual` MINUS the 420 Pool
                         aux-recipient leg (which is already counted in 420_jubilee).
                         Represents Treasury sUSD holdings *outside* the 420 Pool
                         program — buyback reserves, operational sUSD, etc. Currently
                         ~$0 because the only tracked Treasury wallet (`0xFa1DF09…`)
                         holds program-earmarked sUSD only. Bucket will grow if/when
                         Treasury accumulates non-program sUSD elsewhere.
  420_jubilee          ← pool_420/latest.json `susd_total` — live ERC-20 balanceOf
                         on the two Synthetix Treasury wallets (NFT-custody +
                         aux-recipient), summed across Mainnet + Optimism. This
                         IS the 5M SNX staking rewards program — sUSD is the
                         "auxiliary deposit" sent to Treasury, not v3 vault state.
                         Pool 8 architecture: see `project_susd_420_pool_architecture.md`.
                         (The previously separate `susd_rewards` bucket pointing
                         at stats.synthetix.io was the same money via a stale
                         data source — removed to fix double-counting.)
  slp                  ← $0 — SLP Vault is in private/internal mode per Synthetix
                         team (2026-05-04). No on-chain or published TVL. Public
                         launch planned Q2 2026; official target $15M sUSD by
                         2026-06-30. Earlier $1.45M placeholder was unsourced —
                         dropped to zero until launch makes actual TVL readable.
  free (residual)      ← total - sum(others) ; ~$7.5M, mostly EOAs

DEX sub-tree (5 named + Other DEX bucket):
  derived from peg.py venues by name match. The 4 smallest venues are
  bucketed into `dex_other`.

delta_24h: computed against the previous snapshot on disk if one exists.
This is a strictly "since last run" delta — labeled "24h" on the panel
because the cron lands roughly daily once it's running. Phase 2.5 enhancement:
maintain a daily archive for true 24h-window deltas.

Run:
  python -m collectors.flow
"""
from __future__ import annotations

import json
import sys

from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.flow import FlowSnapshot, FlowNode, FlowEdge


# ── anchored / stubbed bucket values ─────────────────────────────────────────
INFINEX_STUB = 11_300_000               # gap §4 #2
SLP_STUB = 0                            # private/internal until Q2 2026 (target $15M)
TREASURY_ADDRESS = "0xFa1DF09D8d09D6E8FAB2a6C4712fEa02ce203e99"

# Map from peg.py venue name → flow node id. The first 5 venues (by depth)
# get their own Sankey leaf; everything else aggregates into `dex_other`.
DEX_NAMED_NODES: dict[str, dict] = {
    "Curve sUSD/sUSDe":       {"id": "curve_susde",     "label": "Curve sUSD/sUSDe"},
    "Uniswap V3 sUSD/SNX":    {"id": "uni_susd_snx",    "label": "Uniswap V3 sUSD/SNX"},
    "Velodrome V2 USDC/sUSD": {"id": "velo_usdc_susd",  "label": "Velodrome V2 USDC/sUSD"},
    "Uniswap V2 sUSD/WETH":   {"id": "uni_susd_weth",   "label": "Uniswap V2 sUSD/WETH"},
    "Sushiswap sUSD/WETH":    {"id": "sushi_susd_weth", "label": "Sushiswap sUSD/WETH"},
}


def load_snapshot(name: str) -> dict:
    path = CLIENT_DATA_DIR / name / "latest.json"
    if not path.exists():
        raise RuntimeError(f"missing upstream snapshot: {path}")
    return json.loads(path.read_text())


def previous_node_values() -> dict[str, int]:
    """Read the existing flow/latest.json (if present) and return {node_id: value}."""
    path = CLIENT_DATA_DIR / "flow" / "latest.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {n["id"]: int(n["value"]) for n in raw.get("nodes", [])}


def collect() -> FlowSnapshot:
    print("[flow] reading upstream snapshots…")
    peg = load_snapshot("peg")
    supply = load_snapshot("supply")
    scorecard = load_snapshot("scorecard")
    pool_420 = load_snapshot("pool_420")

    total_supply = int(supply["total_supply_susd"])

    treasury_kpi = next((k for k in scorecard["kpis"] if k["id"] == "treasury_reserves"), None)
    treasury_total = int(treasury_kpi["actual"]) if treasury_kpi else 0

    pool_420_susd = int(pool_420["susd_total"])

    # Treasury bucket = sUSD held by Treasury *outside* the 420 program. Subtract
    # the Mainnet aux-recipient leg (which is what `treasury_reserves` reads —
    # same wallet pool_420 already counts under "Synthetix Treasury (aux recipient)").
    pool_420_aux_eth = 0
    for chain in pool_420.get("chains", []):
        if chain.get("chain") != "ethereum":
            continue
        for t in chain.get("treasuries", []):
            if t.get("address", "").lower() == TREASURY_ADDRESS.lower():
                pool_420_aux_eth = int(t.get("susd_amount", 0))
                break
    treasury_non_420 = max(0, treasury_total - pool_420_aux_eth)

    # ── DEX sub-tree: pull depths per venue from peg, split named vs other ────
    dex_named: list[FlowNode] = []
    dex_other_total = 0
    dex_other_pool_names: list[str] = []
    for v in peg["venues"]:
        depth = int(v.get("depth_usd") or 0)
        match = DEX_NAMED_NODES.get(v["name"])
        if match:
            dex_named.append(FlowNode(id=match["id"], label=match["label"], value=depth))
        else:
            dex_other_total += depth
            dex_other_pool_names.append(v["name"])
    dex_named.sort(key=lambda n: n.value, reverse=True)
    dex_other_node = FlowNode(
        id="dex_other",
        label=f"Other DEX ({len(dex_other_pool_names)} pools)",
        value=dex_other_total,
    )
    dex_total = sum(n.value for n in dex_named) + dex_other_node.value

    # ── top-level buckets ─────────────────────────────────────────────────────
    buckets_fixed = {
        "infinex":      INFINEX_STUB,
        "treasury":     treasury_non_420,
        "420_jubilee":  pool_420_susd,
        "slp":          SLP_STUB,
    }
    accounted = sum(buckets_fixed.values()) + dex_total
    free_floating = max(0, total_supply - accounted)

    nodes: list[FlowNode] = [
        FlowNode(id="supply", label="Total sUSD supply", value=total_supply),
        FlowNode(id="420_jubilee",  label="420 Pool (sUSD on Synthetix Treasury)", value=buckets_fixed["420_jubilee"]),
        FlowNode(id="infinex",      label="Infinex (Dune)",                 value=buckets_fixed["infinex"]),
        FlowNode(id="free",         label="Free-floating EOAs (CEX <0.3%)", value=free_floating),
        FlowNode(id="dex_liquidity", label="DEX Liquidity",                 value=dex_total),
        FlowNode(id="treasury",     label="Treasury reserves (non-420)",    value=buckets_fixed["treasury"]),
        FlowNode(id="slp",          label="SLP Vault (private — Q2 2026)",  value=buckets_fixed["slp"]),
        *dex_named,
        dex_other_node,
    ]

    edges: list[FlowEdge] = [
        FlowEdge.model_validate({"from": "supply", "to": "420_jubilee",  "value": buckets_fixed["420_jubilee"]}),
        FlowEdge.model_validate({"from": "supply", "to": "infinex",      "value": buckets_fixed["infinex"]}),
        FlowEdge.model_validate({"from": "supply", "to": "free",         "value": free_floating}),
        FlowEdge.model_validate({"from": "supply", "to": "dex_liquidity", "value": dex_total}),
        FlowEdge.model_validate({"from": "supply", "to": "treasury",     "value": buckets_fixed["treasury"]}),
        FlowEdge.model_validate({"from": "supply", "to": "slp",          "value": buckets_fixed["slp"]}),
        *[FlowEdge.model_validate({"from": "dex_liquidity", "to": n.id, "value": n.value}) for n in dex_named],
        FlowEdge.model_validate({"from": "dex_liquidity", "to": dex_other_node.id, "value": dex_other_node.value}),
    ]

    # ── delta_24h: current - previous (per node) ─────────────────────────────
    prev = previous_node_values()
    delta_24h: dict[str, int] = {}
    for n in nodes:
        if n.id == "supply":
            continue  # the root doesn't get a delta chip
        delta_24h[n.id] = n.value - prev.get(n.id, n.value)

    return FlowSnapshot(
        as_of=now_iso(),
        total_supply_susd=total_supply,
        nodes=nodes,
        edges=edges,
        delta_24h=delta_24h,
        infinex_source="dune",
        treasury_address=TREASURY_ADDRESS,
        dex_other_pools=dex_other_pool_names,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("flow", snapshot.model_dump(mode="json", by_alias=True, exclude_none=True))
    print(f"[flow] wrote {path}")
    print(f"[flow]   total supply:  ${snapshot.total_supply_susd:,}")
    # Top-level buckets only (children of `supply` per the edge graph)
    top_level_ids = {e.to for e in snapshot.edges if e.from_ == "supply"}
    for n in snapshot.nodes:
        if n.id in top_level_ids:
            delta = snapshot.delta_24h.get(n.id, 0)
            print(f"[flow]   {n.id:14} ${n.value:>12,}  Δ {delta:+,}")
    print(f"[flow]   ({len(snapshot.dex_other_pools or [])} pools aggregated into 'Other DEX')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
