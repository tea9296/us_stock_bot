"""Vercel Cron handler — runs once per day at 22:00 UTC (06:00 Asia/Taipei).

Vercel invokes this as a GET with `Authorization: Bearer ${CRON_SECRET}`.
We fetch the watchlist from Notion, batch-fetch prices from Yahoo, format
the message, and push it to the user via LINE.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from zoneinfo import ZoneInfo

# Vercel runs each file independently; add the project root so `lib.*` resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.config import CRON_SECRET, SKIP_WEEKDAYS_TW  # noqa: E402
from lib.formatter import format_empty, format_watchlist  # noqa: E402
from lib.line_api import push_text  # noqa: E402
from lib.notion_db import get_watchlist  # noqa: E402
from lib.stock import fetch_batch  # noqa: E402


def _run() -> str:
    """Do the actual work. Returns a short status string for the HTTP body."""
    now_tw = datetime.now(ZoneInfo("Asia/Taipei"))
    if now_tw.weekday() in SKIP_WEEKDAYS_TW:
        return f"skipped: {now_tw.strftime('%a')} (weekend/no fresh data)"

    symbols = get_watchlist()
    if not symbols:
        push_text(format_empty())
        return "pushed: empty watchlist message"

    rows = fetch_batch(symbols)
    push_text(format_watchlist(rows))
    return f"pushed: {len(rows)} rows"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — Vercel Python convention
        # Vercel Cron auth: it sends Authorization: Bearer ${CRON_SECRET}.
        # If CRON_SECRET is unset we run wide open (useful for local dev).
        if CRON_SECRET:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {CRON_SECRET}":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"unauthorized")
                return

        try:
            status = _run()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(status.encode("utf-8"))
        except Exception:  # noqa: BLE001
            body = f"error\n\n{traceback.format_exc()}"
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
