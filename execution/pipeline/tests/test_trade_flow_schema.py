"""Schema-conformance + invariant tests for the trade_flow snapshot."""
import json

from schemas.trade_flow import TradeFlowSnapshot
from lib.snapshot import CLIENT_DATA_DIR


def test_trade_flow_snapshot_validates():
    path = CLIENT_DATA_DIR / "trade_flow" / "latest.json"
    assert path.exists(), f"missing snapshot: {path}"
    raw = json.loads(path.read_text())
    TradeFlowSnapshot.model_validate(raw)


def test_trade_flow_per_venue_sums_match_totals():
    """For each window, sum of per-venue sell/buy must equal `total.sell_susd`/`total.buy_susd`."""
    path = CLIENT_DATA_DIR / "trade_flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = TradeFlowSnapshot.model_validate(raw)
    for window_name, w in snap.windows.items():
        venue_sell = sum(v.sell_susd for v in w.venues)
        venue_buy = sum(v.buy_susd for v in w.venues)
        assert venue_sell == w.total.sell_susd, (
            f"{window_name}: venue sell sum ${venue_sell:,} != total.sell_susd ${w.total.sell_susd:,}"
        )
        assert venue_buy == w.total.buy_susd, (
            f"{window_name}: venue buy sum ${venue_buy:,} != total.buy_susd ${w.total.buy_susd:,}"
        )
        assert w.total.net_susd == w.total.buy_susd - w.total.sell_susd, (
            f"{window_name}: net != buy - sell"
        )


def test_trade_flow_buy_split_sums_to_total_buy():
    """programmatic + organic must equal total buy."""
    path = CLIENT_DATA_DIR / "trade_flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = TradeFlowSnapshot.model_validate(raw)
    for window_name, w in snap.windows.items():
        bs = w.buy_split
        assert bs.programmatic_susd + bs.organic_susd == w.total.buy_susd, (
            f"{window_name}: programmatic + organic != total buy"
        )


def test_trade_flow_counter_asset_shares_sum_to_one():
    """Counter-asset shares within each side should sum to ~1.0."""
    path = CLIENT_DATA_DIR / "trade_flow" / "latest.json"
    raw = json.loads(path.read_text())
    snap = TradeFlowSnapshot.model_validate(raw)
    for window_name, w in snap.windows.items():
        sell_sum = sum(w.sell_counter_assets.values())
        buy_sum = sum(w.buy_counter_assets.values())
        assert abs(sell_sum - 1.0) < 0.01, f"{window_name}: sell counter-assets sum {sell_sum} != 1.0"
        assert abs(buy_sum - 1.0) < 0.01, f"{window_name}: buy counter-assets sum {buy_sum} != 1.0"
