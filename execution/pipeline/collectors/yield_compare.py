"""
Stakeholder Yield Compare collector.

6 yield options for sUSD holders. We refresh the two we can compute live and
preserve the others as documented stubs.

Live (refreshed every run):
  - Curve sUSD/sUSDe LP    → DefiLlama yield-pools `apy` field (base + reward)
  - Buy & hold to peg      → math from current sUSD price
  - Burn sUSD to repay debt → math from current sUSD price (same denominator)

Stubbed pending team data:
  - Infinex sUSD (recon §4 #2)
  - SLP Vault   (recon §4 #3 — Pre-deposit Season 2 closed)

Correct as-is (no live refresh needed):
  - sUSD Staking Rewards (5M SNX) — program ended 2026-04-19, vesting only

Phase B candidates (Pass 2 discovery sweep, not yet integrated):
  - Convex Curve sUSD/sUSDe boosted APR  → convexfinance.com/api/curve-platform-stats
  - Beefy Velodrome USDC/sUSD auto-comp → api.beefy.finance/apy

Run:
  python -m collectors.yield_compare
"""
from __future__ import annotations

import sys

from lib.http import get_json
from lib.snapshot import now_iso, write_snapshot
from schemas.yield_compare import YieldSnapshot, YieldVenue


SUSD_MAINNET_LOWER = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51".lower()
TARGET_PEG_PRICE = 1.00
DEPEG_LOW = 0.66  # The April-2025 low used as the "starting point" for implied gains
ASSUMED_HORIZON_MONTHS = 12  # Conservative 12-month horizon for annualizing implied APR


def fetch_susd_price() -> float:
    """sUSD reference price from DefiLlama (cross-venue aggregator)."""
    url = (
        "https://coins.llama.fi/prices/current/"
        "ethereum:0x57Ab1ec28D129707052df4dF418D58a2D46d5f51"
    )
    data = get_json(url)
    coins = data.get("coins") or {}
    prices = [c.get("price") for c in coins.values() if c.get("price") is not None]
    if not prices:
        raise RuntimeError(f"DefiLlama returned no sUSD price: {data}")
    return prices[0]


def fetch_curve_susd_susde_apy() -> tuple[float, float, float]:
    """
    DefiLlama yield-pools entry for the Mainnet Curve sUSD/sUSDe pool.
    Returns (apy_total_pct, apy_base_pct, apy_reward_pct).
    """
    data = get_json("https://yields.llama.fi/pools")
    pools = data.get("data") or []
    for p in pools:
        if p.get("project") != "curve-dex":
            continue
        if p.get("chain") != "Ethereum":
            continue
        if (p.get("symbol") or "").upper() != "SUSD-SUSDE":
            continue
        underlying = [t.lower() for t in (p.get("underlyingTokens") or [])]
        if SUSD_MAINNET_LOWER not in underlying:
            continue
        # DefiLlama returns APY as a percentage (e.g. 18.532 = 18.532%) — already correct unit.
        apy = float(p.get("apy") or 0)
        apy_base = float(p.get("apyBase") or 0)
        apy_reward = float(p.get("apyReward") or 0)
        return apy, apy_base, apy_reward
    raise RuntimeError("Curve sUSD/sUSDe pool not found in DefiLlama yield-pools")


def implied_peg_apr(current_price: float, horizon_months: int) -> float:
    """
    Annualized implied APR from buying at the current depegged price and holding to par.
    Conservative 12-month horizon — matches the displayed copy on the Yield Compare panel.
    """
    if current_price <= 0:
        return 0.0
    gross_pct = (TARGET_PEG_PRICE - current_price) / current_price * 100
    return round(gross_pct * (12 / horizon_months), 1)


def collect() -> YieldSnapshot:
    print("[yield] fetching sUSD reference price…")
    susd_price = fetch_susd_price()
    print(f"[yield]   sUSD price: ${susd_price:.4f}")

    print("[yield] fetching Curve sUSD/sUSDe APY from DefiLlama yield-pools…")
    apy_total, apy_base, apy_reward = fetch_curve_susd_susde_apy()
    print(f"[yield]   Curve LP APY: {apy_total:.2f}% ({apy_base:.1f}% base + {apy_reward:.1f}% reward)")

    implied = implied_peg_apr(susd_price, ASSUMED_HORIZON_MONTHS)
    print(f"[yield]   implied peg APR (12mo horizon): {implied:.1f}%")

    venues = [
        YieldVenue(
            id="infinex",
            label="Infinex sUSD",
            apr_pct=12.0,
            lock="rolling 8wk extensions",
            risk_note="smart-account custody · APR is stub pending team confirmation (recon §4 #2)",
            status="active",
        ),
        YieldVenue(
            id="curve_susde_lp",
            label="Curve sUSD/sUSDe LP",
            apr_pct=round(apy_total, 1),
            lock="none",
            risk_note=(
                f"{apy_base:.1f}% base (trading fees, lagged) + {apy_reward:.1f}% CRV/CVX rewards · "
                "IL if peg moves"
            ),
            status="active",
        ),
        YieldVenue(
            id="buy_hold_peg",
            label="Buy & hold to peg",
            apr_pct_implied=implied,
            lock="none",
            risk_note=(
                f"{round((TARGET_PEG_PRICE - susd_price) / susd_price * 100, 1)}% gross at "
                f"${susd_price:.4f} → $1.00; annualized depends on time-to-peg (12mo horizon shown)"
            ),
            status="theoretical",
        ),
        YieldVenue(
            id="burn_debt",
            label="Burn sUSD to repay SNX debt",
            apr_pct_implied=implied,
            lock="n/a",
            risk_note=f"one-shot — pays $1 of debt forgiveness per ${susd_price:.4f} of sUSD",
            status="theoretical",
            audience="SNX stakers only",
        ),
        YieldVenue(
            id="slp_vault",
            label="SLP Vault",
            apr_pct=45.0,
            lock="between seasons — closed for new deposits",
            risk_note="pre-deposit Season 2 closed; public Q2 2026 launch pending (recon §4 #3)",
            status="closed",
        ),
        YieldVenue(
            id="susd_rewards",
            label="sUSD Staking Rewards (5M SNX)",
            apr_pct=0,
            lock="principal unlocked Apr 19; SNX rewards vest 3mo linear",
            risk_note="program ended 2026-04-19 — no new yield",
            status="vesting_only",
        ),
    ]

    return YieldSnapshot(as_of=now_iso(), venues=venues)


def main() -> int:
    snapshot = collect()
    path = write_snapshot("yield", snapshot.model_dump(mode="json", exclude_none=True))
    print(f"[yield] wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
