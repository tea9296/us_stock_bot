"""Fetch stock prices in parallel from Yahoo Finance's chart endpoint.

Yahoo doesn't just rate-limit by IP — it also fingerprints the TLS handshake
(JA3). Python's stdlib `requests` has a default TLS fingerprint that's
trivially identified as "script, not browser", and gets a much lower quota
even when headers and cookies look legit.

`curl_cffi` solves this by wrapping libcurl with pre-recorded Chrome/Safari
TLS fingerprints — same trick yfinance uses internally. We get the lightweight
direct-HTTP approach without the pandas/numpy bloat of full yfinance.

For 60 symbols at 5 workers with 50–250ms jitter, total wall time ~10–15s.
"""
from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from curl_cffi import requests as cffi_requests

from .config import STOCK_FETCH_WORKERS

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Pin a stable Chrome version's TLS fingerprint so behavior is reproducible.
# Valid impersonate strings: chrome110, chrome120, chrome124, safari17_0, etc.
_IMPERSONATE = "chrome124"

_session_lock = threading.Lock()
_session: Optional[cffi_requests.Session] = None


def _get_session() -> cffi_requests.Session:
    """Lazy singleton — first call sets up cookies via finance.yahoo.com."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = cffi_requests.Session(impersonate=_IMPERSONATE)
                # Pre-warm: visit the main site so Yahoo sets its consent
                # cookies on us. Subsequent chart calls now look like the
                # 2nd page-view from the same browser session.
                try:
                    s.get("https://finance.yahoo.com/", timeout=8)
                except Exception:  # noqa: BLE001 — non-fatal
                    pass
                _session = s
    return _session


def reset_session() -> None:
    """Drop the cached session — useful in tests, or after a long-lived
    cron worker has been alive long enough for cookies to go stale."""
    global _session
    with _session_lock:
        _session = None


def _pct(curr: Optional[float], base: Optional[float]) -> Optional[float]:
    if curr is None or base is None or base == 0:
        return None
    return (curr - base) / base * 100.0


def _fetch_one(symbol: str, timeout: float = 8.0) -> Dict:
    """Fetch one symbol with retries on 429. Always returns a dict, never raises."""
    session = _get_session()
    # range=5d (not 2d): we need 2 daily candles to compute change_pct from
    # yesterday's close. `meta.chartPreviousClose` is the close from BEFORE
    # the chart range starts — with range=2d that's 2 trading days ago,
    # giving wrong percentages. 5d covers normal weeks, holidays, and the
    # occasional missing candle.
    params = {"interval": "1d", "range": "5d", "includePrePost": "true"}
    last_err = "unknown"

    for attempt in range(3):
        # Per-call jitter spreads simultaneous worker requests over a few hundred ms
        time.sleep(random.uniform(0.05, 0.25))
        try:
            r = session.get(
                CHART_URL.format(symbol=symbol),
                params=params,
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001 — curl_cffi has its own exception hierarchy
            last_err = f"net: {str(e)[:60]}"
            time.sleep(0.5 + random.uniform(0, 0.5))
            continue

        if r.status_code == 429:
            last_err = "rate limited (429)"
            time.sleep((attempt + 1) * 2 + random.uniform(0, 0.5))
            continue
        if r.status_code in (401, 403) and attempt == 0:
            # Cookie may have expired — rebuild session and retry once.
            reset_session()
            session = _get_session()
            continue
        if r.status_code != 200:
            return {"symbol": symbol, "error": f"http {r.status_code}"}

        try:
            payload = r.json()
        except ValueError:
            return {"symbol": symbol, "error": "invalid json"}

        chart = payload.get("chart") or {}
        results = chart.get("result")
        if not results:
            err = (chart.get("error") or {}).get("description") or "no data"
            return {"symbol": symbol, "error": err}
        result0 = results[0]
        meta = result0.get("meta") or {}

        last_price = meta.get("regularMarketPrice")

        # Previous close: pull from the daily candle series, not from
        # meta.chartPreviousClose. The latter is the close BEFORE the chart
        # range starts (e.g. range=5d → close from 6+ trading days ago), so
        # using it gives wrong percentages on every day except by coincidence.
        # We want yesterday's close = the candle right before today's.
        indicators = (result0.get("indicators") or {}).get("quote") or [{}]
        closes = indicators[0].get("close") or []
        valid_closes = [c for c in closes if c is not None]

        prev_close: Optional[float] = None
        if len(valid_closes) >= 2:
            # Last entry is today's close (or current intraday if still open);
            # second-to-last is the previous trading day's close.
            prev_close = float(valid_closes[-2])
        else:
            # Single candle (first trading day after a long halt, etc.) —
            # fall back to chartPreviousClose so we still return *something*.
            cpc = meta.get("chartPreviousClose") or meta.get("previousClose")
            if cpc is not None:
                prev_close = float(cpc)

        if last_price is None or prev_close is None:
            return {"symbol": symbol, "error": "missing price fields"}

        return {
            "symbol": symbol,
            "name": meta.get("shortName") or meta.get("longName") or symbol,
            "price": float(last_price),
            "prev_close": float(prev_close),
            "change_pct": _pct(last_price, prev_close),
            "pre_price": float(meta["preMarketPrice"]) if meta.get("preMarketPrice") is not None else None,
            "pre_change_pct": _pct(meta.get("preMarketPrice"), last_price),
            "post_price": float(meta["postMarketPrice"]) if meta.get("postMarketPrice") is not None else None,
            "post_change_pct": _pct(meta.get("postMarketPrice"), last_price),
            "currency": meta.get("currency"),
            "market_state": meta.get("marketState"),
        }

    return {"symbol": symbol, "error": last_err}


def fetch_batch(
    symbols: List[str], max_workers: Optional[int] = None
) -> List[Dict]:
    """Fetch many symbols in parallel. Preserves input order in the result."""
    if not symbols:
        return []
    # Prime the session once before fanning out — avoids every worker racing
    # to do the cookie bootstrap simultaneously.
    _get_session()

    workers = max_workers or STOCK_FETCH_WORKERS
    workers = max(1, min(workers, len(symbols)))

    by_symbol: Dict[str, Dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_one, s): s for s in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                by_symbol[sym] = fut.result()
            except Exception as e:  # noqa: BLE001
                by_symbol[sym] = {"symbol": sym, "error": str(e)[:80]}
    return [by_symbol[s] for s in symbols if s in by_symbol]
