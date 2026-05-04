"""
Trade Flow collector — semi-live (Step 1 of 3).

Live (refreshed every run):
  - per-venue total volume (sell + buy) ← peg/latest.json (DexScreener-derived)
  - aggregate sell/buy/net totals
  - 7d window scaled as 24h × 7

Illustrative (preserved as documented stubs — panel header discloses):
  - sell vs buy USD split per venue
  - counter-asset attribution (sUSDe / SNX / USDC / WETH share)
  - programmatic vs organic buy split

True directional sell/buy USD, real counter-asset bucketing, and Treasury-origin
classification all require per-DEX subgraph queries (Phase 2.5):
  - Uniswap V2 (Mainnet), Uniswap V3 (Mainnet + Optimism)
  - Sushiswap (Mainnet)
  - Velodrome V2 (Optimism)
  - Curve fallback via API + DexScreener

Run:
  python -m collectors.trade_flow
"""
from __future__ import annotations

import json
import sys

from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.trade_flow import (
    TradeFlowSnapshot,
    TradeFlowWindow,
    TradeFlowVenue,
    TradeFlowTotals,
    TradeFlowBuySplit,
)


# Top 5 venues by depth, matching Capital Flow Map's named DEX nodes.
# Each entry maps the peg.py venue name to its Trade Flow node identity +
# the illustrative sell/buy ratios used until subgraph integration ships.
# Ratios are sourced from the original stub design (see project memory
# `project_susd_phase1_status.md`); panel header discloses they're illustrative.
VENUES = [
    {"name": "Curve sUSD/sUSDe",       "id": "curve_susde",     "dex": "curve",     "label": "Curve sUSD/sUSDe",       "chain": "Ethereum", "sell_share": 0.6667},
    {"name": "Uniswap V3 sUSD/SNX",    "id": "uni_susd_snx",    "dex": "uniswap",   "label": "Uniswap V3 sUSD/SNX",    "chain": "Ethereum", "sell_share": 0.5833},
    {"name": "Velodrome V2 USDC/sUSD", "id": "velo_usdc_susd",  "dex": "velodrome", "label": "Velodrome V2 USDC/sUSD", "chain": "Optimism", "sell_share": 0.6444},
    {"name": "Uniswap V2 sUSD/WETH",   "id": "uni_susd_weth",   "dex": "uniswap",   "label": "Uniswap V2 sUSD/WETH",   "chain": "Ethereum", "sell_share": 0.6500},
    {"name": "Sushiswap sUSD/WETH",    "id": "sushi_susd_weth", "dex": "sushiswap", "label": "Sushiswap sUSD/WETH",    "chain": "Ethereum", "sell_share": 0.8000},
]

# Illustrative counter-asset distribution (sUSDe-dominant on Curve etc.).
# Phase 2.5 derives these from per-swap subgraph data instead.
COUNTER_ASSETS_24H = {
    "sell": {"sUSDe": 0.70, "SNX": 0.15, "USDC": 0.08, "WETH": 0.07},
    "buy":  {"sUSDe": 0.66, "SNX": 0.20, "USDC": 0.08, "WETH": 0.06},
}
COUNTER_ASSETS_7D = {
    "sell": {"sUSDe": 0.69, "SNX": 0.16, "USDC": 0.08, "WETH": 0.07},
    "buy":  {"sUSDe": 0.65, "SNX": 0.21, "USDC": 0.08, "WETH": 0.06},
}

# Illustrative programmatic share — Treasury-fee-router buybacks vs organic.
# Phase 2.5 computes this from `tx.from = <treasury executor>` after the
# executor address is confirmed (gap §4 E #10).
PROGRAMMATIC_SHARE_24H = 0.24
PROGRAMMATIC_SHARE_7D = 0.239


def load_peg() -> dict:
    path = CLIENT_DATA_DIR / "peg" / "latest.json"
    if not path.exists():
        raise RuntimeError(f"missing upstream snapshot: {path} — run peg.py first")
    return json.loads(path.read_text())


def build_window(name_to_volume: dict[str, int], counter_assets: dict, prog_share: float) -> TradeFlowWindow:
    """
    Build a TradeFlowWindow from per-venue volume totals + illustrative ratios.
    `name_to_volume` keys are peg.py venue names.
    """
    venues: list[TradeFlowVenue] = []
    for v in VENUES:
        total = int(name_to_volume.get(v["name"], 0))
        sell = int(round(total * v["sell_share"]))
        buy = total - sell
        venues.append(TradeFlowVenue(
            id=v["id"], dex=v["dex"], label=v["label"], chain=v["chain"],
            sell_susd=sell, buy_susd=buy,
        ))

    total_sell = sum(v.sell_susd for v in venues)
    total_buy = sum(v.buy_susd for v in venues)
    programmatic = int(round(total_buy * prog_share))
    organic = total_buy - programmatic

    return TradeFlowWindow(
        total=TradeFlowTotals(
            sell_susd=total_sell,
            buy_susd=total_buy,
            net_susd=total_buy - total_sell,
        ),
        venues=venues,
        sell_counter_assets=counter_assets["sell"],
        buy_counter_assets=counter_assets["buy"],
        buy_split=TradeFlowBuySplit(
            programmatic_susd=programmatic,
            organic_susd=organic,
            programmatic_share=prog_share,
        ),
    )


def collect() -> TradeFlowSnapshot:
    print("[trade_flow] reading peg/latest.json for fresh per-venue volumes…")
    peg = load_peg()

    name_to_vol_24h: dict[str, int] = {}
    for v in peg["venues"]:
        name_to_vol_24h[v["name"]] = int(v.get("volume_24h_usd") or 0)
    print(f"[trade_flow]   24h volumes: " + ", ".join(
        f'{v["name"]}=${name_to_vol_24h.get(v["name"], 0):,}' for v in VENUES
    ))

    # 7d window = 24h × 7 (illustrative scaling — Phase 2.5 uses real 7d subgraph data)
    name_to_vol_7d = {k: v * 7 for k, v in name_to_vol_24h.items()}

    return TradeFlowSnapshot(
        as_of=now_iso(),
        windows={
            "24h": build_window(name_to_vol_24h, COUNTER_ASSETS_24H, PROGRAMMATIC_SHARE_24H),
            "7d":  build_window(name_to_vol_7d,  COUNTER_ASSETS_7D,  PROGRAMMATIC_SHARE_7D),
        },
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("trade_flow", snapshot.model_dump(mode="json"))
    print(f"[trade_flow] wrote {path}")
    for window_name, w in snapshot.windows.items():
        print(
            f"[trade_flow]   {window_name:3} sell ${w.total.sell_susd:>9,}  buy ${w.total.buy_susd:>9,}  "
            f"net ${w.total.net_susd:>+9,}  organic share {(1 - w.buy_split.programmatic_share)*100:.1f}%"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
