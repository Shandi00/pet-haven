# backend/AGENTS.md

在 `backend/` 工作時適用；根目錄 [AGENTS.md](../AGENTS.md) 的規則仍然有效。

後端是 Python FastAPI，正在從舊 Node 版（`backend-legacy/`）搬遷。搬遷規則與順序見 [後端改用 FastAPI 規格](../docs/superpowers/specs/2026-11-25-後端改用FastAPI-design.md)。

## 結構

- `app/main.py`：建立 app，router 在這裡用 `include_router` 註冊。
- `app/routers/`：一個資源一個檔案，路徑前綴沿用舊版（例如 `/api/pets`）。商業邏輯較多時放進 `app/services/`，不要全部寫在路由裡。
- `app/db.py`：用 `get_db()` 取得資料庫。collection 名稱與欄位沿用舊版 Mongoose，不改 schema；新增欄位要有預設值，舊資料才不會壞掉。
- `app/config.py`：所有環境變數從 `Settings` 讀取；新的變數寫進 `.env.example`，值留空。

## 寫法

- **搬遷**：以 `backend-legacy/` 的行為為準（路徑、欄位、JWT、密碼雜湊、Socket.IO 事件），遵守規格 §6 的相容規則。
- **只能處理自己的資源**：修改申請或動物前，確認目前使用者是擁有者。`admin` 例外。
- **輸入驗證**：用 Pydantic model；驗證失敗會自動回 400。
- **回應格式**：成功時回傳 `ok(data)`，也就是 `{ success: true, data }`；失敗時 `raise HTTPException(狀態碼, "繁體中文訊息")`，會轉成 `{ success: false, message }`。
- **記錄**：用 `logging`，不要 `print`；log 裡不能有密碼、token、Email、電話。
- **路由順序**：固定路徑（如 `/featured`）要寫在參數路徑（如 `/{id}`）之前。
- **Swagger**：FastAPI 會自動產生；每支路由要寫 `summary`，必要時寫 `responses`。

## AI 與 LLM

- 只有後端可以呼叫 LLM；金鑰從 `app.config` 讀取，新的變數名稱寫進 `.env.example`，值留空。
- 送給 LLM 的內容只放動物與配對欄位，不放使用者姓名、Email、電話、地址。
- 一定要設逾時；逾時或失敗時改回傳規則理由，並在回應中標示 `source: "rule"`，讓前端知道這次沒有用到 AI。

## 測試

```bash
npm run test:backend   # 在專案根目錄執行，等同 backend/.venv 的 python -m pytest
```

- 測試放在 `tests/test_*.py`；單元測試不連真的資料庫（用 `app.dependency_overrides` 或 monkeypatch）。
- 新的 service 函式要有單元測試；權限相關的修改要有「別人不能做」的測試案例。
