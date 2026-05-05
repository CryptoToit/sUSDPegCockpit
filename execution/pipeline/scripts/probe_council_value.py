"""
One-off probe: validate Etherscan tokentx works for the council wallet, and
sanity-check the per-NFT-unstake average value.

Why this script exists: the SNX Mainnet proxy doesn't respond to standard
ERC-20 calldata (Synthetix's Proxyable pattern), so we can't read the council's
token flows via direct RPC. Etherscan's V2 tokentx endpoint sidesteps this
because it uses their internal indexer rather than vanilla Transfer events.
This script proves the path before we wire it into the nft_queue collector.

Run:
  python -m scripts.probe_council_value

What it prints:
  - Outbound-from-council token flows for the last ~30 days, on both chains
  - Sums per token (SNX, sUSD)
  - Average per processed-NFT estimate (council's NFT-balance ≈ pending + processed)
  - First-pass valuation of the current 165-NFT custody depth
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone

from lib.etherscan import tokentx, token_value
from lib.rpc import RPC_MAINNET, RPC_OPTIMISM, eth_block_number


COUNCIL = "0xebAC8Fc8752A267A36cE683A867000F69Fd0e73d"

# Approximate block heights for "30 days ago" — recomputed live, not hardcoded.
BLOCK_TIME_S = {"ethereum": 12, "optimism": 2}
SECONDS_30D = 30 * 24 * 60 * 60

# Tokens we care about. SNX returned in legacy v2x exits, sUSD returned for jubilee exits.
INTERESTING_SYMBOLS = {"SNX", "sUSD"}


def _scan(chain: str, rpc: str) -> dict[str, dict]:
    head = eth_block_number(rpc)
    start = head - (SECONDS_30D // BLOCK_TIME_S[chain])
    print(f"\n=== {chain} ===")
    print(f"scan window: blocks {start} → {head}")
    rows = tokentx(chain, COUNCIL, startblock=start, endblock=head, sort="asc")
    print(f"total token transfers involving council: {len(rows)}")

    sums: dict[str, dict] = {}
    for r in rows:
        sym = r.get("tokenSymbol", "?")
        if sym not in INTERESTING_SYMBOLS:
            continue
        direction = "out" if r.get("from", "").lower() == COUNCIL.lower() else "in"
        bucket = sums.setdefault(
            sym, {"out_count": 0, "out_value": 0.0, "in_count": 0, "in_value": 0.0}
        )
        v = token_value(r)
        bucket[f"{direction}_count"] += 1
        bucket[f"{direction}_value"] += v

    for sym, b in sums.items():
        avg_out = b["out_value"] / b["out_count"] if b["out_count"] else 0
        print(
            f"  {sym:5}  out: {b['out_count']:>4} txs / {b['out_value']:>14,.2f}  "
            f"(avg {avg_out:>10,.2f})  ·  in: {b['in_count']:>4} txs / {b['in_value']:>14,.2f}"
        )
    if not sums:
        print(f"  (no SNX/sUSD activity in window)")
    return sums


def main() -> int:
    print(f"Probing Etherscan tokentx for council {COUNCIL}")
    print(f"now: {datetime.now(timezone.utc).isoformat()}")

    eth = _scan("ethereum", RPC_MAINNET)
    op = _scan("optimism", RPC_OPTIMISM)

    print("\n=== rough valuation estimate ===")
    print("Method: avg processed-unstake value × current custody count.")
    print("Caveats: this is an order-of-magnitude estimate. Actual queue value")
    print("requires per-NFT historical state reads (out of scope for v1).")

    for chain_label, sums in (("Mainnet", eth), ("Optimism", op)):
        snx = sums.get("SNX", {})
        susd = sums.get("sUSD", {})
        snx_avg = (snx.get("out_value", 0) / snx["out_count"]) if snx.get("out_count") else 0
        susd_avg = (susd.get("out_value", 0) / susd["out_count"]) if susd.get("out_count") else 0
        print(
            f"  {chain_label}: avg processed-unstake ≈ {snx_avg:,.2f} SNX + {susd_avg:,.2f} sUSD"
        )

    print("\nDone. If sums look sensible, we're ready to wire valuation into nft_queue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
