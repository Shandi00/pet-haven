# backend/AGENTS.md

在 `backend/` 工作時適用；根目錄 [AGENTS.md](../AGENTS.md) 的規則仍然有效。

## 結構

- `server.js`：進入點，路由在這裡掛載到 `/api/*`。新增路由檔要在這裡註冊。
- `routes/`：一個資源一個檔案。商業邏輯較多時放進 `services/`，不要全部寫在路由裡。
- `models/`：Mongoose model。新增欄位要有預設值，舊資料才不會壞掉。
- `services/`：`advancedMatchingService.js`（規則配對）、`recommendationService.js`（熱門推薦）。AI 相關服務也放這裡。

## 寫法

- **登入驗證**：用 `middleware/auth.js` 匯出的 `auth`（必須登入）或 `optionalAuth`；角色用 `authorize(...roles)` 或 `middleware/roleCheck.js`。
- **只能處理自己的資源**：修改申請或動物前，確認 `req.user` 是擁有者，可參考 `checkOwnershipOrAdmin` 或 `routes/adoptions.js` 的 `POST /:id/review`。`admin` 例外。
- **輸入驗證**：用 `middleware/validation.js` 的 `validateBody`、`validateParams`，規則放在 `utils/validators.js`。
- **回應格式**：成功時回傳 `{ success: true, data }`，失敗時回傳 `{ success: false, message }`，`message` 用繁體中文，給使用者看。
- **記錄**：用 `utils/logger.js`，不要新增 `console.log`；log 裡不能有密碼、token、Email、電話。
- **路由順序**：固定路徑（如 `/featured`）要寫在參數路徑（如 `/:id`）之前。
- **swagger**：新增或修改 API 時，同步更新路由上方的 `@swagger` 註解。

## AI 與 LLM

- 只有後端可以呼叫 LLM；金鑰從 `process.env` 讀取，新的變數名稱寫進 `.env.example`，值留空。
- 送給 LLM 的內容只放動物與配對欄位，不放使用者姓名、Email、電話、地址。
- 一定要設逾時；逾時或失敗時改回傳規則理由（`advancedMatchingService` 的 `analysis.strengths`、`analysis.concerns`），並在回應中標示 `source: "rule"`，讓前端知道這次沒有用到 AI。

## 測試

```bash
npm run test:unit                # jest，測試放在 tests/，檔名 *.test.js
node test-integration-verbose.js # 整合測試，需要後端在 :5000 執行（CI 會跑）
```

- 新的 service 函式要有單元測試；權限相關的修改要有「別人不能做」的測試案例。
- `backend/` 根目錄的 `test-*.js` 是舊的手動測試腳本，CI 只用 `test-integration-verbose.js` 和 `test-socketio-resilience.js`。新測試一律寫進 `tests/`。
