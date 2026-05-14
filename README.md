# us_stock_bot

每天台灣時間 06:00 把美股 watchlist 的現價、漲跌幅、盤前/盤後價格推到你的 LINE。
可以在 LINE 對話視窗用「加 NVDA」、「刪 TSLA」、「list」直接管理清單。

## 架構

```
Vercel Cron (22:00 UTC = 06:00 TW)
        ↓
   /api/cron.py  ──▶ Notion (讀 watchlist)
                ──▶ Yahoo Finance chart API (平行抓 15 個 workers)
                ──▶ LINE Messaging API (push)

LINE 訊息進來
        ↓
  /api/webhook.py ──▶ parser → Notion (加/刪/查)
                  ──▶ LINE reply
```

- 排程 + Webhook 都跑在 Vercel 同一個專案，免費版 Hobby 可滿足。
- Stock 資料直接打 Yahoo `chart/v8` 端點，不需要 yfinance 整包（含 pandas）依賴。
- 資料儲存用 Notion database（你可以直接在 Notion 上手動編輯，Bot 看得到變更）。

## 第一次使用

請看 [SETUP.md](./SETUP.md)。

## 檔案結構

```
us_stock_bot/
├── api/
│   ├── cron.py          # 每天 6am 觸發的 handler
│   └── webhook.py       # LINE webhook
├── lib/
│   ├── config.py        # 讀環境變數
│   ├── notion_db.py     # Notion API wrapper
│   ├── stock.py         # Yahoo chart API + ThreadPool
│   ├── line_api.py      # LINE push/reply + 簽章驗證
│   ├── parser.py        # 解析「加 NVDA」這類指令
│   └── formatter.py     # 訊息格式化
├── scripts/
│   └── seed_watchlist.py  # 一次匯入初始股票清單
├── tests/
│   ├── test_local.py    # 跑 fetcher + formatter (不需要 LINE/Notion)
│   └── test_parser.py   # 解析器 sanity test
├── vercel.json
├── requirements.txt
└── .env.example
```

## 本地測試

```bash
# 1) 抓股價測試 — 完全不需要 LINE / Notion token
pip install requests
python tests/test_local.py

# 2) 指令解析測試
python tests/test_parser.py

# 3) 整合測試（需要設好 .env）
pip install python-dotenv
python scripts/seed_watchlist.py
```
