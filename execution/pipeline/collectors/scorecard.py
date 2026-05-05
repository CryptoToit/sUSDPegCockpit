"""
Recovery Program Scorecard collector.

6 KPIs. Status mix:
  - VERIFIED   live on-chain reads
  - STUB       awaiting Synthetix team confirmation (see directions/proposal/06-supply-reconciliation.md §4)
  - CLOSED     program paused / not currently active
  - CONTEXT    derived (not a target metric)

What we refresh live:
  - treasury_reserves    ← on-chain `balanceOf` of the 420 Pool aux-recipient (Mainnet leg only)
  - jubilee_burned       ← cumulative sum of `TreasuryBurned` events on TreasuryMarketProxy
                            (currently $0 — no burns have fired yet; awaiting team confirmation)
  - days_since_unlock    ← derived from the 2026-04-19 unlock anchor

Closed / not measured (deliberate, not gaps to chase):
  - jubilee_phase        (no single on-chain field — derived metric pending team clarification)
  - slp_fill             ($0 actual confirmed; Q2 2026 launch + $15M target)
  - snx_in_420_pool      (Mainnet uses legacy v2x — SNX side is parallel to peg story, out of scope)

When stubs are answered (e.g. by team response or self-serve via gunboats/snx-buyback),
update the values inline below — schema-validated, atomic write to disk.

Run:
  python -m collectors.scorecard
"""
from __future__ import annotations

import sys
from datetime import date

from lib.snapshot import now_iso, write_snapshot
from lib.rpc import RPC_MAINNET, erc20_balance_of, eth_block_number, eth_get_logs
from schemas.scorecard import ScorecardSnapshot, KpiItem


# Mainnet sUSD ERC-20 (ProxysUSD)
SUSD_MAINNET = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51"

# Treasury Market aux mechanism recipient — accumulates sUSD from the 20% fee skim
# (treasury_aux_ratio = 0.2). Verified at $5.64M during 2026-05-03 on-chain top-holders recon.
TREASURY_AUX_RECIPIENT = "0xFa1DF09D8d09D6E8FAB2a6C4712fEa02ce203e99"

# Synthetix Treasury Market Proxy — Cannon-deployed; verified via
# Etherscan ("SynthetixTreasuryProxy") + ABI extracted from
# `@synthetixio/v3-contracts:8.10.0`. Holds the 420 Pool / Simple sUSD
# Staking Rewards program logic. See project memory.
TREASURY_MARKET_PROXY_MAINNET = "0x7b952507306E7D983bcFe6942Ac9F2f75C1332D8"

# Event topic hashes (keccak256 of event signature)
TOPIC_TREASURY_BURNED = "0x0c368a1ed0fadc01b4c00ea9ff762a706fc853aecce44548dfc876f0484f9947"

# Scan window for cumulative TreasuryBurned. 200k blocks ≈ 28 days on Mainnet,
# which covers the entire post-lockup period (lockup ended 2026-04-19) plus
# margin. Pre-lockup era was deposit-only — no burns expected before that.
JUBILEE_SCAN_BLOCKS_BACK = 200_000

# 5M SNX sUSD-staking program principal unlock — confirmed via blog
# `susd-staks-5-million-snx-rewards`: 12-month lock from 2026-04-19 deposit deadline.
UNLOCK_DATE = date(2026, 4, 19)


def _scan_jubilee_burned() -> int:
    """Cumulative jubilee debt forgiven via on-chain TreasuryBurned events."""
    head = eth_block_number(RPC_MAINNET)
    from_block = max(0, head - JUBILEE_SCAN_BLOCKS_BACK)
    logs = eth_get_logs(
        RPC_MAINNET,
        address=TREASURY_MARKET_PROXY_MAINNET,
        topics=[TOPIC_TREASURY_BURNED],
        from_block=from_block,
        to_block=head,
        window_size=10_000,
    )
    total = sum(int(log["data"][2:66], 16) / 1e18 for log in logs)
    return int(round(total))


def collect() -> ScorecardSnapshot:
    # ── live: Treasury reserves ──────────────────────────────────────────────────
    print("[scorecard] reading Treasury sUSD balance from Mainnet RPC…")
    treasury_balance = erc20_balance_of(RPC_MAINNET, SUSD_MAINNET, TREASURY_AUX_RECIPIENT)
    print(f"[scorecard]   treasury sUSD: ${treasury_balance:,.2f}")

    # ── live: cumulative jubilee debt forgiven ──────────────────────────────────
    print("[scorecard] scanning TreasuryMarketProxy for TreasuryBurned events…")
    jubilee_burned_total = _scan_jubilee_burned()
    print(f"[scorecard]   jubilee burned (cumulative, last 200k blocks): ${jubilee_burned_total:,}")

    # ── live: time-anchor KPIs ──────────────────────────────────────────────────
    # Lockup ended 2026-04-19 (UNLOCK_DATE). 5M SNX rewards distribute linearly
    # over 3 months → release window ends ~2026-07-19. Past that, unmeasured
    # period begins; today's "days_remaining" goes negative which we clamp to 0
    # and the panel can interpret accordingly.
    today = date.today()
    days_since_unlock = (today - UNLOCK_DATE).days
    release_end_date = date(2026, 7, 19)
    days_remaining = max(0, (release_end_date - today).days)
    print(
        f"[scorecard]   days since unlock ({UNLOCK_DATE.isoformat()}): {days_since_unlock}  ·  "
        f"days remaining in 5M-SNX release window: {days_remaining}"
    )

    kpis = [
        KpiItem(
            id="treasury_reserves",
            label="420 Pool aux-recipient (Mainnet)",
            actual=int(round(treasury_balance)),
            target=None,
            unit="USD",
            status="verified",
            note=(
                "sUSD held at 0xFa1DF09… on Mainnet — the Treasury Market `aux_recipient` "
                "for the 420 Pool / Simple sUSD Staking Rewards program. Live balanceOf. "
                "This is one of two Treasury wallets holding the program's locked sUSD; "
                "see the 420 Pool bucket in the Capital Flow Map for the chain-wide total."
            ),
        ),
        KpiItem(
            id="snx_in_420_pool",
            label="SNX migrated to 420 Pool",
            actual="not measured",
            target=None,
            unit="text",
            status="context",
            note=(
                "Not measured — Mainnet uses legacy v2x architecture for the 420 Pool (SNX is "
                "not registered as a v3 collateral on Mainnet, verified 2026-05-04 via "
                "getCollateralConfiguration). Reading the figure would require a separate v2x "
                "integration. Out of scope for the peg-recovery dashboard: sUSD supply is fully "
                "captured by the 420 Pool bucket in the Capital Flow Map; SNX collateral "
                "mechanics are parallel to the peg story. Earlier 0.62 stub was an unsourced "
                "guess and has been removed."
            ),
        ),
        KpiItem(
            id="jubilee_burned",
            label="Jubilee debt forgiven",
            actual=jubilee_burned_total,
            target=60000000,
            unit="USD",
            status="verified",
            note=(
                "Live cumulative sum of TreasuryBurned events on TreasuryMarketProxy "
                "0x7b952507306E7D983bcFe6942Ac9F2f75C1332D8 over the last 200k Mainnet "
                "blocks (~28 days, covers the entire post-2026-04-19 unlock period). "
                "Currently $0 — and structurally expected. Synthetix contributor "
                "confirmed 2026-05-05 that burning requires a staker to be at 100% "
                "of their original debt collateralized in sUSD; most stakers are "
                "nowhere near that threshold, so $0 cumulative is mechanically "
                "expected, not a recovery failure. The earlier-reported '20% aux "
                "ratio' from the support bot was wrong (or conflated with the deposit "
                "minimum); the burn gate is 100%. Burns then linear over 12 months "
                "for eligible accounts. The figure will rise if/when (a) the cohort "
                "tops up to 100% of original debt or (b) the threshold is relaxed."
            ),
        ),
        KpiItem(
            id="jubilee_phase",
            label="Current jubilee phase",
            actual="Phase 2 — sUSD staking past $10M (live $18.5M)",
            target=None,
            unit="text",
            status="context",
            note=(
                "Synthetix team clarified (2026-05-04): the only on-record 'phase' "
                "framework is Phase 1 (Debt Migration complete) → Phase 2 (sUSD staking "
                "progress toward $10M target). NOT a numeric percentage — the 'Rebuilding "
                "sUSD' blog's 50%+10% biweekly schedule was either marketing simplification "
                "or referring to a different schedule. We're past the $10M staking target "
                "(verified $18.5M locked across the 2 Treasury wallets), so Phase 2's "
                "stated goal is satisfied. Phase 3 not on record."
            ),
        ),
        KpiItem(
            id="slp_fill",
            label="SLP sUSD deposits",
            actual=0,
            target=15000000,
            deadline="2026-06-30",
            unit="USD",
            status="stub",
            note=(
                "Synthetix contributor confirmed 2026-05-05 that the SLP Vault opens this "
                "quarter (~end of Q2 2026), accepts sUSD only, locks the deposits (no new "
                "minting), and the team's intent is for 'most of the sUSD supply to go here'. "
                "New contract — not a v3 vault. Currently $0 because the contract isn't live "
                "yet. Status will switch to 'verified' once the contract address is "
                "announced and we wire the live read. Target $15M by 2026-06-30 is the "
                "published roadmap goal; actual ambition appears materially higher."
            ),
        ),
        KpiItem(
            id="days_since_unlock",
            label="Days since unlock event",
            actual=f"{days_since_unlock} days",
            target=None,
            unit="text",
            status="context",
            note=f"Post-unlock window opened {UNLOCK_DATE.isoformat()} — see Sell-Pressure Radar.",
        ),
        KpiItem(
            id="days_remaining_release",
            label="Days remaining in release window",
            actual=f"~{days_remaining} days" if days_remaining > 0 else "ended",
            target=None,
            unit="text",
            status="context",
            note=(
                f"5M SNX rewards distribute linearly Apr 19 → ~Jul 19, 2026 (3-month window). "
                "Stakers in the program have a financial incentive to delay exit until close; "
                "expect inflow to the council's unstake queue to accelerate as the window "
                "approaches its end. After ~2026-07-19, this KPI flips to 'ended' and the "
                "Sell-Pressure Radar phase qualifier should transition out of 'interim'."
            ),
        ),
    ]

    return ScorecardSnapshot(as_of=now_iso(), kpis=kpis)


def main() -> int:
    snapshot = collect()
    # `exclude_unset=True` (not `exclude_none=True`): keep explicitly-set None
    # values (e.g. `target: null` for context KPIs) but drop fields we never
    # assigned (e.g. `velocity`, `deadline` on rows that don't have one).
    path = write_snapshot("scorecard", snapshot.model_dump(mode="json", exclude_unset=True))
    print(f"[scorecard] wrote {path}")
    print(f"[scorecard]   {len(snapshot.kpis)} KPIs (2 live, 1 closed, 3 context)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
