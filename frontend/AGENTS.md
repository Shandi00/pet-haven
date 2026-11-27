# frontend/AGENTS.md

在 `frontend/` 工作時適用；根目錄 [AGENTS.md](../AGENTS.md) 的規則仍然有效。

## 結構

- `src/App.js`：路由表。新增頁面要在這裡註冊。需要登入的新頁面，用 `src/services/auth.js` 的 `ProtectedRoute` 包起來。目前既有頁面沒有用它，各自在頁面內檢查登入狀態。
- `src/pages/`：一個網址一個頁面。
- `src/components/`：跨頁共用的元件；`src/components/ui/` 是基礎 UI 元件（Button、Input、Card、Modal、Toast 等，說明見其中的 README.md）。
- `src/services/api.js`：所有 API 呼叫都集中在這裡，依資源分組（`petAPI`、`adoptionAPI`、`matchingAPI` 等）。新增的 API 在這裡加一組，例如 `aiAPI`。
- `src/services/mockMode.js`、`src/services/aiMock.js`：AI 功能（配對遊戲、推薦、聊天）的假資料模式。設定 `REACT_APP_USE_MOCK=true`，或在瀏覽器把 localStorage 的 `useMockData` 設為 `true` 就會改用假資料；用完記得移除，畫面上沒有提示。其他頁面一律打後端（舊的 `mockAPI.js` 與假資料檔沒有人使用，已於 2026-11-27 刪除）。

## 寫法

- 先用 `components/ui/` 的元件，沒有合適的才新增；樣式用 Tailwind class，不要另寫 CSS 檔。
- 頁面不直接呼叫 axios，一律透過 `services/api.js`。
- 每個資料畫面都要處理三種狀態：載入中（`Skeleton` 或 `LoadingSpinner`）、錯誤（顯示後端回傳的 `message`）、沒有資料（`EmptyState`）。
- AI 回應中有 `source: "rule"` 時，畫面要顯示「目前使用規則推薦」之類的提示，不能假裝是 AI 產生的。
- 畫面文字用繁體中文；按鈕和表單要有可讀的 label，讓 Playwright 可以用文字找到元素。
- 不在前端保存或顯示金鑰；不呼叫 LLM。

## 測試

```bash
npm test -- --watchAll=false   # 單元測試（react-scripts / jest）
npm run test:e2e               # Playwright，測試放在 e2e/，需要前後端都在執行
```

- 動到展示主線（建檔、遊戲、推薦、回饋、聊天、申請）時，要新增或更新 `e2e/` 的測試。
