"""
Etherscan V2 multichain API helpers.

Used by:
  - nft_queue collector (Phase 2 valuation, Phase 3 lag): tokentx for the council wallet
  - Future Phase 4 DEX attribution: tokentx for individual EOAs

Why V2: Etherscan's V1 endpoints were deprecated mid-2025; V2 uses a single
host (`api.etherscan.io/v2/api`) with a `chainid` query param. One key works
across Mainnet (chainid=1) and Optimism (chainid=10).

Why not web3.py: we stay with httpx + raw HTTP calls to keep deps minimal.
The token-transfer endpoint exposes Etherscan's internal indexer, which
handles Synthetix's non-standard Proxyable event-emission pattern correctly
(unlike eth_getLogs against the SNX proxy address, which returns nothing).
That's the key reason this module exists at all.

Free tier: 5 calls/sec, 100k/day. We don't need throttling for the cron
cadence — full sweep is ~5–10 calls per tick.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from .config import etherscan_api_key
from .http import DEFAULT_HEADERS, DEFAULT_TIMEOUT


API_BASE = "https://api.etherscan.io/v2/api"

# Etherscan chainid param values (subset — extend as needed)
CHAIN_ID = {"ethereum": 1, "mainnet": 1, "optimism": 10, "op": 10}

# tokentx returns up to this many records per page
PAGE_SIZE = 10_000

# Min seconds between calls to stay under the free-tier 5/sec limit
_MIN_CALL_INTERVAL = 0.21
_last_call_ts: float = 0.0


def _throttle() -> None:
    """Enforce a minimum gap between consecutive Etherscan calls."""
    global _last_call_ts
    now = time.monotonic()
    delta = now - _last_call_ts
    if delta < _MIN_CALL_INTERVAL:
        time.sleep(_MIN_CALL_INTERVAL - delta)
    _last_call_ts = time.monotonic()


def _request(params: dict[str, Any]) -> Any:
    """
    Single Etherscan V2 call. Adds chainid + apikey, parses the standard
    `{status, message, result}` envelope, and raises on error responses.
    Returns the `result` field on success.
    """
    full = {"apikey": etherscan_api_key(), **params}
    _throttle()
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        r = client.get(API_BASE, params=full)
        r.raise_for_status()
        body = r.json()
    status = body.get("status")
    if status == "1":
        return body.get("result")
    # Etherscan returns status "0" with `message: "No transactions found"` and an empty
    # result list — that's a valid empty response, not an error.
    if status == "0" and body.get("message") == "No transactions found":
        return []
    # Real error: NOTOK / rate-limited / bad key etc.
    raise RuntimeError(
        f"Etherscan V2 error: status={status!r} message={body.get('message')!r} "
        f"result={body.get('result')!r}"
    )


def tokentx(
    chain: str,
    address: str,
    *,
    contractaddress: str | None = None,
    startblock: int = 0,
    endblock: int = 99_999_999,
    sort: str = "asc",
) -> list[dict]:
    """
    ERC-20 token transfers involving `address`. Optionally filter to a single
    `contractaddress` (e.g., SNX or sUSD). Paginated transparently — returns
    a flat list of all matching transfers.

    Each result row includes (selected fields):
        blockNumber, timeStamp (unix), hash, from, to, value (raw), tokenSymbol,
        tokenDecimal, contractAddress.
    """
    chainid = CHAIN_ID[chain.lower()]
    out: list[dict] = []
    page = 1
    while True:
        params: dict[str, Any] = {
            "chainid": chainid,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": page,
            "offset": PAGE_SIZE,
            "startblock": startblock,
            "endblock": endblock,
            "sort": sort,
        }
        if contractaddress:
            params["contractaddress"] = contractaddress
        batch = _request(params)
        if not isinstance(batch, list):
            raise RuntimeError(f"Etherscan tokentx returned non-list: {batch!r}")
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        # Safety stop: 10 pages × 10k = 100k records would exceed any sane window
        if page > 10:
            raise RuntimeError(
                f"Etherscan tokentx exceeded 100k records for {address} on {chain} "
                f"in window [{startblock}, {endblock}] — narrow the window."
            )
    return out


def token_decimal(row: dict) -> int:
    """Parse `tokenDecimal` from a tokentx row (returned as a string)."""
    return int(row.get("tokenDecimal", "18") or 18)


def token_value(row: dict) -> float:
    """Convert a tokentx row's raw `value` to a decimal float."""
    raw = int(row.get("value", "0"))
    return raw / (10 ** token_decimal(row))
