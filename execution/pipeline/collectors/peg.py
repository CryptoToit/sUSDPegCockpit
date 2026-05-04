"""
Peg Tracker collector.

Fetches sUSD reference price + per-venue depth, spot price, and 24h volume
across the 9 tracked venues, computes the depth-weighted average and depeg
basis points, and writes the result to `peg/latest.json`.

Sources:
  - DefiLlama coins API:    sUSD reference price (cross-venue aggregate)
  - DexScreener token API:  per-pool spot price, depth, 24h volume (8 venues)
  - Curve API:              fallback for Curve sUSD/3CRV (Optimism), which
                            DexScreener doesn't index

Run:
  python -m collectors.peg
"""
from __future__ import annotations

import sys
from typing import Optional

from lib.http import get_json
from lib.snapshot import now_iso, write_snapshot
from schemas.peg import PegSnapshot, PegReference, PegVenue


# sUSD ERC-20 addresses
SUSD_MAINNET = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51"
SUSD_OPTIMISM = "0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9"

# Curve sUSD/3CRV pool on Optimism — DexScreener doesn't index this; use Curve API
CURVE_SUSD_3CRV_OP_POOL = "0x061b87122Ed14b9526A813209C8a59a633257bAb"


# The 9 venues we track. pool_address is the canonical identifier for matching
# DexScreener responses (case-insensitive). Order is the display order in the
# snapshot — sorted by depth descending, but we let the data decide at write time.
VENUES = [
    {"name": "Curve sUSD/sUSDe",       "dex": "curve",      "chain": "Ethereum", "pool_address": "0x4b5E827F4C0a1042272a11857a355dA1F4Ceebae", "pair_kind": None,         "source": "dexscreener"},
    {"name": "Uniswap V3 sUSD/SNX",    "dex": "uniswap",    "chain": "Ethereum", "pool_address": "0xA3ccaf08a54Cf31649f91aE1570A0720C8d4EB1E", "pair_kind": "non-stable", "source": "dexscreener"},
    {"name": "Velodrome V2 USDC/sUSD", "dex": "velodrome",  "chain": "Optimism", "pool_address": "0xbC26519f936A90E78fe2C9aA2A03CC208f041234", "pair_kind": None,         "source": "dexscreener"},
    {"name": "Uniswap V2 sUSD/WETH",   "dex": "uniswap",    "chain": "Ethereum", "pool_address": "0xf80758aB42C3B07dA84053Fd88804bCB6BAA4b5c", "pair_kind": "non-stable", "source": "dexscreener"},
    {"name": "Sushiswap sUSD/WETH",    "dex": "sushiswap",  "chain": "Ethereum", "pool_address": "0xF1F85b2C54a2bD284B1cf4141D64fD171Bd85539", "pair_kind": "non-stable", "source": "dexscreener"},
    {"name": "Uniswap V3 sUSD/DAI",    "dex": "uniswap",    "chain": "Optimism", "pool_address": "0xAdb35413eC50E0Afe41039eaC8B930d313E94FA4", "pair_kind": None,         "source": "dexscreener"},
    {"name": "Curve sUSD/3CRV",        "dex": "curve",      "chain": "Optimism", "pool_address": CURVE_SUSD_3CRV_OP_POOL,                       "pair_kind": None,         "source": "curve_api"},
    {"name": "Curve sUSD/crvUSD",      "dex": "curve",      "chain": "Ethereum", "pool_address": "0x94cC50e4521bD271C1a997a3A4Dc815C2F920b41", "pair_kind": None,         "source": "dexscreener"},
    {"name": "Uniswap V3 WETH/sUSD",   "dex": "uniswap",    "chain": "Optimism", "pool_address": "0x2E80d5A7B3C613d854EE43243Ff09808108561EB", "pair_kind": "non-stable", "source": "dexscreener"},
]


def fetch_reference_price() -> float:
    """sUSD price from DefiLlama's cross-venue aggregator (Mainnet + Optimism)."""
    url = (
        "https://coins.llama.fi/prices/current/"
        f"ethereum:{SUSD_MAINNET},optimism:{SUSD_OPTIMISM}"
    )
    data = get_json(url)
    coins = data.get("coins") or {}
    prices = [c.get("price") for c in coins.values() if c.get("price") is not None]
    if not prices:
        raise RuntimeError(f"DefiLlama returned no sUSD price: {data}")
    # Mainnet and Optimism prices are aggregated to the same value by DefiLlama;
    # if they ever diverge, return the average rather than failing.
    return sum(prices) / len(prices)


def fetch_dexscreener_pools() -> dict[str, dict]:
    """
    Returns a map of `lowercase_pool_address -> dexscreener pair object` for all
    pools containing sUSD across Mainnet and Optimism.
    """
    pools: dict[str, dict] = {}
    for token in (SUSD_MAINNET, SUSD_OPTIMISM):
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token}"
        data = get_json(url)
        pairs = data.get("pairs") or []
        for p in pairs:
            addr = (p.get("pairAddress") or "").lower()
            if addr:
                pools[addr] = p
    return pools


def fetch_curve_op_pool(pool_address: str) -> Optional[dict]:
    """Fetch a specific Curve Optimism pool's 24h volume by address (via Curve API)."""
    data = get_json("https://api.curve.finance/v1/getVolumes/optimism")
    pools = (data.get("data") or {}).get("pools") or []
    target = pool_address.lower()
    for p in pools:
        if (p.get("address") or "").lower() == target:
            return p
    return None


def fetch_defillama_yield_pool_tvl(project: str, chain: str, symbol: str) -> Optional[float]:
    """
    Look up a specific pool's TVL from DefiLlama's yield-pools API. Used for
    pools that aren't on DexScreener (e.g. Curve metapool on Optimism). Matches
    on (project, chain, symbol) — should uniquely identify a pool given that
    DefiLlama normalizes naming.
    """
    try:
        data = get_json("https://yields.llama.fi/pools")
    except Exception as e:
        print(f"[peg] WARN: DefiLlama yield-pools fetch failed: {e}", file=sys.stderr)
        return None
    pools = data.get("data") or []
    for p in pools:
        if (p.get("project") == project
                and p.get("chain") == chain
                and (p.get("symbol") or "").upper() == symbol.upper()):
            tvl = p.get("tvlUsd")
            return float(tvl) if tvl is not None else None
    return None


def build_venue_dexscreener(venue: dict, ds_pool: dict) -> PegVenue:
    """
    Build a PegVenue from a DexScreener pair.

    sUSD price derivation:
      - If sUSD is the base token of the pair → priceUsd is already the sUSD/USD price.
      - If sUSD is the quote token (e.g. SNX/sUSD) → priceUsd is the BASE token's USD
        price, not sUSD's. Compute sUSD/USD = priceUsd / priceNative, where priceNative
        is the price of base in quote (i.e. how many sUSD per 1 base).
    """
    base_addr = (ds_pool.get("baseToken") or {}).get("address", "").lower()
    quote_addr = (ds_pool.get("quoteToken") or {}).get("address", "").lower()
    base_price_usd = float(ds_pool.get("priceUsd") or 0)
    price_native = float(ds_pool.get("priceNative") or 0)

    if base_addr in (SUSD_MAINNET.lower(), SUSD_OPTIMISM.lower()):
        susd_price_usd = base_price_usd
    elif quote_addr in (SUSD_MAINNET.lower(), SUSD_OPTIMISM.lower()) and price_native > 0:
        susd_price_usd = base_price_usd / price_native
    else:
        raise RuntimeError(
            f"DexScreener pair {ds_pool.get('pairAddress')} for venue {venue['name']} "
            f"contains neither sUSD as base nor quote (base={base_addr}, quote={quote_addr})"
        )

    depth = float((ds_pool.get("liquidity") or {}).get("usd") or 0)
    vol = float((ds_pool.get("volume") or {}).get("h24") or 0)
    return PegVenue(
        name=venue["name"],
        dex=venue["dex"],
        chain=venue["chain"],
        price_usd=round(susd_price_usd, 4),
        depth_usd=int(round(depth)),
        pair_kind=venue["pair_kind"],
        pool_address=venue["pool_address"],
        volume_24h_usd=int(round(vol)),
    )


def build_venue_curve_op(venue: dict, curve_pool: dict, depth_tvl: Optional[float], fallback_price: float) -> PegVenue:
    """
    Build a PegVenue for the Optimism Curve sUSD/3CRV pool.

    Data sources for this pool (DexScreener doesn't index it):
      - 24h volume: Curve API (`api.curve.finance/v1/getVolumes/optimism`)
      - Total TVL: DefiLlama yield-pools API (passed in as `depth_tvl`)
      - Spot price: chain-wide DefiLlama sUSD price (passed in as `fallback_price`)

    Note: DefiLlama's `tvlUsd` is total pool TVL across all four assets in the
    sUSD/3CRV metapool (sUSD + USDC + USDT + DAI via 3CRV). The other tracked
    venues are 2-asset pools where the displayed liquidity is similarly the
    total pool TVL — so we treat the metapool's total TVL the same way for
    consistent depth-display semantics.
    """
    vol = float(curve_pool.get("volumeUSD") or 0)
    depth = depth_tvl if depth_tvl is not None else 0
    return PegVenue(
        name=venue["name"],
        dex=venue["dex"],
        chain=venue["chain"],
        price_usd=round(fallback_price, 4),
        depth_usd=int(round(depth)),
        pair_kind=venue["pair_kind"],
        pool_address=venue["pool_address"],
        volume_24h_usd=int(round(vol)),
    )


def collect() -> PegSnapshot:
    print("[peg] fetching reference price from DefiLlama…")
    ref_price = fetch_reference_price()
    print(f"[peg] reference price: ${ref_price:.4f}")

    print("[peg] fetching DexScreener pool data (Mainnet + Optimism)…")
    ds_pools = fetch_dexscreener_pools()
    print(f"[peg] found {len(ds_pools)} sUSD pools on DexScreener")

    print("[peg] fetching Curve Optimism volumes (for sUSD/3CRV)…")
    curve_pool = fetch_curve_op_pool(CURVE_SUSD_3CRV_OP_POOL)
    if not curve_pool:
        print(f"[peg] WARN: Curve sUSD/3CRV OP pool {CURVE_SUSD_3CRV_OP_POOL} not found in API response; volume will be 0", file=sys.stderr)
        curve_pool = {"volumeUSD": 0}

    # DexScreener doesn't index the OP Curve sUSD/3CRV metapool — pull TVL
    # from DefiLlama yield-pools instead so the venue isn't perpetually depth=0.
    # Note: DefiLlama uses 'OP Mainnet' as the chain name for Optimism in this
    # API (different from `Optimism` used elsewhere in their endpoints).
    print("[peg] fetching DefiLlama yield-pools TVL (for Curve sUSD/3CRV OP)…")
    curve_op_tvl = fetch_defillama_yield_pool_tvl("curve-dex", "OP Mainnet", "SUSD-3CRV")
    if curve_op_tvl is None:
        print("[peg] WARN: Curve sUSD/3CRV OP not found in DefiLlama yield-pools; depth will be 0", file=sys.stderr)
    else:
        print(f"[peg]   Curve sUSD/3CRV OP TVL: ${curve_op_tvl:,.0f}")

    venues: list[PegVenue] = []
    skipped: list[str] = []
    for v in VENUES:
        if v["source"] == "dexscreener":
            ds = ds_pools.get(v["pool_address"].lower())
            if not ds:
                # DexScreener occasionally drops marginal pools from its index
                # (low liquidity / volume → temporarily removed). Don't fail the
                # whole pipeline for one venue — skip it and carry on. The
                # weighted-avg calc just operates on the remaining venues for
                # this snapshot.
                print(f"[peg] WARN: pool {v['pool_address']} ({v['name']}) not in DexScreener response — skipping this venue", file=sys.stderr)
                skipped.append(v["name"])
                continue
            venues.append(build_venue_dexscreener(v, ds))
        elif v["source"] == "curve_api":
            venues.append(build_venue_curve_op(v, curve_pool, curve_op_tvl, ref_price))
        else:
            raise RuntimeError(f"unknown source for venue {v['name']}: {v['source']}")
    if skipped:
        print(f"[peg] {len(skipped)} venue(s) skipped this run: {', '.join(skipped)}", file=sys.stderr)

    # Sort by depth desc to match the existing snapshot convention
    venues.sort(key=lambda x: x.depth_usd, reverse=True)

    # Depth-weighted average (skip zero-depth venues so they don't dominate)
    total_depth = sum(v.depth_usd for v in venues)
    if total_depth > 0:
        weighted = sum(v.price_usd * v.depth_usd for v in venues) / total_depth
    else:
        weighted = ref_price
    weighted = round(weighted, 4)
    depeg_bp = round((weighted - 1.0) * 10000)

    snapshot = PegSnapshot(
        as_of=now_iso(),
        reference=PegReference(source="DefiLlama (cross-venue aggregator)", price_usd=round(ref_price, 4)),
        venues=venues,
        weighted_avg_price_usd=weighted,
        depeg_basis_points=depeg_bp,
    )
    return snapshot


def main() -> int:
    snapshot = collect()
    path = write_snapshot("peg", snapshot.model_dump(mode="json", exclude_none=True))
    total_depth = sum(v.depth_usd for v in snapshot.venues)
    total_vol = sum((v.volume_24h_usd or 0) for v in snapshot.venues)
    print()
    print(f"[peg] wrote {path}")
    print(f"[peg]   reference price:    ${snapshot.reference.price_usd:.4f}")
    print(f"[peg]   weighted avg price: ${snapshot.weighted_avg_price_usd:.4f}")
    print(f"[peg]   depeg from $1.00:   {snapshot.depeg_basis_points} bp")
    print(f"[peg]   venues:             {len(snapshot.venues)}  total depth ${total_depth:,.0f}  24h volume ${total_vol:,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
