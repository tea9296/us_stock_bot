"""One-shot script: populate the Notion watchlist with an initial set of symbols.

Run once after creating the Notion database. Idempotent — if a symbol is
already present, it just makes sure Active=True.

Usage:
    # Reads NOTION_API_KEY / NOTION_DATABASE_ID from .env or shell env
    python scripts/seed_watchlist.py

    # Pass a custom list:
    python scripts/seed_watchlist.py AAPL MSFT GOOG
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Lazy-load .env if python-dotenv is installed; otherwise read shell env only.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

from lib.notion_db import add_symbol  # noqa: E402

DEFAULT_SEED = [
    "SPY", "SOXL", "ASTS", "UNH", "MU", "LEU", "CEG",
    "GOOGL", "NBIS", "TSLA", "UNCY", "MSFT", "NE",
]


def main(argv: list[str]) -> int:
    symbols = argv[1:] or DEFAULT_SEED
    if not os.environ.get("NOTION_API_KEY") or not os.environ.get("NOTION_DATABASE_ID"):
        print("⚠️  Set NOTION_API_KEY and NOTION_DATABASE_ID first (env or .env file).",
              file=sys.stderr)
        return 2

    print(f"Seeding {len(symbols)} symbols: {', '.join(symbols)}\n")
    for sym in symbols:
        try:
            status = add_symbol(sym)
            print(f"  {sym:<8}  {status}")
        except Exception as e:  # noqa: BLE001
            print(f"  {sym:<8}  ERROR: {e}")
    print("\ndone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
