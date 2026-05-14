"""Environment variables. Read once at import time."""
import os

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
# Your own user ID — used as the destination for the daily push and as an
# allowlist for who can issue commands. Leave empty to allow anyone.
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

# Notion
NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
# Data Source ID (preferred — the new Notion API operates on data sources,
# not databases). For databases with one data source these are 1:1 but the
# IDs differ. Find it via GET /v1/databases/{db_id}.data_sources[0].id
NOTION_DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "")
# Legacy fallback: if NOTION_DATA_SOURCE_ID is unset we'll resolve it from
# the database ID on first call.
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
# 2025-09-03 introduced the data_sources resource. Older versions still
# work for legacy single-data-source databases but new ones (like the one
# we just created) only respond on the new endpoints.
NOTION_VERSION = "2025-09-03"

# Vercel cron auth — Vercel sends `Authorization: Bearer ${CRON_SECRET}` for
# scheduled invocations. Set this in Vercel env vars to any random string.
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# How parallel to fetch stock prices. Yahoo rate-limits bursts hard, so we
# keep this low and rely on jitter + retries in stock.py. With 5 workers and
# a per-call delay <300ms, 60 symbols finish in ~10–15s.
STOCK_FETCH_WORKERS = int(os.environ.get("STOCK_FETCH_WORKERS", "5"))

# Skip the daily push when there was no US trading day to report. Taiwan
# weekdays Sun (6) and Mon (0) correspond to US Sat/Sun — no fresh prices.
SKIP_WEEKDAYS_TW = {0, 6}
