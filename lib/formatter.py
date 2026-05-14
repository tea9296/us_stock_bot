"""Render watchlist rows into the LINE-friendly text we send to the user."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Taipei")


def _emoji(change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "⚪"
    if change_pct >= 0.05:
        return "🟢"
    if change_pct <= -0.05:
        return "🔴"
    return "⚪"


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "N/A"
    if p >= 1000:
        return f"${p:,.2f}"
    return f"${p:.2f}"


def _fmt_pct(p: Optional[float]) -> str:
    if p is None:
        return "n/a"
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.2f}%"


def format_watchlist(rows: List[Dict]) -> str:
    today = datetime.now(_TZ).strftime("%Y/%m/%d %a")
    lines = [f"📊 {today} 美股清單", ""]

    for row in rows:
        sym = row.get("symbol", "?")
        if row.get("error"):
            lines.append(f"{sym}  ⚠️ {row['error']}")
            continue

        emoji = _emoji(row.get("change_pct"))
        lines.append(
            f"{sym}  {_fmt_price(row.get('price'))}  "
            f"{_fmt_pct(row.get('change_pct'))} {emoji}"
        )

        # Post-market first (more recent than regular close).
        if row.get("post_price") is not None:
            lines.append(
                f"  盤後 {_fmt_price(row['post_price'])} "
                f"({_fmt_pct(row.get('post_change_pct'))})"
            )
        if row.get("pre_price") is not None:
            lines.append(
                f"  盤前 {_fmt_price(row['pre_price'])} "
                f"({_fmt_pct(row.get('pre_change_pct'))})"
            )

    lines.append("")
    lines.append("─────────────")
    lines.append("加 SYMBOL  /  刪 SYMBOL  /  list  /  help")
    return "\n".join(lines)


def format_empty() -> str:
    return (
        "📋 watchlist 目前是空的。\n\n"
        "用「加 NVDA」加入股票，或一次加多檔：「加 NVDA TSM AAPL」"
    )


HELP_TEXT = (
    "📖 使用說明\n\n"
    "加 NVDA              加入一檔\n"
    "加 NVDA TSM AAPL     一次加多檔\n"
    "刪 NVDA              移除\n"
    "list / 清單          看目前清單 + 現價\n"
    "help                 這個說明\n\n"
    "每天台灣時間 6:00 會自動推當天清單。"
)
