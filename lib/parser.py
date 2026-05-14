"""Parse incoming LINE text messages into commands.

Supported syntax (case-insensitive, Chinese or English):
  加 NVDA              -> ("add", ["NVDA"])
  add NVDA TSM AAPL    -> ("add", ["NVDA", "TSM", "AAPL"])
  +NVDA                -> ("add", ["NVDA"])
  刪 NVDA              -> ("remove", ["NVDA"])
  del NVDA             -> ("remove", ["NVDA"])
  remove NVDA          -> ("remove", ["NVDA"])
  -NVDA                -> ("remove", ["NVDA"])
  查 NVDA              -> ("query", ["NVDA"])
  查 NVDA TSM          -> ("query", ["NVDA", "TSM"])
  q NVDA / query NVDA  -> ("query", ["NVDA"])
  ?NVDA                -> ("query", ["NVDA"])
  list / 清單 / ls     -> ("list", [])
  help / 說明 / ?      -> ("help", [])
  anything else        -> ("unknown", [])
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Order matters: longer / more specific keywords first.
# `query` must come before `q` in length matching; we sort longest-first below.
_ADD_PREFIXES = ("加", "add", "+")
_REMOVE_PREFIXES = ("刪", "删", "delete", "del", "remove", "rm", "-")
_QUERY_PREFIXES = ("查", "query", "q", "?", "？")
_LIST_WORDS = {"list", "ls", "清單", "清单"}
_HELP_WORDS = {"help", "說明", "说明", "?", "？"}

# A stock symbol: 1–6 letters, optionally with a dot/dash and extra letters
# (e.g. BRK.B, RDS-A). Not all real symbols match this perfectly but it
# covers virtually all US tickers we'd realistically watch.
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")


def _split_tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[\s,，、]+", text.strip()) if t]


def _extract_symbols(rest: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for tok in _split_tokens(rest):
        if _SYMBOL_RE.match(tok):
            s = tok.upper()
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def parse(text: str) -> Tuple[str, List[str]]:
    if not text:
        return ("unknown", [])
    raw = text.strip()
    low = raw.lower()

    # Whole-word commands first.
    if low in _HELP_WORDS or raw in _HELP_WORDS:
        return ("help", [])
    if low in _LIST_WORDS or raw in _LIST_WORDS:
        return ("list", [])

    # Prefix-style commands. Order: add/remove first (most common), then query.
    # `?` is also a help word, but only if it's the *entire* message (handled
    # above); a `?NVDA` should fall through to query.
    for p in _ADD_PREFIXES:
        if low.startswith(p):
            rest = raw[len(p):]
            return ("add", _extract_symbols(rest))
    for p in _REMOVE_PREFIXES:
        if low.startswith(p):
            rest = raw[len(p):]
            return ("remove", _extract_symbols(rest))
    for p in _QUERY_PREFIXES:
        if low.startswith(p):
            rest = raw[len(p):]
            syms = _extract_symbols(rest)
            if syms:
                return ("query", syms)

    return ("unknown", [])
