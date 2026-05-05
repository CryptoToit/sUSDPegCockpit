"""
Unstake Queue collector.

Tracks the inbound side of Synthetix's manual unstake-processing flow by scanning
ERC-721 `Transfer` events on the Synthetix Account NFT (SACCT) contract where
`to == 0xebAC8…d` (the council/Treasury wallet that processes manual unstakes).

Why this exists:
  Stakers exit Synthetix positions by transferring their Account NFT to the council
  wallet, where the team manually returns SNX (and sUSD, for 420 Pool jubilee exits)
  to the staker's wallet. This produces a queue of pending claims that's invisible
  on standard Synthetix dashboards. We surface the inbound rate as the upstream
  signal of pending sell-pressure releases. v2x-confirmed first-hand 2026-05-05.

What we read:
  - SACCT contract (same address both chains via CREATE2): 0x0E429603…77Dac
  - ERC-721 Transfer event filtered on topic[2] (indexed `to`) = council wallet
  - Both Mainnet + Optimism, 30d window split into 24h / 7d / 30d buckets

What v1 does NOT cover:
  - Round-trip latency (NFT in → SNX out): the Mainnet SNX proxy uses Synthetix's
    non-standard Proxyable event pattern, so per-EOA matching needs more work.
    Deferred to v2. The Sell-Pressure Radar already shows the sUSD-outbound side
    for jubilee-program exits.
  - Per-token underlying value: requires per-tokenId state reads against the v2x
    or v3 staking contract.

Run:
  python -m collectors.nft_queue
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from lib.rpc import (
    RPC_MAINNET,
    RPC_OPTIMISM,
    eth_block_number,
    eth_get_logs,
)
from lib.snapshot import now_iso, write_snapshot
from schemas.nft_queue import NftQueueSnapshot, ChainWindow, InboundEvent


COUNCIL_WALLET = "0xebAC8Fc8752A267A36cE683A867000F69Fd0e73d"
SACCT_ADDRESS = "0x0E429603D3Cb1DFae4E6F52Add5fE82d96d77Dac"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Approximate block times (matches radar.py)
BLOCK_TIME_S = {"ethereum": 12, "optimism": 2}

SECONDS_24H = 24 * 60 * 60
SECONDS_7D = 7 * 24 * 60 * 60
SECONDS_30D = 30 * 24 * 60 * 60

# Show the most recent N inbound events in the snapshot for an inspection table.
RECENT_EVENTS_LIMIT = 20


def _topic_from_addr(addr: str) -> str:
    return "0x000000000000000000000000" + addr[2:].lower()


def _scan_chain(chain: str, rpc: str) -> tuple[ChainWindow, list[InboundEvent]]:
    """Scan SACCT inbound events to council on `chain` over a 30d window."""
    blk_per_s = BLOCK_TIME_S[chain]
    head = eth_block_number(rpc)
    blocks_30d = SECONDS_30D // blk_per_s
    blocks_7d = SECONDS_7D // blk_per_s
    blocks_24h = SECONDS_24H // blk_per_s
    threshold_7d = head - blocks_7d
    threshold_24h = head - blocks_24h
    from_block = head - blocks_30d

    to_topic = _topic_from_addr(COUNCIL_WALLET)
    logs = eth_get_logs(
        rpc,
        address=SACCT_ADDRESS,
        topics=[TRANSFER_TOPIC, None, to_topic],
        from_block=from_block,
        to_block=head,
    )

    addrs_24h: set[str] = set()
    addrs_7d: set[str] = set()
    addrs_30d: set[str] = set()
    n_24h = n_7d = n_30d = 0
    events: list[InboundEvent] = []

    for log in logs:
        block_num = int(log["blockNumber"], 16)
        from_addr_raw = log["topics"][1]
        from_addr = "0x" + from_addr_raw[26:].lower()
        token_id = int(log["topics"][3], 16)
        tx_hash = log["transactionHash"]

        n_30d += 1
        addrs_30d.add(from_addr)
        if block_num >= threshold_7d:
            n_7d += 1
            addrs_7d.add(from_addr)
        if block_num >= threshold_24h:
            n_24h += 1
            addrs_24h.add(from_addr)

        events.append(
            InboundEvent(
                chain=chain,
                block_number=block_num,
                tx_hash=tx_hash,
                from_address=from_addr,
                token_id=str(token_id),
            )
        )

    window = ChainWindow(
        nfts_in_24h=n_24h,
        nfts_in_7d=n_7d,
        nfts_in_30d=n_30d,
        unique_addrs_24h=len(addrs_24h),
        unique_addrs_7d=len(addrs_7d),
        unique_addrs_30d=len(addrs_30d),
    )
    print(
        f"[nft_queue] {chain:8} inbound: 24h={n_24h:>3}  7d={n_7d:>3}  30d={n_30d:>4}  "
        f"unique30d={len(addrs_30d):>3}"
    )
    return window, events


def collect() -> NftQueueSnapshot:
    print("[nft_queue] scanning SACCT inbound to council on Mainnet…")
    try:
        eth_window, eth_events = _scan_chain("ethereum", RPC_MAINNET)
    except Exception as exc:
        print(f"[nft_queue] WARN Mainnet scan failed: {exc}")
        eth_window = ChainWindow(
            nfts_in_24h=0, nfts_in_7d=0, nfts_in_30d=0,
            unique_addrs_24h=0, unique_addrs_7d=0, unique_addrs_30d=0,
        )
        eth_events = []

    print("[nft_queue] scanning SACCT inbound to council on Optimism…")
    try:
        op_window, op_events = _scan_chain("optimism", RPC_OPTIMISM)
    except Exception as exc:
        print(f"[nft_queue] WARN Optimism scan failed: {exc}")
        op_window = ChainWindow(
            nfts_in_24h=0, nfts_in_7d=0, nfts_in_30d=0,
            unique_addrs_24h=0, unique_addrs_7d=0, unique_addrs_30d=0,
        )
        op_events = []

    all_events = eth_events + op_events
    all_events.sort(key=lambda e: e.block_number, reverse=True)
    recent = all_events[:RECENT_EVENTS_LIMIT]

    total_24h = eth_window.nfts_in_24h + op_window.nfts_in_24h
    total_7d = eth_window.nfts_in_7d + op_window.nfts_in_7d
    total_30d = eth_window.nfts_in_30d + op_window.nfts_in_30d

    return NftQueueSnapshot(
        as_of=now_iso(),
        council_wallet=COUNCIL_WALLET,
        sacct_address=SACCT_ADDRESS,
        chains={"ethereum": eth_window, "optimism": op_window},
        total_nfts_in_24h=total_24h,
        total_nfts_in_7d=total_7d,
        total_nfts_in_30d=total_30d,
        recent_inbound=recent,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("nft_queue", snapshot.model_dump(mode="json"))
    print(f"[nft_queue] wrote {path}")
    print(
        f"[nft_queue]   totals: 24h={snapshot.total_nfts_in_24h}  "
        f"7d={snapshot.total_nfts_in_7d}  30d={snapshot.total_nfts_in_30d}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
