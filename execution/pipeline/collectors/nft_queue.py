"""
Unstake Queue collector.

Tracks two sides of Synthetix's manual unstake-processing flow:

  (a) INBOUND — ERC-721 `Transfer` events on the Synthetix Account NFT (SACCT)
      where `to == 0xebAC8…d` (the council/Treasury wallet). These are stakers
      queueing their positions for manual processing.

  (b) DISBURSEMENT — historical SNX + sUSD outflows from the council wallet to
      non-treasury addresses (i.e., to actual stakers). Read via Etherscan /
      Blockscout `tokentx` endpoints because Synthetix's SNX proxy uses a
      non-standard Proxyable event pattern that direct eth_getLogs can't see.

Custody is read live as `SACCT.balanceOf(council)` on both chains.

Phase 2 (this version) adds USD valuation: avg disbursement value × pending
count, using a 180-day disbursement window for stable averages and the
current SNX price from DefiLlama. Internal Treasury shuffles (transfers
between the two Treasury wallets, or to the liquidator) are filtered out
of the disbursement set.

Phase 3 will add per-EOA pairing for processing-lag distribution. Phase 4
will add post-disbursement DEX attribution.

Run:
  python -m collectors.nft_queue
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone

from lib.etherscan import token_value, tokennfttx, tokentx
from lib.http import get_json
from lib.rpc import (
    RPC_MAINNET,
    RPC_OPTIMISM,
    eth_block_number,
    eth_call,
    eth_get_logs,
)
from lib.snapshot import now_iso, write_snapshot
from schemas.nft_queue import (
    ChainValuation,
    ChainWindow,
    DisbursementStats,
    InboundEvent,
    LagStats,
    NftQueueSnapshot,
    PostReleaseStats,
)


COUNCIL_WALLET = "0xebAC8Fc8752A267A36cE683A867000F69Fd0e73d"
SACCT_ADDRESS = "0x0E429603D3Cb1DFae4E6F52Add5fE82d96d77Dac"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Synthetix-related addresses to exclude from "disbursement to user" classification:
# transfers between these and the council are internal shuffles, not user payouts.
TREASURY_INTERNAL = {
    "0xebac8fc8752a267a36ce683a867000f69fd0e73d",  # council itself (self-loops)
    "0xfa1df09d8d09d6e8fab2a6c4712fea02ce203e99",  # other Treasury (omnibus aux_recipient)
    "0x9daffb42b60bb14d8ee80b503aafc312dcbaf552",  # treasury liquidator
}

# DefiLlama identifiers for SNX, in fallback order. Mainnet SNX address doesn't
# resolve on DefiLlama (Synthetix's non-standard Proxyable token pattern), so we
# try OP SNX (a clean ERC-20) first, then the coingecko:havven legacy ID. Same
# price applies to both chains since SNX is bridged at parity.
SNX_PRICE_IDS = (
    "optimism:0x8700dAec35aF8Ff88c16BdF0418774CB3D7599B4",
    "coingecko:havven",
)

# Approximate block times (matches radar.py)
BLOCK_TIME_S = {"ethereum": 12, "optimism": 2}

SECONDS_24H = 24 * 60 * 60
SECONDS_7D = 7 * 24 * 60 * 60
SECONDS_30D = 30 * 24 * 60 * 60
SECONDS_180D = 180 * 24 * 60 * 60

# Show the most recent N inbound events in the snapshot for an inspection table.
RECENT_EVENTS_LIMIT = 20

# Tokens we count as user-facing disbursements
DISBURSEMENT_SYMBOLS = {"SNX", "sUSD"}

# Curated set of "sell-route" destination addresses per chain. Outflows from a
# disbursement recipient to any of these are treated as observed sell pressure.
# Includes:
#   1) DEX routers (where users actively swap)
#   2) Major sUSD/SNX pool addresses (direct-to-pool swaps)
#   3) Known CEX deposit/hot-wallet addresses (selling on a centralized venue)
#   4) Bridges (cross-chain → likely sold elsewhere)
# Lowercase. NOT exhaustive — observed sell-share is a LOWER BOUND, not a
# precise figure. CEX address lists need periodic refresh as exchanges rotate
# hot wallets. Sources: Etherscan public tags, our own peg.py pool addresses.
SELL_ROUTE_ADDRESSES: dict[str, set[str]] = {
    "ethereum": {
        # === DEX routers ===
        "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2 Router
        "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3 SwapRouter
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap SwapRouter02
        "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b",  # Uniswap Universal Router v1
        "0x66a9893cc07d91d95644aedd05d03f95e1dba8af",  # Uniswap Universal Router v1.2
        "0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f",  # Sushiswap Router
        "0x1111111254eeb25477b68fb85ed929f73a960582",  # 1inch v5
        "0x111111125421ca6dc452d289314280a0f8842a65",  # 1inch v6
        "0xdef171fe48cf0115b1d80b88dc8eab59176fee57",  # ParaSwap v5
        "0x6131b5fae19ea4f9d964eac0408e4408b66337b5",  # KyberSwap MetaAggregator
        "0xdef1c0ded9bec7f1a1670819833240f027b25eff",  # 0x Exchange Proxy
        # === Major sUSD / SNX pools (direct swaps) ===
        "0xa3ccaf08a54cf31649f91ae1570a0720c8d4eb1e",  # Uniswap V3 sUSD/SNX
        "0xf80758ab42c3b07da84053fd88804bcb6baa4b5c",  # Uniswap V2 sUSD/WETH
        "0xf1f85b2c54a2bd284b1cf4141d64fd171bd85539",  # Sushiswap sUSD/WETH
        "0x94cc50e4521bd271c1a997a3a4dc815c2f920b41",  # Curve sUSD/crvUSD
        "0xa5407eae9ba41422680e2e00537571bcc53efbfd",  # Curve sUSDv2 (sUSD/DAI/USDC/USDT)
        # === Major CEX hot wallets (Etherscan-tagged) ===
        # Binance
        "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # Binance 15
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",  # Binance 16
        "0x56eddb7aa87536c09ccc2793473599fd21a8b17f",  # Binance 17
        "0x9696f59e4d72e237be84ffd425dcad154bf96976",  # Binance 18
        "0x4976a4a02f38326660d17bf34b431dc6e2eb2327",  # Binance 19
        "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67",  # Binance 20
        "0xae2d4617c862309a3d75a0ffb358c7a5009c673f",  # Binance 21
        "0x5a52e96bacdabb82fd05763e25335261b270efcb",  # Binance 27
        "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8",  # Binance 7
        "0xf977814e90da44bfa03b6295a0616a897441acec",  # Binance 8
        # Coinbase
        "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",  # Coinbase 1
        "0x503828976d22510aad0201ac7ec88293211d23da",  # Coinbase 2
        "0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740",  # Coinbase 3
        "0x3cd751e6b0078be393132286c442345e5dc49699",  # Coinbase 4
        # Kraken
        "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",  # Kraken 1
        "0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13",  # Kraken 4
        "0xe853c56864a2ebe4576a807d26fdc4a0ada51919",  # Kraken 5
        # OKX
        "0xa7efae728d2936e78bda97dc267687568dd593f3",  # OKX 1
        "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b",  # OKX 4
        "0x868dab0b8e21ec0a48b76a7dbb66dcbf67855eef",  # OKX 5
        "0x539c92186f7c6cc4cbf443f26ef84c595babbca1",  # OKX 6
        # Bybit / Bitfinex / Gate / Crypto.com
        "0xf89d7b9c864f589bbf53a82105107622b35eaa40",  # Bybit 1
        "0x1151314c646ce4e0efd76d1af4760ae66a9fe30f",  # Bitfinex 5
        "0xc882b111a75c0c657fc507c04fbfcd2cc984f071",  # Gate.io
        "0x6262998ced04146fa42253a5c0af90ca02dfd2a3",  # Crypto.com 1
        # === Bridges (cross-chain routing) ===
        "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1",  # Optimism Standard Bridge
    },
    "optimism": {
        # === DEX routers ===
        "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap SwapRouter02
        "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b",  # Uniswap Universal Router
        "0xa062ae8a9c5e11aaa026fc2670b0d65ccc8b2858",  # Velodrome V2 Router
        "0x1111111254eeb25477b68fb85ed929f73a960582",  # 1inch v5
        "0x111111125421ca6dc452d289314280a0f8842a65",  # 1inch v6
        # === Major sUSD pools (direct swaps) ===
        "0xbc26519f936a90e78fe2c9aa2a03cc208f041234",  # Velodrome V2 USDC/sUSD
        "0xadb35413ec50e0afe41039eac8b930d313e94fa4",  # Uniswap V3 sUSD/DAI
        "0x2e80d5a7b3c613d854ee43243ff09808108561eb",  # Uniswap V3 WETH/sUSD
        "0x061b87122ed14b9526a813209c8a59a633257bab",  # Curve sUSD/3CRV (OP)
        # === CEX hot wallets on OP (smaller list — most exchanges concentrate Mainnet) ===
        "0xacd03d601e5bb1b275bb94076ff46ed9d753435a",  # Binance OP
        "0x6e3edb20f55ce3f0f4fc3a36c5ed4e98e2a3e6a7",  # OKX OP (best-effort)
        # === Bridges ===
        "0x4200000000000000000000000000000000000010",  # OP Standard Bridge (L2 side)
    },
}


def _topic_from_addr(addr: str) -> str:
    return "0x000000000000000000000000" + addr[2:].lower()


def _erc721_balance_of(rpc: str, contract: str, holder: str) -> int:
    """ERC-721 `balanceOf(holder)` — count of NFTs the holder currently owns."""
    addr_clean = holder.lower().replace("0x", "").rjust(64, "0")
    data = "0x70a08231" + addr_clean
    raw_hex = eth_call(rpc, contract, data)
    return int(raw_hex, 16)


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


def _custody_count(chain: str, rpc: str) -> int:
    """Live count of SACCT NFTs currently held by the council wallet."""
    try:
        n = _erc721_balance_of(rpc, SACCT_ADDRESS, COUNCIL_WALLET)
        print(f"[nft_queue] {chain:8} council custody: {n} NFTs")
        return n
    except Exception as exc:
        print(f"[nft_queue] WARN custody read on {chain} failed: {exc}")
        return 0


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolation percentile on a pre-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    lo = int(rank)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (rank - lo)


def _scan_disbursements(
    chain: str, rpc: str
) -> tuple[dict[str, DisbursementStats], list[dict]]:
    """
    Pull SNX + sUSD outflows from the council wallet over the last 180 days,
    excluding internal Treasury shuffles. Returns (per-token stats, raw rows)
    so callers can reuse the rows for downstream pairing without re-querying.
    """
    head = eth_block_number(rpc)
    start_block = max(0, head - (SECONDS_180D // BLOCK_TIME_S[chain]))
    rows = tokentx(chain, COUNCIL_WALLET, startblock=start_block, endblock=head, sort="asc")

    by_token: dict[str, dict] = defaultdict(
        lambda: {"values": [], "recipients": set()}
    )
    council_lc = COUNCIL_WALLET.lower()
    for r in rows:
        sym = r.get("tokenSymbol", "?")
        if sym not in DISBURSEMENT_SYMBOLS:
            continue
        if (r.get("from") or "").lower() != council_lc:
            continue  # inbound (treasury top-up), not a disbursement
        to = (r.get("to") or "").lower()
        if to in TREASURY_INTERNAL:
            continue  # internal shuffle
        v = token_value(r)
        if v <= 0:
            continue
        by_token[sym]["values"].append(v)
        by_token[sym]["recipients"].add(to)

    out: dict[str, DisbursementStats] = {}
    for sym, b in by_token.items():
        vals = sorted(b["values"])
        n = len(vals)
        out[sym] = DisbursementStats(
            count=n,
            unique_recipients=len(b["recipients"]),
            total=round(sum(vals), 4),
            mean=round(sum(vals) / n, 4) if n else 0.0,
            median=round(vals[n // 2], 4) if n else 0.0,
            p25=round(_percentile(vals, 0.25), 4) if n else 0.0,
            p75=round(_percentile(vals, 0.75), 4) if n else 0.0,
        )
    print(
        f"[nft_queue] {chain:8} disbursements (180d): "
        + ", ".join(
            f"{sym} n={s.count} mean={s.mean:,.0f}" for sym, s in out.items()
        )
    )
    return out, rows


def _fetch_snx_price_usd() -> float:
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
            print(f"[nft_queue] WARN SNX price fetch via {ident} failed: {exc}")
    print("[nft_queue] WARN all SNX price sources returned empty")
    return 0.0


def _value_chain(
    custody: int,
    disb: dict[str, DisbursementStats],
    snx_price_usd: float,
) -> ChainValuation:
    """
    Compute a USD-value estimate for a chain's pending custody.

    Method: split the pending count proportionally by historical processing mix
    (SNX disbursements vs sUSD disbursements over 180d), then apply each token's
    mean disbursement value, then convert to USD.
    """
    snx = disb.get("SNX")
    susd = disb.get("sUSD")
    snx_count = snx.count if snx else 0
    susd_count = susd.count if susd else 0
    total_processed = snx_count + susd_count

    if total_processed == 0 or custody == 0:
        return ChainValuation(
            estimated_usd=0,
            estimated_snx_value_usd=0,
            estimated_susd_value_usd=0,
            sample_n=total_processed,
            snx_price_usd=round(snx_price_usd, 4),
        )

    # Pending split = historical processing split
    snx_share = snx_count / total_processed
    susd_share = susd_count / total_processed
    pending_snx = custody * snx_share
    pending_susd = custody * susd_share

    snx_mean = snx.mean if snx else 0.0
    susd_mean = susd.mean if susd else 0.0

    snx_usd = pending_snx * snx_mean * snx_price_usd
    susd_usd = pending_susd * susd_mean  # sUSD ≈ $1 (we let actual peg drift wash through)

    return ChainValuation(
        estimated_usd=int(round(snx_usd + susd_usd)),
        estimated_snx_value_usd=int(round(snx_usd)),
        estimated_susd_value_usd=int(round(susd_usd)),
        sample_n=total_processed,
        snx_price_usd=round(snx_price_usd, 4),
    )


def _scan_inbound_180d(chain: str, rpc: str) -> list[dict]:
    """
    Pull SACCT inbound events to council over 180d via Etherscan/Blockscout
    tokennfttx (much faster than RPC eth_getLogs at this window size).
    Returns rows with from_address + blockNumber + timeStamp.
    """
    head = eth_block_number(rpc)
    start_block = max(0, head - (SECONDS_180D // BLOCK_TIME_S[chain]))
    rows = tokennfttx(
        chain, COUNCIL_WALLET,
        contractaddress=SACCT_ADDRESS,
        startblock=start_block, endblock=head, sort="asc",
    )
    council_lc = COUNCIL_WALLET.lower()
    inbounds = [r for r in rows if (r.get("to") or "").lower() == council_lc]
    print(f"[nft_queue] {chain:8} 180d inbound NFTs (for lag pairing): {len(inbounds)}")
    return inbounds


def _pair_lag(
    chain: str,
    inbounds: list[dict],
    disbursement_rows: list[dict],
) -> tuple[LagStats, list[float]]:
    """
    Per-EOA chronological matching of NFT inbound to subsequent council outflow.

    Algorithm: for each EOA, sort inbounds and outflows chronologically; pair
    up in order. Inbound[i] from EOA X matches outflow[i] to EOA X — provided
    outflow[i] is at a later block than inbound[i]. Unmatched inbounds = pending.

    Returns (LagStats, raw_lag_seconds_list) for downstream histogram if needed.
    """
    council_lc = COUNCIL_WALLET.lower()
    block_s = BLOCK_TIME_S[chain]

    # Group inbounds by EOA, sorted by block
    in_by_eoa: dict[str, list[int]] = defaultdict(list)
    for r in inbounds:
        from_addr = (r.get("from") or "").lower()
        if not from_addr:
            continue
        in_by_eoa[from_addr].append(int(r["blockNumber"]))
    for blocks in in_by_eoa.values():
        blocks.sort()

    # Group outflows by recipient EOA, sorted by block.
    # Filter: only token symbols we care about (SNX/sUSD), only outbound from council,
    # only to non-internal addresses (already done upstream but defensive here).
    out_by_eoa: dict[str, list[int]] = defaultdict(list)
    for r in disbursement_rows:
        sym = r.get("tokenSymbol", "?")
        if sym not in DISBURSEMENT_SYMBOLS:
            continue
        if (r.get("from") or "").lower() != council_lc:
            continue
        to = (r.get("to") or "").lower()
        if not to or to in TREASURY_INTERNAL:
            continue
        out_by_eoa[to].append(int(r["blockNumber"]))
    for blocks in out_by_eoa.values():
        blocks.sort()

    lag_seconds: list[float] = []
    pending = 0
    for eoa, in_blocks in in_by_eoa.items():
        out_blocks = out_by_eoa.get(eoa, [])
        oi = 0
        for in_blk in in_blocks:
            # Advance the outbound cursor to the first outbound at a later block
            while oi < len(out_blocks) and out_blocks[oi] <= in_blk:
                oi += 1
            if oi < len(out_blocks):
                lag_blocks = out_blocks[oi] - in_blk
                lag_seconds.append(lag_blocks * block_s)
                oi += 1  # consume this outbound
            else:
                pending += 1

    sample_n = len(lag_seconds)
    sorted_lags = sorted(lag_seconds)
    median = _percentile(sorted_lags, 0.5) if sample_n else 0.0
    p25 = _percentile(sorted_lags, 0.25) if sample_n else 0.0
    p75 = _percentile(sorted_lags, 0.75) if sample_n else 0.0

    stats = LagStats(
        sample_n=sample_n,
        pending_count=pending,
        median_hours=round(median / 3600, 2),
        p25_hours=round(p25 / 3600, 2),
        p75_hours=round(p75 / 3600, 2),
    )
    print(
        f"[nft_queue] {chain:8} lag (180d): n={sample_n} pending={pending}  "
        f"median={stats.median_hours}h  p25={stats.p25_hours}h  p75={stats.p75_hours}h"
    )
    return stats, lag_seconds


def _scan_post_release(
    chain: str,
    disbursement_rows: list[dict],
    snx_price_usd: float,
) -> PostReleaseStats:
    """
    For each council disbursement recipient, scan their subsequent token
    transfers for SNX/sUSD outflows to known DEX addresses.

    Returns aggregate stats: per-token disbursed/to-dex amounts and shares,
    plus a USD-weighted observed sell-through share.

    Caveats: this is a LOWER BOUND on actual selling. Recipients who use
    private mempool, swap through addresses we haven't curated, bridge to
    another chain before selling, or route via contract wallets we can't
    trace will be classified as "held" even if they did sell. Treat the
    sell_share as a directional indicator, not a precise figure.
    """
    council_lc = COUNCIL_WALLET.lower()
    dex_addrs = SELL_ROUTE_ADDRESSES.get(chain.lower(), set())
    if not dex_addrs:
        return PostReleaseStats(
            recipients_scanned=0, snx_received=0, snx_to_dex=0, snx_sell_share=0,
            susd_received=0, susd_to_dex=0, susd_sell_share=0,
            usd_received=0, usd_to_dex=0, usd_sell_share=0,
        )

    # Build per-recipient profile from disbursement rows
    profiles: dict[str, dict] = defaultdict(lambda: {
        "snx_received": 0.0, "susd_received": 0.0,
        "earliest_block": None,
        "snx_to_dex": 0.0, "susd_to_dex": 0.0,
    })
    for r in disbursement_rows:
        sym = r.get("tokenSymbol", "?")
        if sym not in DISBURSEMENT_SYMBOLS:
            continue
        if (r.get("from") or "").lower() != council_lc:
            continue
        to = (r.get("to") or "").lower()
        if not to or to in TREASURY_INTERNAL:
            continue
        v = token_value(r)
        if v <= 0:
            continue
        prof = profiles[to]
        if sym == "SNX":
            prof["snx_received"] += v
        elif sym == "sUSD":
            prof["susd_received"] += v
        block = int(r.get("blockNumber", 0))
        if prof["earliest_block"] is None or block < prof["earliest_block"]:
            prof["earliest_block"] = block

    recipients = list(profiles.keys())
    print(f"[nft_queue] {chain:8} scanning {len(recipients)} recipients for DEX outflow…")

    failed = 0
    for eoa in recipients:
        prof = profiles[eoa]
        try:
            user_rows = tokentx(
                chain, eoa,
                startblock=prof["earliest_block"] or 0,
                sort="asc",
            )
        except Exception as exc:
            failed += 1
            # Don't spam — keep individual failures quiet, summarize at end
            continue
        for ur in user_rows:
            if (ur.get("from") or "").lower() != eoa:
                continue  # only outbound from this recipient
            to_addr = (ur.get("to") or "").lower()
            if to_addr not in dex_addrs:
                continue
            sym = ur.get("tokenSymbol", "?")
            if sym not in DISBURSEMENT_SYMBOLS:
                continue
            v = token_value(ur)
            if v <= 0:
                continue
            if sym == "SNX":
                prof["snx_to_dex"] += v
            elif sym == "sUSD":
                prof["susd_to_dex"] += v

    if failed:
        print(f"[nft_queue]   warn: {failed} recipient queries failed (skipped)")

    # Aggregate
    snx_recv = sum(p["snx_received"] for p in profiles.values())
    susd_recv = sum(p["susd_received"] for p in profiles.values())
    snx_dex = sum(p["snx_to_dex"] for p in profiles.values())
    susd_dex = sum(p["susd_to_dex"] for p in profiles.values())

    # USD-denominate using SNX price + sUSD ≈ $1
    usd_recv = snx_recv * snx_price_usd + susd_recv
    usd_dex = snx_dex * snx_price_usd + susd_dex

    snx_share = snx_dex / snx_recv if snx_recv > 0 else 0.0
    susd_share = susd_dex / susd_recv if susd_recv > 0 else 0.0
    usd_share = usd_dex / usd_recv if usd_recv > 0 else 0.0

    print(
        f"[nft_queue]   {chain:8} sell-through: "
        f"SNX {snx_dex:,.0f}/{snx_recv:,.0f} ({snx_share*100:.1f}%) · "
        f"sUSD {susd_dex:,.0f}/{susd_recv:,.0f} ({susd_share*100:.1f}%) · "
        f"USD-weighted {usd_share*100:.1f}%"
    )
    return PostReleaseStats(
        recipients_scanned=len(recipients),
        snx_received=round(snx_recv, 4),
        snx_to_dex=round(snx_dex, 4),
        snx_sell_share=round(snx_share, 4),
        susd_received=round(susd_recv, 4),
        susd_to_dex=round(susd_dex, 4),
        susd_sell_share=round(susd_share, 4),
        usd_received=int(round(usd_recv)),
        usd_to_dex=int(round(usd_dex)),
        usd_sell_share=round(usd_share, 4),
    )


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

    eth_custody = _custody_count("ethereum", RPC_MAINNET)
    op_custody = _custody_count("optimism", RPC_OPTIMISM)

    all_events = eth_events + op_events
    all_events.sort(key=lambda e: e.block_number, reverse=True)
    recent = all_events[:RECENT_EVENTS_LIMIT]

    total_24h = eth_window.nfts_in_24h + op_window.nfts_in_24h
    total_7d = eth_window.nfts_in_7d + op_window.nfts_in_7d
    total_30d = eth_window.nfts_in_30d + op_window.nfts_in_30d

    # Phase 2 valuation: pull 180d disbursements from each chain, fetch SNX price,
    # estimate pending USD value. Degrades gracefully if any of the upstream calls
    # fail (e.g., Etherscan key missing, DefiLlama down) — collector still emits a
    # valid snapshot with zeroed valuation fields.
    eth_disb: dict[str, DisbursementStats] = {}
    op_disb: dict[str, DisbursementStats] = {}
    eth_disb_rows: list[dict] = []
    op_disb_rows: list[dict] = []
    snx_price = 0.0
    try:
        eth_disb, eth_disb_rows = _scan_disbursements("ethereum", RPC_MAINNET)
    except Exception as exc:
        print(f"[nft_queue] WARN Mainnet disbursement scan failed: {exc}")
    try:
        op_disb, op_disb_rows = _scan_disbursements("optimism", RPC_OPTIMISM)
    except Exception as exc:
        print(f"[nft_queue] WARN Optimism disbursement scan failed: {exc}")
    try:
        snx_price = _fetch_snx_price_usd()
        print(f"[nft_queue] SNX price (DefiLlama): ${snx_price:,.4f}")
    except Exception as exc:
        print(f"[nft_queue] WARN SNX price fetch failed: {exc}")

    eth_val = _value_chain(eth_custody, eth_disb, snx_price)
    op_val = _value_chain(op_custody, op_disb, snx_price)

    # Phase 3: per-EOA pairing → processing-lag distribution. Pulls 180d NFT
    # inbounds via Etherscan/Blockscout (faster than RPC at this window) and
    # pairs them chronologically with the disbursement rows already fetched.
    eth_lag = LagStats(sample_n=0, pending_count=0, median_hours=0, p25_hours=0, p75_hours=0)
    op_lag = LagStats(sample_n=0, pending_count=0, median_hours=0, p25_hours=0, p75_hours=0)
    try:
        eth_inb_180 = _scan_inbound_180d("ethereum", RPC_MAINNET)
        eth_lag, _ = _pair_lag("ethereum", eth_inb_180, eth_disb_rows)
    except Exception as exc:
        print(f"[nft_queue] WARN Mainnet lag pairing failed: {exc}")
    try:
        op_inb_180 = _scan_inbound_180d("optimism", RPC_OPTIMISM)
        op_lag, _ = _pair_lag("optimism", op_inb_180, op_disb_rows)
    except Exception as exc:
        print(f"[nft_queue] WARN Optimism lag pairing failed: {exc}")

    combined_lags: list[float] = []
    # Cheap: derive aggregate from the per-chain stats. We don't reconstruct the
    # full distribution — that would need the raw arrays. Instead, surface a
    # weighted-average median with sample sizes so the panel can show "ETH ≈Xh,
    # OP ≈Yh, n=A vs B".
    total_n = eth_lag.sample_n + op_lag.sample_n
    total_pending = eth_lag.pending_count + op_lag.pending_count
    if total_n > 0:
        weighted_median = (
            eth_lag.median_hours * eth_lag.sample_n
            + op_lag.median_hours * op_lag.sample_n
        ) / total_n
    else:
        weighted_median = 0.0

    # Phase 4: post-release behavior. For each disbursement recipient, scan
    # their subsequent token transfers and detect outflows to known DEX
    # addresses. This is a lower bound on actual sell-through (we miss private
    # mempool, contract-wallet routing, and bridges). API budget: ~80
    # recipients × 1 tokentx call ≈ 80 calls per scan.
    eth_post = PostReleaseStats(
        recipients_scanned=0,
        snx_received=0, snx_to_dex=0, snx_sell_share=0,
        susd_received=0, susd_to_dex=0, susd_sell_share=0,
        usd_received=0, usd_to_dex=0, usd_sell_share=0,
    )
    op_post = PostReleaseStats(
        recipients_scanned=0,
        snx_received=0, snx_to_dex=0, snx_sell_share=0,
        susd_received=0, susd_to_dex=0, susd_sell_share=0,
        usd_received=0, usd_to_dex=0, usd_sell_share=0,
    )
    try:
        eth_post = _scan_post_release("ethereum", eth_disb_rows, snx_price)
    except Exception as exc:
        print(f"[nft_queue] WARN Mainnet post-release scan failed: {exc}")
    try:
        op_post = _scan_post_release("optimism", op_disb_rows, snx_price)
    except Exception as exc:
        print(f"[nft_queue] WARN Optimism post-release scan failed: {exc}")

    total_usd_received = eth_post.usd_received + op_post.usd_received
    total_usd_to_dex = eth_post.usd_to_dex + op_post.usd_to_dex
    total_sell_share = (
        total_usd_to_dex / total_usd_received if total_usd_received > 0 else 0.0
    )

    return NftQueueSnapshot(
        as_of=now_iso(),
        council_wallet=COUNCIL_WALLET,
        sacct_address=SACCT_ADDRESS,
        chains={"ethereum": eth_window, "optimism": op_window},
        total_nfts_in_24h=total_24h,
        total_nfts_in_7d=total_7d,
        total_nfts_in_30d=total_30d,
        custody_count={"ethereum": eth_custody, "optimism": op_custody},
        total_custody_count=eth_custody + op_custody,
        disbursements={"ethereum": eth_disb, "optimism": op_disb},
        valuation={"ethereum": eth_val, "optimism": op_val},
        total_estimated_usd=eth_val.estimated_usd + op_val.estimated_usd,
        snx_price_usd=round(snx_price, 4),
        lag={"ethereum": eth_lag, "optimism": op_lag},
        total_lag_sample_n=total_n,
        total_lag_pending_count=total_pending,
        weighted_median_lag_hours=round(weighted_median, 2),
        post_release={"ethereum": eth_post, "optimism": op_post},
        total_usd_received=total_usd_received,
        total_usd_to_dex=total_usd_to_dex,
        total_sell_share=round(total_sell_share, 4),
        recent_inbound=recent,
    )


def main() -> int:
    snapshot = collect()
    path = write_snapshot("nft_queue", snapshot.model_dump(mode="json"))
    print(f"[nft_queue] wrote {path}")
    print(
        f"[nft_queue]   custody: {snapshot.total_custody_count}  ·  "
        f"inflow: 24h={snapshot.total_nfts_in_24h} "
        f"7d={snapshot.total_nfts_in_7d} 30d={snapshot.total_nfts_in_30d}"
    )
    print(
        f"[nft_queue]   est. value: ${snapshot.total_estimated_usd:,}  "
        f"(eth ${snapshot.valuation['ethereum'].estimated_usd:,}  "
        f"op ${snapshot.valuation['optimism'].estimated_usd:,})  "
        f"@ SNX ${snapshot.snx_price_usd:.2f}"
    )
    print(
        f"[nft_queue]   lag (180d): n={snapshot.total_lag_sample_n}  "
        f"pending={snapshot.total_lag_pending_count}  "
        f"weighted-median={snapshot.weighted_median_lag_hours}h"
    )
    print(
        f"[nft_queue]   sell-through (USD-weighted): "
        f"${snapshot.total_usd_to_dex:,} / ${snapshot.total_usd_received:,} = "
        f"{snapshot.total_sell_share*100:.1f}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
