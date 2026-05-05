"""
Trade Flow collector — Phase 2.5 in progress.

Live (refreshed every run):
  - per-venue total volume (sell + buy) ← peg/latest.json (DexScreener-derived)
  - aggregate sell/buy/net totals
  - 7d window scaled as 24h × 7 for illustrative venues; measured venues
    derive 7d directly from event history.

Per-venue attribution:
  - 'measured': sell/buy split + programmatic share derived from on-chain
    swap events (eth_getLogs against the pool's native swap event).
  - 'illustrative': sell/buy split is a hardcoded model approximation,
    pending event-scan integration.

Currently measured (Phase 2.5 progress):
  - Curve sUSD/sUSDe (Mainnet) — TokenExchange events on pool 0x4b5E…ebae

Currently illustrative (queued for measurement):
  - Uniswap V3 sUSD/SNX (Mainnet) — pool Swap events
  - Velodrome V2 USDC/sUSD (Optimism) — pool Swap events
  - Uniswap V2 sUSD/WETH (Mainnet) — pool Swap events
  - Sushiswap sUSD/WETH (Mainnet) — pool Swap events

Run:
  python -m collectors.trade_flow
"""
from __future__ import annotations

import json
import sys

from lib.rpc import RPC_MAINNET, RPC_OPTIMISM, eth_block_number, eth_get_logs
from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.trade_flow import (
    TradeFlowSnapshot,
    TradeFlowWindow,
    TradeFlowVenue,
    TradeFlowTotals,
    TradeFlowBuySplit,
)


# ─── Curve sUSD/sUSDe (Mainnet) — MEASURED ──────────────────────────────────
# Pool address verified on-chain (peg.py canonical list). Token ordering
# verified via coins(0)/coins(1): sUSD at index 0, sUSDe at index 1.
# TokenExchange event signature:
#   keccak256("TokenExchange(address,int128,uint256,int128,uint256)")
CURVE_SUSD_SUSDE_POOL = "0x4b5E827F4C0a1042272a11857a355dA1F4Ceebae"
CURVE_TOKEN_EXCHANGE_TOPIC = (
    "0x8b3e96f2b889fa771c53c981b40daf005f63f637f1869f707052d15a3dd97140"
)

# Synthetix Treasury executor address — swaps where this is the swap recipient
# (V2/V3/Velodrome) or the originator (Curve) are counted as programmatic
# buybacks vs organic counterparty flow.
TREASURY_EXECUTOR = "0xfa1df09d8d09d6e8fab2a6c4712fea02ce203e99"

BLOCK_TIME_S = {"ethereum": 12, "optimism": 2}
SECONDS_24H = 24 * 60 * 60
SECONDS_7D = 7 * 24 * 60 * 60

# ─── Uniswap V2 / Sushiswap / Velodrome V2 — V2-shape Swap events ────────────
# Event data layout: 4 × uint256 = (amount0In, amount1In, amount0Out, amount1Out)
# Indexed: sender (router/EOA) at topic[1], to (output recipient) at topic[2]
UNISWAP_V2_SWAP_TOPIC = (
    "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"
)
# Velodrome V2 (Solidly fork) — different param ORDER (to before amounts) so
# its keccak signature hash differs from Uniswap V2 even though data layout
# is identical (4 × uint256). Verified empirically against sUSD/USDC pool.
VELODROME_V2_SWAP_TOPIC = (
    "0xb3e2773606abfd36b5bd91394b3a54d1398336c65005baf7bf7a05efeffaf75b"
)

# Pool definitions for Uniswap-V2-style scanner. susd_idx ∈ {0, 1} per the
# pool's coins() / token0()/token1() ordering (verified live during build).
# `counter_asset` labels the OTHER token in the pair — used to aggregate
# per-counter-asset breakdowns (Phase 2.5 final piece, replaces hardcoded ratios).
V2_STYLE_POOLS = {
    "uni_susd_weth": {
        "rpc": RPC_MAINNET, "chain": "ethereum",
        "pool": "0xf80758aB42C3B07dA84053Fd88804bCB6BAA4b5c",
        "topic": UNISWAP_V2_SWAP_TOPIC,
        "susd_idx": 0,
        "counter_asset": "WETH",
    },
    "sushi_susd_weth": {
        "rpc": RPC_MAINNET, "chain": "ethereum",
        "pool": "0xF1F85b2C54a2bD284B1cf4141D64fD171Bd85539",
        "topic": UNISWAP_V2_SWAP_TOPIC,
        "susd_idx": 0,
        "counter_asset": "WETH",
    },
    "velo_usdc_susd": {
        "rpc": RPC_OPTIMISM, "chain": "optimism",
        "pool": "0xbC26519f936A90E78fe2C9aA2A03CC208f041234",
        "topic": VELODROME_V2_SWAP_TOPIC,
        "susd_idx": 1,
        "counter_asset": "USDC",
    },
}

# ─── Uniswap V3 — different swap event with signed int256 amounts ────────────
# Event: Swap(sender indexed, recipient indexed, int256 amount0, int256 amount1,
#             uint160 sqrtPriceX96, uint128 liquidity, int24 tick)
# Positive amount = paid INTO pool (user sold). Negative = paid OUT (user bought).
UNISWAP_V3_SWAP_TOPIC = (
    "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
)

V3_POOLS = {
    "uni_susd_snx": {
        "rpc": RPC_MAINNET, "chain": "ethereum",
        "pool": "0xA3ccaf08a54Cf31649f91aE1570A0720C8d4EB1E",
        "susd_idx": 0,
        "counter_asset": "SNX",
    },
}

# Curve sUSD/sUSDe is a single pool with a single counter — sUSDe.
CURVE_SUSD_SUSDE_COUNTER = "sUSDe"


def _parse_int256(hex32: str) -> int:
    """Parse a 32-byte two's-complement hex word into a signed Python int."""
    val = int(hex32, 16)
    if val >= 2 ** 255:
        val -= 2 ** 256
    return val


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


def _scan_curve_susd_first(
    rpc: str, pool: str, susd_price_usd: float, seconds: int,
    chain: str = "ethereum", counter_asset: str = CURVE_SUSD_SUSDE_COUNTER,
) -> dict:
    """
    Scan Curve TokenExchange events for a pool where sUSD is at coin index 0
    over the last `seconds` time window. Returns measured sell/buy USD totals,
    programmatic share, and swap count.

    Direction semantics (from the perspective of sUSD as the asset being traded):
      - sold_id == 0 (user sold sUSD into pool) → SELL of sUSD
      - bought_id == 0 (user received sUSD from pool) → BUY of sUSD

    USD denomination uses the current sUSD reference price (matches DexScreener's
    market-price convention). Programmatic = swaps where buyer == TREASURY_EXECUTOR.
    """
    head = eth_block_number(rpc)
    blocks = seconds // BLOCK_TIME_S[chain]
    logs = eth_get_logs(
        rpc, address=pool, topics=[CURVE_TOKEN_EXCHANGE_TOPIC],
        from_block=head - blocks, to_block=head,
    )

    sell_susd_raw = 0.0
    buy_susd_raw = 0.0
    prog_buy_raw = 0.0  # Treasury BUY of sUSD only (the "buyback" definition)

    for log in logs:
        buyer = "0x" + log["topics"][1][26:].lower()
        data = log["data"][2:]  # strip 0x
        sold_id = int(data[0:64], 16)
        tokens_sold = int(data[64:128], 16) / 1e18
        bought_id = int(data[128:192], 16)
        tokens_bought = int(data[192:256], 16) / 1e18

        is_prog = buyer == TREASURY_EXECUTOR
        if sold_id == 0:
            sell_susd_raw += tokens_sold
            # Treasury selling sUSD is anomalous — would not count as a buyback.
            # We don't track it as programmatic; if it ever happens, it'll show
            # in raw sell totals like any other sell.
        elif bought_id == 0:
            buy_susd_raw += tokens_bought
            if is_prog:
                prog_buy_raw += tokens_bought

    sell_usd = int(round(sell_susd_raw * susd_price_usd))
    buy_usd = int(round(buy_susd_raw * susd_price_usd))
    programmatic_buy_usd = int(round(prog_buy_raw * susd_price_usd))

    return {
        "sell_susd": sell_usd,
        "buy_susd": buy_usd,
        # Per-venue split of BUY volume (matches buy_split aggregate semantics)
        "programmatic_susd": programmatic_buy_usd,
        "organic_susd": buy_usd - programmatic_buy_usd,
        "swap_count": len(logs),
        "counter_asset": counter_asset,
    }


def _scan_v2_style_pool(
    rpc: str, pool: str, topic: str, susd_idx: int, susd_price_usd: float,
    seconds: int, chain: str, counter_asset: str,
) -> dict:
    """
    Scan Uniswap-V2-style Swap events (also Sushiswap, Velodrome V2). Data layout:
    4 × uint256 = (amount0In, amount1In, amount0Out, amount1Out).

    Direction (where sUSD is at coin index `susd_idx`):
      - amount{susd_idx}In > 0  → sUSD INTO pool → SELL
      - amount{susd_idx}Out > 0 → sUSD OUT of pool → BUY

    Programmatic detection: topic[2] is the swap recipient (`to`). If Treasury
    BUYS sUSD via a router, the recipient is Treasury — we mark those as
    programmatic. (Treasury selling is anomalous; not classified as buyback.)
    """
    head = eth_block_number(rpc)
    blocks = seconds // BLOCK_TIME_S[chain]
    logs = eth_get_logs(
        rpc, address=pool, topics=[topic],
        from_block=head - blocks, to_block=head,
    )

    sell_susd_raw = 0.0
    buy_susd_raw = 0.0
    prog_buy_raw = 0.0

    for log in logs:
        recipient = "0x" + log["topics"][2][26:].lower()
        d = log["data"][2:]
        amounts = [int(d[i*64:(i+1)*64], 16) for i in range(4)]
        in_amt = amounts[susd_idx]            # sUSD paid INTO pool (sell side)
        out_amt = amounts[susd_idx + 2]       # sUSD paid OUT of pool (buy side)
        sell_susd_raw += in_amt / 1e18
        if out_amt > 0:
            buy_susd_raw += out_amt / 1e18
            if recipient == TREASURY_EXECUTOR:
                prog_buy_raw += out_amt / 1e18

    sell_usd = int(round(sell_susd_raw * susd_price_usd))
    buy_usd = int(round(buy_susd_raw * susd_price_usd))
    prog_buy_usd = int(round(prog_buy_raw * susd_price_usd))

    return {
        "sell_susd": sell_usd,
        "buy_susd": buy_usd,
        "programmatic_susd": prog_buy_usd,
        "organic_susd": buy_usd - prog_buy_usd,
        "swap_count": len(logs),
        "counter_asset": counter_asset,
    }


def _scan_v3_pool(
    rpc: str, pool: str, susd_idx: int, susd_price_usd: float,
    seconds: int, chain: str, counter_asset: str,
) -> dict:
    """
    Scan Uniswap V3 Swap events. Data layout:
    5 fields = (int256 amount0, int256 amount1, uint160 sqrtPriceX96,
                uint128 liquidity, int24 tick).

    Sign convention: a positive amount means that token was paid INTO the pool
    (user sold it); negative means paid OUT (user bought it).

    Direction for sUSD (at index `susd_idx`):
      - amount{susd_idx} > 0  → SELL of sUSD
      - amount{susd_idx} < 0  → BUY of sUSD (use abs)

    Programmatic: same as V2-style — topic[2] (recipient) == Treasury.
    """
    head = eth_block_number(rpc)
    blocks = seconds // BLOCK_TIME_S[chain]
    logs = eth_get_logs(
        rpc, address=pool, topics=[UNISWAP_V3_SWAP_TOPIC],
        from_block=head - blocks, to_block=head,
    )

    sell_susd_raw = 0.0
    buy_susd_raw = 0.0
    prog_buy_raw = 0.0

    for log in logs:
        recipient = "0x" + log["topics"][2][26:].lower()
        d = log["data"][2:]
        amount0 = _parse_int256(d[0:64])
        amount1 = _parse_int256(d[64:128])
        susd_amount = amount0 if susd_idx == 0 else amount1
        if susd_amount > 0:
            sell_susd_raw += susd_amount / 1e18
        elif susd_amount < 0:
            buy_amt = -susd_amount / 1e18
            buy_susd_raw += buy_amt
            if recipient == TREASURY_EXECUTOR:
                prog_buy_raw += buy_amt

    sell_usd = int(round(sell_susd_raw * susd_price_usd))
    buy_usd = int(round(buy_susd_raw * susd_price_usd))
    prog_buy_usd = int(round(prog_buy_raw * susd_price_usd))

    return {
        "sell_susd": sell_usd,
        "buy_susd": buy_usd,
        "programmatic_susd": prog_buy_usd,
        "organic_susd": buy_usd - prog_buy_usd,
        "swap_count": len(logs),
        "counter_asset": counter_asset,
    }


def build_window(
    name_to_volume: dict[str, int],
    counter_assets: dict,
    prog_share: float,
    measured: dict[str, dict] | None = None,
) -> TradeFlowWindow:
    """
    Build a TradeFlowWindow from per-venue volume totals + illustrative ratios.
    `name_to_volume` keys are peg.py venue names.

    If `measured` is provided (dict of venue id → measured stats), those venues
    use the on-chain-derived sell/buy split + programmatic share instead of the
    illustrative model. Total volume is replaced with measured (sell+buy) when
    available — keeps the panel internally consistent.
    """
    measured = measured or {}
    venues: list[TradeFlowVenue] = []
    for v in VENUES:
        m = measured.get(v["id"])
        if m:
            sell = m["sell_susd"]
            buy = m["buy_susd"]
            venues.append(TradeFlowVenue(
                id=v["id"], dex=v["dex"], label=v["label"], chain=v["chain"],
                sell_susd=sell, buy_susd=buy,
                attribution_source="measured",
                swap_count=m.get("swap_count"),
                programmatic_susd=m.get("programmatic_susd"),
                organic_susd=m.get("organic_susd"),
            ))
        else:
            total = int(name_to_volume.get(v["name"], 0))
            sell = int(round(total * v["sell_share"]))
            buy = total - sell
            venues.append(TradeFlowVenue(
                id=v["id"], dex=v["dex"], label=v["label"], chain=v["chain"],
                sell_susd=sell, buy_susd=buy,
                attribution_source="illustrative",
            ))

    total_sell = sum(v.sell_susd for v in venues)
    total_buy = sum(v.buy_susd for v in venues)

    # Aggregate buy_split — programmatic = sum of BUY volume from Treasury executor.
    # Measured venues report the real per-venue programmatic_susd; illustrative
    # venues apply the model share to their portion of buy volume.
    measured_prog = sum((m.get("programmatic_susd") or 0) for m in measured.values())
    illustrative_buy = sum(
        v.buy_susd for v in venues if v.attribution_source == "illustrative"
    )
    illustrative_prog = int(round(illustrative_buy * prog_share))
    programmatic = measured_prog + illustrative_prog
    organic = total_buy - programmatic
    blended_share = programmatic / total_buy if total_buy > 0 else prog_share

    # Counter-asset attribution. Each MEASURED venue contributes its full
    # sell_susd to its single counter_asset bucket (since each pool has exactly
    # one counter token). Illustrative venues fall back to the hardcoded
    # `counter_assets` shares scaled by their portion of total volume.
    sell_counters = _build_counter_shares(
        venues, measured, total_sell, counter_assets["sell"], side="sell"
    )
    buy_counters = _build_counter_shares(
        venues, measured, total_buy, counter_assets["buy"], side="buy"
    )

    return TradeFlowWindow(
        total=TradeFlowTotals(
            sell_susd=total_sell,
            buy_susd=total_buy,
            net_susd=total_buy - total_sell,
        ),
        venues=venues,
        sell_counter_assets=sell_counters,
        buy_counter_assets=buy_counters,
        buy_split=TradeFlowBuySplit(
            programmatic_susd=programmatic,
            organic_susd=organic,
            programmatic_share=round(blended_share, 4),
        ),
    )


def _build_counter_shares(
    venues: list[TradeFlowVenue],
    measured: dict[str, dict],
    total_side_susd: int,
    illustrative_shares: dict[str, float],
    side: str,
) -> dict[str, float]:
    """
    Compute per-counter-asset share of `side` (sell or buy) volume.

    Measured venues: each pool has exactly one counter token, so the venue's
    full sell_susd / buy_susd contributes to that one counter bucket.
    Illustrative venues: fall back to the hardcoded share distribution scaled
    by their portion of total side volume — so an illustrative venue
    contributing $X out of $T total adds (X/T) × hardcoded_share to each
    counter's bucket.
    """
    if total_side_susd <= 0:
        return illustrative_shares  # nothing to allocate, return defaults

    field = "sell_susd" if side == "sell" else "buy_susd"
    counter_usd: dict[str, float] = {}

    illustrative_side_total = 0
    for v in venues:
        amt = getattr(v, field)
        if v.attribution_source == "measured":
            counter = measured.get(v.id, {}).get("counter_asset")
            if counter:
                counter_usd[counter] = counter_usd.get(counter, 0) + amt
            else:
                # Defensive: shouldn't happen, but if a measured venue lacks
                # counter_asset metadata, classify it as Other.
                counter_usd["Other"] = counter_usd.get("Other", 0) + amt
        else:
            illustrative_side_total += amt

    # Distribute illustrative-venue volume across the hardcoded share keys.
    if illustrative_side_total > 0:
        for counter, share in illustrative_shares.items():
            counter_usd[counter] = (
                counter_usd.get(counter, 0) + illustrative_side_total * share
            )

    # Convert to shares
    return {k: round(v / total_side_susd, 4) for k, v in counter_usd.items()}


def collect() -> TradeFlowSnapshot:
    print("[trade_flow] reading peg/latest.json for fresh per-venue volumes…")
    peg = load_peg()

    name_to_vol_24h: dict[str, int] = {}
    for v in peg["venues"]:
        name_to_vol_24h[v["name"]] = int(v.get("volume_24h_usd") or 0)
    print(f"[trade_flow]   24h volumes: " + ", ".join(
        f'{v["name"]}=${name_to_vol_24h.get(v["name"], 0):,}' for v in VENUES
    ))

    # 7d window = 24h × 7 for ILLUSTRATIVE venues; measured venues compute 7d
    # directly from event history below.
    name_to_vol_7d = {k: v * 7 for k, v in name_to_vol_24h.items()}

    # Measured per venue. Each scanner failure is isolated — the venue falls
    # back to its illustrative model so a single subscan failure doesn't kill
    # the whole panel.
    susd_price = float(peg["reference"]["price_usd"])
    measured_24h: dict[str, dict] = {}
    measured_7d: dict[str, dict] = {}
    print(f"[trade_flow] scanning per-venue swap events (sUSD @ ${susd_price:.4f})…")

    def _try(label: str, venue_id: str, fn, *args):
        for win, secs in (("24h", SECONDS_24H), ("7d", SECONDS_7D)):
            try:
                m = fn(*args, secs)
                (measured_24h if win == "24h" else measured_7d)[venue_id] = m
                print(
                    f"[trade_flow]   {label:30} {win:3}: {m['swap_count']:>4} swaps  "
                    f"sell ${m['sell_susd']:>9,}  buy ${m['buy_susd']:>9,}  "
                    f"prog ${m['programmatic_susd']:>7,}"
                )
            except Exception as exc:
                print(f"[trade_flow]   WARN {label} {win} scan failed: {exc}")

    # Curve sUSD/sUSDe (Mainnet) — TokenExchange events
    _try(
        "curve_susde", "curve_susde",
        lambda secs: _scan_curve_susd_first(RPC_MAINNET, CURVE_SUSD_SUSDE_POOL, susd_price, secs),
    )

    # V2-style pools: Uniswap V2 sUSD/WETH, Sushiswap sUSD/WETH, Velodrome V2 USDC/sUSD
    for vid, cfg in V2_STYLE_POOLS.items():
        _try(
            vid, vid,
            lambda secs, c=cfg: _scan_v2_style_pool(
                c["rpc"], c["pool"], c["topic"], c["susd_idx"], susd_price, secs, c["chain"],
                c["counter_asset"],
            ),
        )

    # V3 pools: Uniswap V3 sUSD/SNX
    for vid, cfg in V3_POOLS.items():
        _try(
            vid, vid,
            lambda secs, c=cfg: _scan_v3_pool(
                c["rpc"], c["pool"], c["susd_idx"], susd_price, secs, c["chain"],
                c["counter_asset"],
            ),
        )

    return TradeFlowSnapshot(
        as_of=now_iso(),
        windows={
            "24h": build_window(name_to_vol_24h, COUNTER_ASSETS_24H, PROGRAMMATIC_SHARE_24H, measured_24h),
            "7d":  build_window(name_to_vol_7d,  COUNTER_ASSETS_7D,  PROGRAMMATIC_SHARE_7D,  measured_7d),
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
