# 前端對後端的接口

前端檔案：`static/index.html`（單檔，不用建置）。
後端用 FastAPI 掛靜態資料夾即可：`app.mount("/", StaticFiles(directory="static", html=True))`，
注意要放在所有 `/api` 路由**之後**。連不到 `/api/health` 時，畫面右上角顯示 MOCK，用示範資料跑。

## 路由

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/health` | 回 200 即可，畫面右上角變 ONLINE |
| POST | `/api/ask` | 問答：檢索 → 組提示詞 → Claude 生成答案（**會用到 Claude 額度**），畫面使用這個 |
| POST | `/api/search` | 只檢索，回傳最相近的資料片段（不呼叫 Claude），除錯與評測用 |

錯誤時回非 2xx，body `{"detail": "錯誤訊息"}`，畫面會直接顯示 detail。

| 狀態碼 | 情況 |
|---|---|
| 400 | 問題是空白 |
| 422 | 請求格式不對（問題超過 500 字、`top_k` 不在 1 到 10） |
| 502 | 語言模型（Claude）暫時無法使用 |
| 503 | 向量模型（Ollama）暫時無法使用 |

## 請求格式（`/api/ask`、`/api/search` 相同）

```json
{"question": "怎麼防止子網域接管？", "top_k": 3}
```

- `question`：必填，1 到 500 字。
- `top_k`：選填，預設 3，範圍 1 到 10，代表要檢索幾塊資料。

## 回傳格式

POST `/api/ask`：

```json
{
  "question": "怎麼防止子網域接管？",
  "answer": "根據檢索資料…（繁體中文，含簡易 Markdown：粗體、清單、行內程式碼）",
  "sources": [
    {"ref": 1, "id": 35, "title": "M1037 Filter Network Traffic"},
    {"ref": 2, "id": 529, "title": "Subdomain Takeover Prevention Cheat Sheet"}
  ]
}
```

- `sources[].ref`：對應答案裡的 `[1]`、`[2]` 編號（提示詞裡資料片段的編號）。
- `sources[].id`：資料庫 `chunks` 表的 id。
- `sources[].title`：該塊所屬文件的標題。

POST `/api/search`：

```json
{
  "question": "怎麼防止子網域接管？",
  "results": [
    {"id": 529, "title": "Subdomain Takeover Prevention Cheat Sheet", "content": "…完整內文…"}
  ]
}
```

## 畫面行為（後端要配合的點）

- 一次問答要等 Claude 生成，畫面只顯示「生成中 N 秒」，**不要在後端設過短的逾時**。
- 答案裡的 `[數字]` 只有在 `sources` 有對應的 `ref` 時，才會變成可點的標籤。
- 資料中找不到答案時，答案會明說「資料中沒有」，不會硬湊。

## 已移除

IP／網域查證（`/api/analyses`）與黑名單（`/api/blocklist`）已從前後端移除，相關程式與查表資料也已從專案刪除。
