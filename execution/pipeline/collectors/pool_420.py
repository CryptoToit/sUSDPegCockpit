"""
420 Pool / "Treasury Pool" (Pool ID 8) custody collector.

The 420 Pool architecture is misleadingly named: pool 8 holds **SNX as collateral**,
and sUSD is an **auxiliary deposit** that's transferred directly to two Synthetix
Treasury wallets — NOT held in v3 vault state. So the locked-sUSD figure is a sum
of plain ERC-20 `balanceOf` reads on those treasury wallets, on both chains.

Authoritative reference: project memory `project_susd_420_pool_architecture.md`.
Verified against omnibus tomls in `Synthetixio/synthetix-deployments`.

Sources:
  - sUSD reads:   ERC-20 `balanceOf` on the two treasury wallets (both chains)
  - SNX reads:    Core Proxy `getVaultCollateral(8, SNX)` — pool 8's SNX collateral

Run:
  python -m collectors.pool_420
"""
from __future__ import annotations

import sys

from lib.rpc import RPC_MAINNET, RPC_OPTIMISM, eth_call, erc20_balance_of
from lib.snapshot import now_iso, write_snapshot
from schemas.pool_420 import Pool420ChainBreakdown, Pool420Snapshot, TreasuryBalance


POOL_ID = 8

# sUSD ERC-20 (legacy Synthetix sUSD).
SUSD_MAINNET = "0x57Ab1ec28D129707052df4dF418D58a2D46d5f51"
SUSD_OPTIMISM = "0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9"

# v3 Core Proxy — same address on both chains via CREATE2.
CORE_PROXY = "0xefaCa6Fc316B3B2Aa6c55FF5E02a62A85d4391e8"

# SNX (legacy Synthetix Network Token).
SNX_MAINNET = "0xC011a73ee7576c2Ae67b1d1B3a5a40b2Bdcd3a6f"
SNX_OPTIMISM = "0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4"

# Synthetix Treasury wallets that hold the program's locked sUSD.
# #1 also receives v3 Account NFTs from manual-unstake transfers.
# #2 is the omnibus `settings.treasury` (aux_recipient).
TREASURIES = [
    {
        "address": "0xebAC8Fc8752A267A36cE683A867000F69Fd0e73d",
        "label": "Synthetix Treasury (NFT custody)",
    },
    {
        "address": "0xFa1DF09D8d09D6E8FAB2a6C4712fEa02ce203e99",
        "label": "Synthetix Treasury (aux recipient)",
    },
]

# Selector for `getVaultCollateral(uint128 poolId, address collateralType)`.
GET_VAULT_COLLATERAL = "0x078145a8"


def _encode_get_vault_collateral(pool_id: int, collateral: str) -> str:
    pool_padded = format(pool_id, "x").rjust(64, "0")
    addr_padded = collateral.lower().replace("0x", "").rjust(64, "0")
    return GET_VAULT_COLLATERAL + pool_padded + addr_padded


def _read_snx_collateral(rpc: str, snx_addr: str) -> tuple[float, float] | None:
    """
    Returns (collateral_amount, collateral_value_usd) or None.

    Returns None on Mainnet: SNX is NOT registered as a v3 collateral type on Mainnet
    (`getCollateralConfiguration` returns zeros), so the vault read reverts with the
    Synthetix-internal error `0x23a9bbc9` (collateral-type-not-configured). On Mainnet
    the 420 Pool's SNX is held in legacy v2x architecture, not v3 vault state — a
    separate v2x-side read path would be needed to surface that figure here.

    On Optimism the call succeeds; pool 8's SNX vault returns (0, 0) currently
    because no SNX has been delegated to v3 pool 8 on OP (consistent with OP's
    deprecation in favour of Mainnet for sUSD operations).
    """
    try:
        data = _encode_get_vault_collateral(POOL_ID, snx_addr)
        result = eth_call(rpc, CORE_PROXY, data)
    except Exception as e:
        print(f"[pool_420]   getVaultCollateral skipped (expected on Mainnet — SNX not v3-registered): {e}")
        return None
    h = result[2:] if result.startswith("0x") else result
    if len(h) < 128:
        return None
    return (int(h[:64], 16) / 1e18, int(h[64:128], 16) / 1e18)


def _collect_chain(chain: str, rpc: str, susd_addr: str, snx_addr: str) -> Pool420ChainBreakdown:
    treasuries: list[TreasuryBalance] = []
    for t in TREASURIES:
        amount = erc20_balance_of(rpc, susd_addr, t["address"])
        treasuries.append(
            TreasuryBalance(
                address=t["address"],
                label=t["label"],
                susd_amount=int(round(amount)),
            )
        )
    susd_total = sum(t.susd_amount for t in treasuries)

    snx_amount: float | None = None
    snx_value_usd: int | None = None
    snx = _read_snx_collateral(rpc, snx_addr)
    if snx is not None:
        snx_amount = round(snx[0], 2)
        snx_value_usd = int(round(snx[1]))

    return Pool420ChainBreakdown(
        chain=chain,
        treasuries=treasuries,
        susd_total=susd_total,
        snx_amount=snx_amount,
        snx_value_usd=snx_value_usd,
    )


def collect() -> Pool420Snapshot:
    print("[pool_420] reading sUSD balances on Synthetix Treasury wallets…")
    chains = [
        _collect_chain("ethereum", RPC_MAINNET, SUSD_MAINNET, SNX_MAINNET),
        _collect_chain("optimism", RPC_OPTIMISM, SUSD_OPTIMISM, SNX_OPTIMISM),
    ]
    return Pool420Snapshot(
        as_of=now_iso(),
        pool_id=POOL_ID,
        susd_total=sum(c.susd_total for c in chains),
        chains=chains,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("pool_420", snapshot.model_dump(mode="json"))
    print(f"[pool_420] wrote {path}")
    print(f"[pool_420]   pool ID:      {snapshot.pool_id}")
    print(f"[pool_420]   sUSD total:   ${snapshot.susd_total:,}")
    for c in snapshot.chains:
        line = f"[pool_420]   {c.chain:9} sUSD ${c.susd_total:>13,}"
        if c.snx_amount is not None:
            line += f"   SNX {c.snx_amount:,.2f}"
            if c.snx_value_usd is not None:
                line += f" (${c.snx_value_usd:,})"
        print(line)
        for t in c.treasuries:
            print(f"[pool_420]     {t.label}: ${t.susd_amount:>13,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
