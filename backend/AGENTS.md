# backend/AGENTS.md

在 `backend/` 工作時適用；根目錄 [AGENTS.md](../AGENTS.md) 的規則仍然有效。

後端是 Python FastAPI，已從舊 Node 版（`backend-legacy/`，只供參考）完整搬遷，路徑與回應格式與舊版相同。相容規則見 [後端改用 FastAPI 規格](../docs/superpowers/specs/2026-11-25-後端改用FastAPI-design.md)。

## 結構

- `app/main.py`：建立 app，新的 router 加進 `ROUTERS`。uvicorn 啟動的是 `app.main:asgi_app`（含 Socket.IO）。
- `app/routers/`：一個資源一個檔案，路徑前綴沿用舊版（例如 `/api/pets`）。商業邏輯放 `app/services/`（例如 `advanced_matching.py` 規則配對、`recommendation.py` 推薦）。
- `app/models/`：每個 collection 一個檔，定義 Mongoose 對應的 `SCHEMA`（`app/core/schema.py`）、建立新文件的 `prepare_new_*` 與輸出用的 `*_json`（含虛擬欄位）。collection 名稱與欄位沿用舊版，不改 schema；新增欄位要有預設值。
- `app/core/`：`serialize`（輸出格式同 Mongoose toJSON）、`validation`（Joi 相容的輸入驗證）、`populate`、`security`（JWT、bcrypt）、`uploads`。
- `app/deps.py`：`current_user`／`optional_user`／`require_roles`，以及舊版 pets、adoptions、users 用的 `token_user_zh`（錯誤格式 `{ error }`）。
- `app/realtime.py`：Socket.IO；推送用 `emit_to_user(user_id, event, data)`。通知一律用 `app.models.notification.create_notification` 或 `safe_notify`，會同時推送。
- `app/config.py`：所有環境變數從 `Settings` 讀取；新的變數寫進 `.env.example`，值留空。

## 寫法

- **回應格式**：每個路由檔沿用舊版的格式（有的是 `{ success, data }`，有的是 `{ error }`），前端依賴這些格式，不要改。新的 API 用 `{ success: true, data }`／`{ success: false, message }`。
- **只能處理自己的資源**：修改申請或動物前，確認目前使用者是擁有者（`same_id`）。`admin` 例外。認養申請用 `can_manage_adoption`。
- **ID**：路徑上的 id 用 `oid()` 轉換，不合法時回 404 或 400，不能 500。
- **輸入驗證**：照 Joi 的寫法用 `app/core/validation.py`（`O`、`S`、`N`…），寫入資料庫前用 model 的 `SCHEMA` 驗證；不要直接把 request body 寫進資料庫。
- **記錄**：用 `logging.getLogger(__name__)`，不要 `print`；log 裡不能有密碼、token、Email、電話。每筆 log 自動帶 request id（回應標頭 `X-Request-ID`），存取紀錄由 `app/core/logging.py` 統一產生，不含 query string。
- **稽核**：登入、權限、管理員操作、認養審核這類動作用 `audit("動作", user=..., target=...)` 記錄，只放 id、角色、狀態；401／403 會自動記錄。
- **Socket.IO**：連線必須帶有效 JWT，只能加入自己的房間；新增事件時要用 `sio.get_session(sid)` 取得目前使用者，不能相信 client 送來的 userId。
- **請求大小**：單一請求上限是 `MAX_REQUEST_BYTES`（預設 55MB），上傳檔案用 `app/core/uploads.py`，不要自己把檔案整個讀進記憶體。
- **路由順序**：固定路徑（如 `/featured`）要寫在參數路徑（如 `/{id}`）之前。
- **Swagger**：FastAPI 自動產生；每支路由要寫 `summary`。

## AI 與 LLM

- 只有後端可以呼叫 LLM（Gemini，金鑰 `GEMINI_API_KEY`）；金鑰從 `app.config` 讀取。
- 送給 LLM 的內容只放動物與配對欄位，不放使用者姓名、Email、電話、地址。
- 一定要設逾時；逾時或失敗時改回傳規則理由，並在回應中標示 `source: "rule"`，讓前端知道這次沒有用到 AI。

## 測試

```bash
npm run test:backend   # 在專案根目錄執行，等同 backend/.venv 的 python -m pytest
```

- 測試放在 `tests/test_*.py`。用 `api` fixture 的測試會連到 `pet_haven_test` 資料庫（CI 用 `TEST_MONGODB_URI`，本機用 `backend/.env` 的連線字串），每個測試前清空；`client` fixture 不連資料庫。
- `make_user`、`make_pet` fixture 建立測試資料。外部服務（Google、政府開放資料）一律 monkeypatch。
- 新的 service 函式要有單元測試；權限相關的修改要有「別人不能做」的測試案例。
