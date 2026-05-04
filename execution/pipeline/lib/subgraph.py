"""
TheGraph decentralized network query helper.

Wraps the gateway URL + API-key auth + GraphQL POST. Returns the parsed `data`
field of a successful response, or raises with the GraphQL error context on
failure.

Usage:
    from lib.subgraph import query, UNISWAP_V3_MAINNET

    data = query(UNISWAP_V3_MAINNET, '''
        { _meta { block { number timestamp } } }
    ''')
    print(data["_meta"]["block"]["number"])
"""
from __future__ import annotations

import httpx

from .config import thegraph_api_key
from .http import DEFAULT_TIMEOUT, DEFAULT_HEADERS


# ── known good subgraph IDs (verified 2026-05-03 against the gateway) ────────
# Sushiswap V2 Mainnet has no actively-indexed subgraph on the network — its
# coverage stays on DexScreener via peg.py.
UNISWAP_V3_MAINNET = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
UNISWAP_V3_OPTIMISM = "EgnS9YE1avupkvCNj9fHnJxppfEmNNywYJtghqiu2pd9"
UNISWAP_V2_MAINNET = "EYCKATKGBKLWvSfwvBjzfCBmGwYNdVkduYXVivCsLRFu"
VELODROME_V2_OPTIMISM = "A4Y1A82YhSLTn998BVVELC8eWzhi992k4ZitByvssxqA"


GATEWAY_BASE = "https://gateway.thegraph.com/api"


def query(subgraph_id: str, gql: str, variables: dict | None = None,
          timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> dict:
    """
    POST a GraphQL query to TheGraph gateway. Returns the `data` field on success.
    Raises RuntimeError if the response includes `errors` or no `data`.
    """
    url = f"{GATEWAY_BASE}/{thegraph_api_key()}/subgraphs/id/{subgraph_id}"
    payload: dict = {"query": gql}
    if variables:
        payload["variables"] = variables

    with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        body = r.json()

    if body.get("errors"):
        raise RuntimeError(f"subgraph {subgraph_id[:8]}… returned errors: {body['errors']}")
    data = body.get("data")
    if data is None:
        raise RuntimeError(f"subgraph {subgraph_id[:8]}… returned no data: {body}")
    return data


def latest_block(subgraph_id: str) -> tuple[int, int]:
    """
    Convenience health-check: returns (block_number, block_timestamp) for a subgraph.
    Useful for verifying a subgraph is responsive and not lagging.
    """
    data = query(subgraph_id, "{ _meta { block { number timestamp } } }")
    block = data["_meta"]["block"]
    return int(block["number"]), int(block["timestamp"])
