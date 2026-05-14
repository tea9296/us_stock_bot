"""Local smoke test — runs the stock fetcher + formatter without LINE/Notion.

Usage:
    python tests/test_local.py
    python tests/test_local.py SPY NVDA TSM     # override the symbol list

Prints the same message the cron job would push, plus per-symbol timing.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.formatter import format_watchlist  # noqa: E402
from lib.stock import fetch_batch  # noqa: E402

DEFAULT_SYMBOLS = [
    "SPY", "SOXL", "ASTS", "UNH", "MU", "LEU", "CEG",
    "GOOGL", "NBIS", "TSLA", "UNCY", "MSFT", "NE",
]


def main(argv: list[str]) -> int:
    symbols = argv[1:] or DEFAULT_SYMBOLS
    print(f"Fetching {len(symbols)} symbols: {', '.join(symbols)}\n")
    t0 = time.time()
    rows = fetch_batch(symbols)
    elapsed = time.time() - t0
    print(f"--- fetched in {elapsed:.2f}s ---\n")
    print(format_watchlist(rows))
    errs = [r["symbol"] for r in rows if r.get("error")]
    if errs:
        print(f"\nErrors on: {', '.join(errs)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
