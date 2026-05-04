"""
Minimal JSON-RPC helpers for on-chain reads.

Avoids pulling in `web3.py` (heavy) for the simple `balanceOf` reads we need.
If/when we need contract events, decoding, or batched multicall, we'll graduate
to web3.py.
"""
from __future__ import annotations

import httpx
from .http import DEFAULT_TIMEOUT, DEFAULT_HEADERS


# Default public RPCs — no auth, generous rate limits, used in earlier sessions.
RPC_MAINNET = "https://ethereum-rpc.publicnode.com"
RPC_OPTIMISM = "https://mainnet.optimism.io"


def eth_call(rpc_url: str, to: str, data: str) -> str:
    """Run an `eth_call` against `to` with calldata `data`. Returns raw hex result."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        r = client.post(rpc_url, json=payload)
        r.raise_for_status()
        body = r.json()
    if "error" in body:
        raise RuntimeError(f"RPC error from {rpc_url}: {body['error']}")
    result = body.get("result")
    if not result:
        raise RuntimeError(f"RPC returned no result: {body}")
    return result


def erc20_balance_of(rpc_url: str, token: str, holder: str, *, decimals: int = 18) -> float:
    """ERC-20 `balanceOf(holder)` returning a USD-like value scaled by 10**decimals."""
    addr_clean = holder.lower().replace("0x", "").rjust(64, "0")
    data = "0x70a08231" + addr_clean
    raw_hex = eth_call(rpc_url, token, data)
    raw = int(raw_hex, 16)
    return raw / (10 ** decimals)


def eth_block_number(rpc_url: str) -> int:
    """Current head block number on the chain."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        r = client.post(rpc_url, json=payload)
        r.raise_for_status()
        body = r.json()
    if "error" in body:
        raise RuntimeError(f"RPC error from {rpc_url}: {body['error']}")
    return int(body["result"], 16)


def eth_get_logs(
    rpc_url: str,
    address: str,
    topics: list,
    from_block: int,
    to_block: int,
    *,
    window_size: int = 10_000,
) -> list[dict]:
    """
    Paginated `eth_getLogs` across [from_block, to_block], windowed at most `window_size`
    blocks per request to stay within public RPC limits (publicnode caps at 10k for
    Mainnet and OP). Returns a flat list of log objects.
    """
    all_logs: list[dict] = []
    cursor = from_block
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        while cursor <= to_block:
            end = min(cursor + window_size - 1, to_block)
            params = [{
                "address": address,
                "topics": topics,
                "fromBlock": hex(cursor),
                "toBlock": hex(end),
            }]
            payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": params}
            r = client.post(rpc_url, json=payload)
            r.raise_for_status()
            body = r.json()
            if "error" in body:
                raise RuntimeError(f"eth_getLogs error from {rpc_url}: {body['error']}")
            logs = body.get("result") or []
            all_logs.extend(logs)
            cursor = end + 1
    return all_logs
