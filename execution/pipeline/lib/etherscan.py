"""
Token-transfer history helpers, dispatching per chain to whichever free
explorer API actually serves it:

  - Mainnet  → Etherscan V2 (api.etherscan.io/v2/api, chainid=1, requires key)
  - Optimism → OP's official Blockscout-based explorer at explorer.optimism.io
               (free, no key, Etherscan-V1-compatible JSON shape)

Why two paths: Etherscan's V2 free tier covers Ethereum mainnet only.
Optimism on V2 requires a paid plan ("Free API access is not supported for
this chain"). The legacy V1 OP endpoint at api-optimistic.etherscan.io has
been retired. The OP Foundation's explorer is Blockscout-based and exposes
an Etherscan-shaped `/api?module=account&action=tokentx` endpoint that's
free, public, and returns the same field names — so we use that for OP.

Why not web3.py: we stay with httpx + raw HTTP calls to keep deps minimal.
These token-transfer endpoints expose Etherscan/Blockscout's internal
indexer, which handles Synthetix's non-standard Proxyable event-emission
pattern correctly (unlike eth_getLogs against the SNX proxy address, which
returns nothing). That's the key reason this module exists at all.

Free-tier limits:
  - Etherscan V2: 5 calls/sec, 100k/day (Mainnet only on free)
  - explorer.optimism.io: published rate limits, generous in practice

We throttle conservatively and the cron cadence keeps usage well under both.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from .config import etherscan_api_key
from .http import DEFAULT_HEADERS, DEFAULT_TIMEOUT


# Per-chain endpoint config
ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"
OP_EXPLORER_URL = "https://explorer.optimism.io/api"

# Etherscan chainid param values (V2 multichain — Mainnet only on free)
ETHERSCAN_V2_CHAINS = {"ethereum": 1, "mainnet": 1}

# Chains served via Blockscout-shaped public APIs (no key, redirected from
# the older optimism.blockscout.com host).
BLOCKSCOUT_CHAINS = {"optimism": OP_EXPLORER_URL, "op": OP_EXPLORER_URL}

# tokentx returns up to this many records per page
PAGE_SIZE = 10_000

# Min seconds between calls to stay under any of the providers' free limits
_MIN_CALL_INTERVAL = 0.21
_last_call_ts: float = 0.0


def _throttle() -> None:
    global _last_call_ts
    now = time.monotonic()
    delta = now - _last_call_ts
    if delta < _MIN_CALL_INTERVAL:
        time.sleep(_MIN_CALL_INTERVAL - delta)
    _last_call_ts = time.monotonic()


def _parse_envelope(body: dict, *, provider: str) -> Any:
    """
    Both Etherscan and Blockscout return `{status, message, result}`. status="1"
    is success. status="0" with an empty-result list is a valid empty response —
    Etherscan and Blockscout each phrase this differently ("No transactions found"
    vs "No token transfers found"), so we treat any status="0" with `result == []`
    as success-empty. Anything else is an error.
    """
    status = body.get("status")
    if status == "1":
        return body.get("result")
    if status == "0" and body.get("result") == []:
        return []
    raise RuntimeError(
        f"{provider} error: status={status!r} message={body.get('message')!r} "
        f"result={body.get('result')!r}"
    )


def _etherscan_v2_request(chain: str, params: dict[str, Any]) -> Any:
    chainid = ETHERSCAN_V2_CHAINS[chain.lower()]
    full = {"chainid": chainid, "apikey": etherscan_api_key(), **params}
    _throttle()
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        r = client.get(ETHERSCAN_V2_URL, params=full)
        r.raise_for_status()
        body = r.json()
    return _parse_envelope(body, provider="Etherscan V2")


def _blockscout_request(chain: str, params: dict[str, Any]) -> Any:
    url = BLOCKSCOUT_CHAINS[chain.lower()]
    _throttle()
    # Blockscout's `optimism.blockscout.com` redirects to explorer.optimism.io;
    # we hit the canonical host directly to skip the 301.
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS) as client:
        r = client.get(url, params=params, follow_redirects=True)
        r.raise_for_status()
        body = r.json()
    return _parse_envelope(body, provider=f"Blockscout({chain})")


def _select_request(chain: str):
    chain_lc = chain.lower()
    if chain_lc in ETHERSCAN_V2_CHAINS:
        return lambda p: _etherscan_v2_request(chain_lc, p)
    if chain_lc in BLOCKSCOUT_CHAINS:
        return lambda p: _blockscout_request(chain_lc, p)
    raise ValueError(f"unsupported chain: {chain!r}")


def _paginated(
    request,
    chain: str,
    action: str,
    address: str,
    *,
    contractaddress: str | None,
    startblock: int,
    endblock: int,
    sort: str,
) -> list[dict]:
    """Walk paginated `account/<action>` calls until exhausted or limit reached."""
    out: list[dict] = []
    page = 1
    while True:
        params: dict[str, Any] = {
            "module": "account",
            "action": action,
            "address": address,
            "page": page,
            "offset": PAGE_SIZE,
            "startblock": startblock,
            "endblock": endblock,
            "sort": sort,
        }
        if contractaddress:
            params["contractaddress"] = contractaddress
        batch = request(params)
        if not isinstance(batch, list):
            raise RuntimeError(f"{action} returned non-list on {chain}: {batch!r}")
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        if page > 10:
            raise RuntimeError(
                f"{action} exceeded 100k records for {address} on {chain} "
                f"in window [{startblock}, {endblock}] — narrow the window."
            )
    return out


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
    `contractaddress`. Paginated transparently — returns a flat list of all
    matching transfers.

    Returned rows expose Etherscan/Blockscout's union of fields. Selected:
        blockNumber, timeStamp (unix), hash, from, to, value (raw), tokenSymbol,
        tokenDecimal, contractAddress.
    """
    request = _select_request(chain)
    return _paginated(
        request, chain, "tokentx", address,
        contractaddress=contractaddress, startblock=startblock, endblock=endblock, sort=sort,
    )


def tokennfttx(
    chain: str,
    address: str,
    *,
    contractaddress: str | None = None,
    startblock: int = 0,
    endblock: int = 99_999_999,
    sort: str = "asc",
) -> list[dict]:
    """
    ERC-721 token transfers involving `address`. Same shape as tokentx but for
    NFT contracts. Returned rows include `tokenID` (sic — capital ID) instead
    of the ERC-20 `value` field.
    """
    request = _select_request(chain)
    return _paginated(
        request, chain, "tokennfttx", address,
        contractaddress=contractaddress, startblock=startblock, endblock=endblock, sort=sort,
    )


def token_decimal(row: dict) -> int:
    """Parse `tokenDecimal` from a tokentx row (returned as a string)."""
    return int(row.get("tokenDecimal", "18") or 18)


def token_value(row: dict) -> float:
    """Convert a tokentx row's raw `value` to a decimal float."""
    raw = int(row.get("value", "0"))
    return raw / (10 ** token_decimal(row))
