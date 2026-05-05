"""
Stakeholder Yield Compare collector.

6 yield options for sUSD holders. We refresh the four we can compute live
and preserve the others as documented stubs.

Live (refreshed every run):
  - Curve sUSD/sUSDe LP    → DefiLlama yield-pools `apy` field (base + reward)
  - Buy & hold to peg      → math from current sUSD price
  - Burn sUSD to repay debt → math from current sUSD price (same denominator)
  - sUSD Staking Rewards (5M SNX) → 5M_SNX × SNX_price / locked_sUSD × (12/3)
    Reads locked sUSD from pool_420 snapshot (must run after that collector).

Stubbed pending team data:
  - Infinex sUSD (recon §4 #2)
  - SLP Vault   (Q2 2026 launch — APR not announced)

Phase B candidates (Pass 2 discovery sweep, not yet integrated):
  - Convex Curve sUSD/sUSDe boosted APR  → convexfinance.com/api/curve-platform-stats
  - Beefy Velodrome USDC/sUSD auto-comp → api.beefy.finance/apy

Run:
  python -m collectors.yield_compare
"""
from __future__ import annotations

import json
import sys

from lib.http import get_json
from lib.snapshot import CLIENT_DATA_DIR, now_iso, write_snapshot
from schemas.yield_compare import YieldSnapshot, YieldVenue


SUSD_MAINNET_LOWER = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51".lower()
TARGET_PEG_PRICE = 1.00
DEPEG_LOW = 0.66  # The April-2025 low used as the "starting point" for implied gains
ASSUMED_HORIZON_MONTHS = 12  # Conservative 12-month horizon for annualizing implied APR

# 5M SNX program parameters
SNX_REWARDS_TOTAL = 5_000_000
RELEASE_WINDOW_MONTHS = 3  # Apr 19 → ~Jul 19 2026 linear release

# DefiLlama identifiers for SNX. Mainnet SNX address doesn't resolve there
# (Synthetix Proxyable pattern), so try OP SNX (clean ERC-20) first, then
# coingecko:havven legacy ID. Same pattern as nft_queue collector.
SNX_PRICE_IDS = (
    "optimism:0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4",
    "coingecko:havven",
)


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


def fetch_snx_price() -> float:
    """SNX spot price in USD via DefiLlama, with identifier fallback."""
    for ident in SNX_PRICE_IDS:
        url = f"https://coins.llama.fi/prices/current/{ident}"
        try:
            data = get_json(url)
            coins = data.get("coins") or {}
            for c in coins.values():
                p = c.get("price")
                if p:
                    return float(p)
        except Exception as exc:
            print(f"[yield] WARN SNX price fetch via {ident} failed: {exc}")
    return 0.0


def fetch_pool_420_locked_susd() -> int:
    """Read the verified locked sUSD total from pool_420's snapshot."""
    path = CLIENT_DATA_DIR / "pool_420" / "latest.json"
    if not path.exists():
        raise RuntimeError(f"missing upstream snapshot: {path} — run pool_420 first")
    return int(json.loads(path.read_text())["susd_total"])


def staking_rewards_apr(snx_price_usd: float, locked_susd: float) -> float:
    """
    APR for stakers in the 5M-SNX rewards program (sUSD-side).

    Method: total reward USD over the 3-month linear release window divided by
    the currently-locked sUSD pool, annualised by × (12 / 3). This is the
    yield being earned by stakers already in the program — NOT accessible to
    new entrants (program closed to new deposits at lockup, 2026-04-19).
    """
    if snx_price_usd <= 0 or locked_susd <= 0:
        return 0.0
    rewards_usd = SNX_REWARDS_TOTAL * snx_price_usd
    yield_over_window = rewards_usd / locked_susd
    return round(yield_over_window * (12 / RELEASE_WINDOW_MONTHS) * 100, 1)


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

    print("[yield] computing 5M-SNX program APR (existing participants)…")
    snx_price = fetch_snx_price()
    locked_susd = fetch_pool_420_locked_susd()
    rewards_apr = staking_rewards_apr(snx_price, locked_susd)
    print(
        f"[yield]   SNX price: ${snx_price:.4f} · locked sUSD: ${locked_susd:,} → "
        f"in-program APR: {rewards_apr:.1f}%"
    )

    venues = [
        YieldVenue(
            id="infinex",
            label="Infinex sUSD",
            apr_pct=12.0,
            apr_unverified=True,
            lock="rolling 8wk extensions",
            summary="Smart-account custody · APR figure unverified",
            risk_note=(
                "Yield from Infinex's sUSD program (smart-account custody on per-user "
                "Safes). The displayed 12% APR is a stub — we don't currently have an "
                "Infinex API to refresh from, and the team hasn't published a definitive "
                "rate. Treat as indicative only; verify against Infinex's UI before "
                "depositing."
            ),
            status="active",
        ),
        YieldVenue(
            id="curve_susde_lp",
            label="Curve sUSD/sUSDe LP",
            apr_pct=round(apy_total, 1),
            lock="none",
            summary=(
                f"{apy_base:.1f}% trading fees + {apy_reward:.1f}% CRV/CVX · IL if peg moves"
            ),
            risk_note=(
                f"Live APY from DefiLlama yield-pools: {apy_base:.2f}% base (trading fees, "
                f"lagged) + {apy_reward:.2f}% CRV/CVX rewards = {apy_total:.2f}% total. "
                "Impermanent-loss risk if the sUSD/sUSDe peg ratio moves further. Both "
                "tokens are stablecoins so IL is bounded relative to volatile-pair LPs, "
                "but a sUSD depeg widening would still hurt."
            ),
            status="active",
        ),
        YieldVenue(
            id="buy_hold_peg",
            label="Buy & hold to peg",
            apr_pct_implied=implied,
            lock="none",
            summary=(
                f"{round((TARGET_PEG_PRICE - susd_price) / susd_price * 100, 1)}% gross to "
                f"$1.00 · 12mo annualisation"
            ),
            risk_note=(
                f"Buy at the current depeg price (${susd_price:.4f}) and hold until peg "
                f"restores to $1.00. Gross gain = "
                f"{round((TARGET_PEG_PRICE - susd_price) / susd_price * 100, 1)}%, annualised "
                "over a 12-month horizon for the displayed APR. Real APR depends on "
                "actual time-to-peg — could be faster (SLP launch + supply absorption "
                "could pull peg up) or slower (peg may stall / deteriorate). Capital is "
                "at risk if peg never recovers."
            ),
            status="theoretical",
        ),
        YieldVenue(
            id="burn_debt",
            label="Burn sUSD to repay SNX debt",
            apr_pct_implied=implied,
            lock="n/a",
            summary="Gated: needs staker at 100% of original debt",
            risk_note=(
                f"One-shot mechanic — $1 of SNX-staker debt forgiven per "
                f"${susd_price:.4f} of sUSD burned, equivalent to "
                f"{round((TARGET_PEG_PRICE - susd_price) / susd_price * 100, 1)}% return. "
                "GATED: the burn mechanic only fires when the staker is at 100% of their "
                "original debt collateralized in sUSD (Synthetix contributor confirmed "
                "2026-05-05). Most stakers are below this threshold, so this yield is "
                "not currently accessible to the bulk of the cohort. The threshold "
                "could be relaxed by governance, but no announcement has been made."
            ),
            status="theoretical",
            audience="SNX stakers at 100% original-debt threshold only",
        ),
        YieldVenue(
            id="slp_vault",
            label="SLP Vault",
            # APR not announced; intentionally no apr_pct or apr_pct_implied.
            lock="opens Q2 2026 (~end of June)",
            summary="Opens Q2 2026 · sUSD sink · APR not announced",
            risk_note=(
                "New contract, sUSD-only deposits, locks the sUSD (no new minting). "
                "Synthetix contributor confirmed 2026-05-05 that the team's intent is "
                "for 'most of the sUSD supply to go here'. Published target: $15M by "
                "2026-06-30 — actual ambition appears materially higher. APR not "
                "announced. Audit status not disclosed. Contract address will surface "
                "at launch."
            ),
            status="theoretical",
        ),
        YieldVenue(
            id="susd_rewards",
            label="sUSD Staking Rewards (5M SNX)",
            apr_pct=rewards_apr,
            lock="principal unlocked Apr 19; SNX rewards vest 3mo linear (~Apr 19 → Jul 19, 2026)",
            summary=(
                f"Closed to new deposits · {rewards_apr:.1f}% APR for stakers already in"
            ),
            risk_note=(
                f"5M SNX rewards distribute linearly from 2026-04-19 to ~2026-07-19 to "
                f"stakers who entered before lockup. APR computed live: "
                f"5M SNX × ${snx_price:.4f} ÷ ${locked_susd:,} locked sUSD × (12÷3 month "
                f"annualisation) = {rewards_apr:.1f}%. NO NEW DEPOSITS accepted — this "
                "yield is only earned by stakers already in the program. Existing "
                "participants have a financial incentive to delay exit until the "
                "release window closes; those who exit early forfeit unvested SNX. The "
                "shown APR floats with SNX price."
            ),
            status="vesting_only",
            audience="existing participants only",
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
