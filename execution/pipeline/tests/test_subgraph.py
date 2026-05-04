"""
Online tests for the subgraph helper.

Skipped automatically if THEGRAPH_API_KEY isn't configured (so this doesn't
fail in environments that haven't set up TheGraph access yet).
"""
import os
import pytest

from lib import config


def _has_key() -> bool:
    try:
        return bool(config.thegraph_api_key())
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(
    not _has_key(),
    reason="THEGRAPH_API_KEY not set — skipping online subgraph tests",
)


def test_uniswap_v3_mainnet_is_live():
    from lib.subgraph import UNISWAP_V3_MAINNET, latest_block
    block, ts = latest_block(UNISWAP_V3_MAINNET)
    assert block > 25_000_000, f"Uniswap V3 Mainnet block too low: {block}"


def test_uniswap_v3_optimism_is_live():
    from lib.subgraph import UNISWAP_V3_OPTIMISM, latest_block
    block, ts = latest_block(UNISWAP_V3_OPTIMISM)
    assert block > 150_000_000, f"Uniswap V3 Optimism block too low: {block}"


def test_uniswap_v2_mainnet_is_live():
    from lib.subgraph import UNISWAP_V2_MAINNET, latest_block
    block, ts = latest_block(UNISWAP_V2_MAINNET)
    assert block > 25_000_000, f"Uniswap V2 Mainnet block too low: {block}"


def test_velodrome_v2_optimism_is_live():
    from lib.subgraph import VELODROME_V2_OPTIMISM, latest_block
    block, ts = latest_block(VELODROME_V2_OPTIMISM)
    assert block > 150_000_000, f"Velodrome V2 Optimism block too low: {block}"
