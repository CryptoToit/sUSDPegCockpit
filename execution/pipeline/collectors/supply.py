"""
Issued Supply collector.

Fetches sUSD circulating supply from DefiLlama's stablecoins API (id=22 = legacy
Synthetix sUSD), maps the chain breakdown to our internal slugs, and writes the
snapshot.

DefiLlama validated against direct on-chain `totalSupply()` reads in earlier
recon sessions to within ~$4K (well under 0.01%) — treated as authoritative for
this collector.

Run:
  python -m collectors.supply
"""
from __future__ import annotations

import sys

from lib.http import get_json
from lib.snapshot import now_iso, write_snapshot
from schemas.supply import SupplySnapshot


# DefiLlama stablecoin id 22 = legacy Synthetix sUSD.
# (Don't confuse with id 216 = Solayer sUSD, a separate token.)
STABLECOIN_ID = 22

# Map DefiLlama's chain naming to our internal slug. Chains we don't display
# (Arbitrum dust ~$673, Fantom dust ~$59, Ontology $0) are intentionally omitted.
CHAIN_SLUG = {
    "Ethereum": "ethereum",
    "OP Mainnet": "optimism",
}


def collect() -> SupplySnapshot:
    print("[supply] fetching DefiLlama stablecoin id=22 (legacy Synthetix sUSD)…")
    data = get_json(f"https://stablecoins.llama.fi/stablecoin/{STABLECOIN_ID}")

    chain_balances = data.get("chainBalances") or {}
    by_chain: dict[str, int] = {}
    for chain_name, payload in chain_balances.items():
        slug = CHAIN_SLUG.get(chain_name)
        if slug is None:
            continue  # Skip dust chains (Arbitrum, Fantom, Ontology)
        tokens = payload.get("tokens") or []
        if not tokens:
            continue
        last = tokens[-1]
        circulating = (last.get("circulating") or {}).get("peggedUSD")
        if circulating is None or circulating <= 0:
            continue
        by_chain[slug] = int(round(circulating))

    if not by_chain:
        raise RuntimeError(f"No tracked-chain supply data returned by DefiLlama: {chain_balances}")

    total = sum(by_chain.values())
    return SupplySnapshot(
        as_of=now_iso(),
        total_supply_susd=total,
        supply_by_chain=by_chain,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("supply", snapshot.model_dump(mode="json"))
    print(f"[supply] wrote {path}")
    print(f"[supply]   total supply: ${snapshot.total_supply_susd:,}")
    for slug, value in snapshot.supply_by_chain.items():
        pct = (value / snapshot.total_supply_susd) * 100
        print(f"[supply]   {slug:10} ${value:>14,}  ({pct:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
