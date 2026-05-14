# 完整設定指南

照下面的順序做，總共大約 30 分鐘。每步驟結尾標有 ⚙️ 的東西最後都要填到 Vercel 環境變數裡。

---

## 1. LINE Messaging API（你應該已經做完）

如果還沒：

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 建一個 Provider（或用既有的）。
2. 在 Provider 底下建一個 **Messaging API** channel。
3. 在 channel 設定頁拿到：
   - **Channel access token (long-lived)** ⚙️ → `LINE_CHANNEL_ACCESS_TOKEN`
   - **Channel secret** ⚙️ → `LINE_CHANNEL_SECRET`
4. 在 channel 設定頁把 **Auto-reply messages** 跟 **Greeting messages** 兩個關掉（否則官方罐頭回覆會跟我們的回覆打架）。
5. 加機器人為 LINE 好友（掃 QR code 或用 Channel ID）。

### 1.1 拿到自己的 LINE User ID

兩種方法擇一：

**方法 A（推薦）：用 webhook 一次性印出**

部署完之後（步驟 5），先打開 Vercel function logs，然後從 LINE 傳一則訊息給 Bot。Log 會印出 `userId: U....`，那串就是你的 User ID。

**方法 B：用 LINE Developers Console**

到 channel 設定的 **Basic settings** 頁，往下捲找 **Your user ID** — 那就是你自己的 ID（前面有 `U` 開頭）。

⚙️ `LINE_USER_ID` = 那串 `U` 開頭的字串

---

## 2. Notion

### 2.1 建 Integration（拿 API key）

1. 到 [Notion My Integrations](https://www.notion.so/my-integrations)。
2. 點 **+ New integration**，名字隨意（例如 `us_stock_bot`），workspace 選你自己的。
3. 創完後在 **Internal Integration Secret** 那一欄複製。
   ⚙️ `NOTION_API_KEY` = `secret_xxxxxxxx...`

### 2.2 建 Watchlist Database

在 Notion 找一個你想放的頁面，新增一個 **Database — Full page**，標題叫 `US Stock Watchlist`（或你喜歡的名字），把預設欄位改成這樣：

| 欄位名稱 | 類型 | 備註 |
|---|---|---|
| `Symbol` | Title | 股票代號，例如 NVDA |
| `Active` | Checkbox | 預設打勾 |
| `Added` | Created time | Notion 自動填，不用動 |
| `Notes` | Text | 可選，留 idea 用 |

⚠️ 欄位名稱要 **完全一致**（大小寫敏感），不然程式會找不到。

### 2.3 把 Integration 加入這個 Database

在 database 右上角點 `...` → **Connections** → 搜尋你剛建的 Integration → 加進來。沒這步的話 API 會回 `unauthorized`。

### 2.4 拿 Database ID

打開那個 database，看瀏覽器網址，會長這樣：

```
https://www.notion.so/yourworkspace/abc123def4567890abc123def4567890?v=...
                                    └─────────────┬──────────────┘
                                          這 32 字元就是 Database ID
```

⚙️ `NOTION_DATABASE_ID` = 那 32 字元（不用加 dash）

---

## 3. 本地跑一次測試（強烈建議）

```bash
cd us_stock_bot
python3 -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv
cp .env.example .env
# 把 LINE / Notion 的值填進 .env

# 驗 stock fetcher
python tests/test_local.py
# → 應該看到 13 檔的價格 + 漲跌幅

# 驗解析器
python tests/test_parser.py
# → 應該看到 13/13 passed

# 把初始 13 檔灌進 Notion
python scripts/seed_watchlist.py
# → Notion 上應該出現 SPY, SOXL, ASTS, UNH, MU, LEU, CEG, GOOGL, NBIS, TSLA, UNCY, MSFT, NE
```

如果這三步都過了，代表程式邏輯沒問題，下一步可以放心 deploy。

---

## 4. 推上 GitHub

```bash
cd us_stock_bot
git init
git add .
git commit -m "init us stock bot"
gh repo create us_stock_bot --private --source=. --push
# 或手動到 GitHub 開 repo 再 push
```

⚠️ 確認 `.env` 沒被 commit 進去（`.gitignore` 已經有排除）。

---

## 5. Vercel 部署

1. [Vercel Dashboard](https://vercel.com/dashboard) → **Add New → Project**。
2. Import 剛 push 的 GitHub repo。
3. Framework Preset 選 **Other**（Vercel 會自動偵測 `api/*.py` 是 Python serverless）。
4. **Root Directory** 設成 `us_stock_bot`（如果 repo 根目錄不是這個子資料夾）。
5. 點開 **Environment Variables**，把這些通通加進去（Production 環境就好）：

| Variable | Value |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 從 LINE console |
| `LINE_CHANNEL_SECRET` | 從 LINE console |
| `LINE_USER_ID` | 你的 `U...` |
| `NOTION_API_KEY` | `secret_...` |
| `NOTION_DATABASE_ID` | 32 字元 hex |
| `CRON_SECRET` | 自己亂打或 `openssl rand -hex 32` 產一個 |

6. 點 **Deploy**。第一次 build 大約 1–2 分鐘。

部署完 Vercel 會給你一個網址，類似 `https://us-stock-bot-xxx.vercel.app`。

---

## 6. 設定 LINE Webhook URL

1. 回到 LINE Developers Console → 你的 channel → **Messaging API** 分頁。
2. **Webhook URL** 填：
   ```
   https://us-stock-bot-xxx.vercel.app/api/webhook
   ```
3. 開啟 **Use webhook**。
4. 點 **Verify** — 應該回 `Success`。如果失敗，看 Vercel function logs debug。

---

## 7. 驗證整個 pipeline

### 7.1 手動觸發 cron

到 Vercel dashboard → **Cron** 分頁 → 點你的 cron job → **Run now**。
應該幾秒內在 LINE 收到當天 watchlist。

### 7.2 LINE 對話測試

在 LINE 對 Bot 傳：

```
list          → 顯示目前 watchlist + 現價
加 NFLX       → 加入 NFLX
刪 NE         → 移除 NE
help          → 顯示說明
```

---

## 常見問題

**Q: LINE 沒收到 6am 推播**
- 確認 Vercel **Cron** 分頁顯示 next run 是台灣時間 06:00（= UTC 22:00）。
- Hobby plan 的 cron 偶爾會延遲幾分鐘，正常現象。
- 看 Vercel logs，搜尋 `cron` — 應該看到 GET `/api/cron` 的成功紀錄。

**Q: Webhook 一直 verify failed**
- `.env` 的 `LINE_CHANNEL_SECRET` 跟 LINE console 的值 100% 一樣？前後不能有空白。
- Vercel 環境變數改完要 **redeploy** 才會生效。

**Q: Notion 回 `object_not_found`**
- 忘了把 Integration 加進 database 的 Connections（步驟 2.3）。

**Q: 「加 NVDA」沒反應**
- 看 Vercel logs 確認 webhook 有被打到。
- 確認你的 LINE User ID 跟 `LINE_USER_ID` 環境變數一致（拼錯就會被擋掉）。

**Q: 想改推播時間**
- 改 `vercel.json` 的 `schedule`。例如想改 5:30 TW = 21:30 UTC：`"30 21 * * *"`。
- Hobby plan 每個 cron 限 daily frequency（每 24 小時一次），所以分數欄非 0 OK，但每天只能跑一次。

**Q: 30 檔不夠想加更多**
- 已用 ThreadPool 平行 15 workers，60 秒 timeout 內可以撐約 100 檔。
- 如果還是 timeout，把 `vercel.json` 的 `api/cron.py` 的 `maxDuration` 從 60 → 不能再高了（Hobby 上限），只能升 Pro 或拆 batch。
