"""Thin Notion API wrapper for the watchlist database.

Uses the modern data_sources API (Notion-Version 2025-09-03), which is what
new databases require. If the user only configures NOTION_DATABASE_ID we
resolve the data_source_id ourselves on first call.

Database schema:
  - Symbol  (title)         e.g. "NVDA"
  - Active  (checkbox)      soft-delete flag; default True
  - Added   (created_time)  read-only, set automatically by Notion
  - Notes   (rich_text)     optional user notes

Soft delete (set Active=False) lets the user "remove" a stock from the daily
push while keeping the history — re-adding the same symbol flips Active back
on instead of creating duplicates.
"""
from __future__ import annotations

import threading
from typing import List, Optional

import requests

from .config import (
    NOTION_API_KEY,
    NOTION_DATABASE_ID,
    NOTION_DATA_SOURCE_ID,
    NOTION_VERSION,
)

_BASE = "https://api.notion.com/v1"

_ds_lock = threading.Lock()
_cached_ds_id: Optional[str] = None


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _resolve_data_source_id() -> str:
    """Get the data_source_id, either from env or by asking Notion."""
    global _cached_ds_id
    if NOTION_DATA_SOURCE_ID:
        return NOTION_DATA_SOURCE_ID
    if _cached_ds_id:
        return _cached_ds_id
    if not NOTION_DATABASE_ID:
        raise RuntimeError(
            "Set either NOTION_DATA_SOURCE_ID or NOTION_DATABASE_ID in env."
        )
    with _ds_lock:
        if _cached_ds_id:
            return _cached_ds_id
        r = requests.get(
            f"{_BASE}/databases/{NOTION_DATABASE_ID}",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        sources = r.json().get("data_sources", [])
        if not sources:
            raise RuntimeError(
                f"Database {NOTION_DATABASE_ID} has no data sources. "
                "Make sure the Integration is added to the database's Connections."
            )
        _cached_ds_id = sources[0]["id"]
        return _cached_ds_id


def _norm(symbol: str) -> str:
    return symbol.strip().upper()


def get_watchlist() -> List[str]:
    """Return all active symbols, ordered by Added asc."""
    ds_id = _resolve_data_source_id()
    url = f"{_BASE}/data_sources/{ds_id}/query"
    payload = {
        "filter": {"property": "Active", "checkbox": {"equals": True}},
        "sorts": [{"property": "Added", "direction": "ascending"}],
        "page_size": 100,
    }
    symbols: List[str] = []
    cursor: Optional[str] = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(url, headers=_headers(), json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        for page in data.get("results", []):
            title_prop = page.get("properties", {}).get("Symbol", {}).get("title", [])
            if title_prop:
                sym = title_prop[0].get("plain_text", "").strip().upper()
                if sym:
                    symbols.append(sym)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return symbols


def _find_page_id(symbol: str) -> Optional[str]:
    """Look up a Notion page by symbol regardless of Active state."""
    ds_id = _resolve_data_source_id()
    url = f"{_BASE}/data_sources/{ds_id}/query"
    payload = {
        "filter": {"property": "Symbol", "title": {"equals": _norm(symbol)}},
        "page_size": 1,
    }
    r = requests.post(url, headers=_headers(), json=payload, timeout=10)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0]["id"] if results else None


def add_symbol(symbol: str) -> str:
    """Add (or re-activate) a symbol.

    Returns one of: "added", "reactivated", "already_active".
    """
    symbol = _norm(symbol)
    page_id = _find_page_id(symbol)
    if page_id:
        r = requests.get(f"{_BASE}/pages/{page_id}", headers=_headers(), timeout=10)
        r.raise_for_status()
        was_active = (
            r.json().get("properties", {}).get("Active", {}).get("checkbox", False)
        )
        if was_active:
            return "already_active"
        patch = requests.patch(
            f"{_BASE}/pages/{page_id}",
            headers=_headers(),
            json={"properties": {"Active": {"checkbox": True}}},
            timeout=10,
        )
        patch.raise_for_status()
        return "reactivated"

    ds_id = _resolve_data_source_id()
    create = requests.post(
        f"{_BASE}/pages",
        headers=_headers(),
        json={
            "parent": {"type": "data_source_id", "data_source_id": ds_id},
            "properties": {
                "Symbol": {"title": [{"text": {"content": symbol}}]},
                "Active": {"checkbox": True},
            },
        },
        timeout=10,
    )
    create.raise_for_status()
    return "added"


def remove_symbol(symbol: str) -> str:
    """Soft-delete by clearing Active.

    Returns one of: "removed", "already_inactive", "not_found".
    """
    symbol = _norm(symbol)
    page_id = _find_page_id(symbol)
    if not page_id:
        return "not_found"
    r = requests.get(f"{_BASE}/pages/{page_id}", headers=_headers(), timeout=10)
    r.raise_for_status()
    was_active = (
        r.json().get("properties", {}).get("Active", {}).get("checkbox", False)
    )
    if not was_active:
        return "already_inactive"
    patch = requests.patch(
        f"{_BASE}/pages/{page_id}",
        headers=_headers(),
        json={"properties": {"Active": {"checkbox": False}}},
        timeout=10,
    )
    patch.raise_for_status()
    return "removed"
