"""Vercel webhook handler — LINE pushes message events here.

We verify the HMAC signature, parse the text, dispatch to Notion +
stock-fetcher, and reply via LINE within the 30-second reply-token window.

Per Vercel Hobby cap this function is limited to 10s, which is plenty for
add/remove (one Notion call) but tight for `list` against a 60-stock
watchlist that's never been cached. If `list` ever times out, bump
maxDuration in vercel.json (Hobby allows up to 60s).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.config import LINE_USER_ID  # noqa: E402
from lib.formatter import HELP_TEXT, format_empty, format_watchlist  # noqa: E402
from lib.line_api import reply_text, verify_signature  # noqa: E402
from lib.notion_db import add_symbol, get_watchlist, remove_symbol  # noqa: E402
from lib.parser import parse  # noqa: E402
from lib.stock import fetch_batch  # noqa: E402


def _handle_add(args: List[str]) -> str:
    if not args:
        return "⚠️ 請給股票代號，例如：加 NVDA"
    added: List[str] = []
    reactivated: List[str] = []
    already: List[str] = []
    failed: List[str] = []
    for sym in args:
        try:
            r = add_symbol(sym)
            if r == "added":
                added.append(sym)
            elif r == "reactivated":
                reactivated.append(sym)
            elif r == "already_active":
                already.append(sym)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{sym}({e})")
    msg = []
    if added:
        msg.append(f"✅ 已加入：{', '.join(added)}")
    if reactivated:
        msg.append(f"♻️ 重新啟用：{', '.join(reactivated)}")
    if already:
        msg.append(f"☑️ 已存在：{', '.join(already)}")
    if failed:
        msg.append(f"⚠️ 失敗：{', '.join(failed)}")
    return "\n".join(msg) if msg else "🤔 沒有可加入的代號"


def _handle_remove(args: List[str]) -> str:
    if not args:
        return "⚠️ 請給股票代號，例如：刪 NVDA"
    removed: List[str] = []
    not_found: List[str] = []
    already: List[str] = []
    failed: List[str] = []
    for sym in args:
        try:
            r = remove_symbol(sym)
            if r == "removed":
                removed.append(sym)
            elif r == "not_found":
                not_found.append(sym)
            elif r == "already_inactive":
                already.append(sym)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{sym}({e})")
    msg = []
    if removed:
        msg.append(f"🗑 已移除：{', '.join(removed)}")
    if already:
        msg.append(f"☑️ 本來就不在清單：{', '.join(already)}")
    if not_found:
        msg.append(f"❓ 找不到：{', '.join(not_found)}")
    if failed:
        msg.append(f"⚠️ 失敗：{', '.join(failed)}")
    return "\n".join(msg) if msg else "🤔 沒有可移除的代號"


def _handle_list() -> str:
    symbols = get_watchlist()
    if not symbols:
        return format_empty()
    rows = fetch_batch(symbols)
    return format_watchlist(rows)


def _dispatch(text: str) -> str:
    cmd, args = parse(text)
    if cmd == "help":
        return HELP_TEXT
    if cmd == "list":
        return _handle_list()
    if cmd == "add":
        return _handle_add(args)
    if cmd == "remove":
        return _handle_remove(args)
    return "🤔 不懂這個指令，輸入 help 看用法"


def _process_events(events: list) -> None:
    """Reply to every text-message event from the authorized user."""
    for ev in events:
        if ev.get("type") != "message":
            continue
        msg = ev.get("message") or {}
        if msg.get("type") != "text":
            continue
        reply_token = ev.get("replyToken")
        text = msg.get("text", "")
        user_id = (ev.get("source") or {}).get("userId")

        # Allowlist: if LINE_USER_ID is configured, only that user can issue
        # commands. Other users get a polite refusal — we still reply so they
        # don't think the bot is broken.
        if LINE_USER_ID and user_id != LINE_USER_ID:
            if reply_token:
                try:
                    reply_text(reply_token, "🚫 這個機器人只回應它的擁有者。")
                except Exception:  # noqa: BLE001 — swallow, we'll log via 500
                    traceback.print_exc()
            continue

        try:
            response = _dispatch(text)
        except Exception as e:  # noqa: BLE001
            response = f"⚠️ 內部錯誤：{e}"
            traceback.print_exc()

        if reply_token:
            try:
                reply_text(reply_token, response)
            except Exception:  # noqa: BLE001
                traceback.print_exc()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        signature = self.headers.get("X-Line-Signature", "")

        if not verify_signature(body, signature):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"invalid signature")
            return

        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"bad json")
            return

        try:
            _process_events(data.get("events", []))
        except Exception:  # noqa: BLE001
            traceback.print_exc()

        # LINE expects a 200 quickly. We always return ok if signature passed.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):  # noqa: N802 — handy for "is the function alive?" pings
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")
