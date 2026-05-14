"""Plain-Python (no pytest) sanity check for the parser."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.parser import parse  # noqa: E402

CASES = [
    ("加 NVDA", "add", ["NVDA"]),
    ("加 NVDA TSM AAPL", "add", ["NVDA", "TSM", "AAPL"]),
    ("加nvda", "add", ["NVDA"]),
    ("add NVDA, TSM", "add", ["NVDA", "TSM"]),
    ("+NVDA", "add", ["NVDA"]),
    ("刪 TSLA", "remove", ["TSLA"]),
    ("del TSLA NVDA", "remove", ["TSLA", "NVDA"]),
    ("-tsla", "remove", ["TSLA"]),
    ("list", "list", []),
    ("清單", "list", []),
    ("help", "help", []),
    ("？", "help", []),
    ("random text", "unknown", []),
]


def main() -> int:
    failures = 0
    for text, want_cmd, want_args in CASES:
        cmd, args = parse(text)
        ok = cmd == want_cmd and args == want_args
        status = "ok" if ok else "FAIL"
        print(f"[{status}] parse({text!r}) → ({cmd!r}, {args!r})")
        if not ok:
            print(f"        expected     ({want_cmd!r}, {want_args!r})")
            failures += 1
    print()
    print(f"{len(CASES) - failures}/{len(CASES)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
