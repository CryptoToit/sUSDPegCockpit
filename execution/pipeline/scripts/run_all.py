"""
Run every implemented collector in sequence.

Each collector is independent — failure of one doesn't block the others.
Exit code is the count of failed collectors (0 = all green).

Run:
  python -m scripts.run_all
"""
from __future__ import annotations

import sys
import traceback
from typing import Callable

from collectors import flow, peg, pool_420, radar, recovery_score, scorecard, supply, trade_flow, yield_compare


# Order matters:
#   - radar reads pool_420 (current locked total) + does live RPC for Treasury outflows
#   - flow reads peg + supply + scorecard + pool_420
#   - trade_flow reads peg
#   - recovery_score reads peg + scorecard + radar + trade_flow
# So peg → supply → scorecard → pool_420 → radar → flow → trade_flow → yield → recovery_score.
COLLECTORS: list[tuple[str, Callable[[], int]]] = [
    ("peg", peg.main),
    ("supply", supply.main),
    ("scorecard", scorecard.main),
    ("pool_420", pool_420.main),
    ("radar", radar.main),
    ("flow", flow.main),
    ("trade_flow", trade_flow.main),
    ("yield", yield_compare.main),
    ("recovery_score", recovery_score.main),
]


def main() -> int:
    failures = 0
    for name, fn in COLLECTORS:
        print(f"\n=== {name} ===")
        try:
            rc = fn()
            if rc != 0:
                print(f"[run_all] {name} returned non-zero ({rc})", file=sys.stderr)
                failures += 1
        except Exception:
            print(f"[run_all] {name} raised an exception:", file=sys.stderr)
            traceback.print_exc()
            failures += 1

    print(f"\n=== run_all summary ===")
    print(f"  collectors run: {len(COLLECTORS)}")
    print(f"  failures:       {failures}")
    return failures


if __name__ == "__main__":
    sys.exit(main())
