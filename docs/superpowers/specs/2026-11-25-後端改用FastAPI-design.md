# 後端改用 Python FastAPI：骨架與遷移規格

- **日期**：2026-11-25
- **狀態**：草稿，待組內確認
- **相關**：[需求與展示範圍](2026-11-25-需求與展示範圍-design.md)、[現況架構](../../architecture/現況架構.md)

## 1. 目的

組內決定把後端從 Node.js／Express 全面改為 Python FastAPI，資料庫改連 MongoDB Atlas。本文件定義：

1. **這一輪要交付的骨架**：新的 FastAPI 專案，可以啟動、連上 Atlas、通過健康檢查與 CI。
2. **之後搬遷各功能時要遵守的相容規則與順序**，讓前端不用改、既有帳號可以繼續登入。

本輪**不搬任何業務 API**。

## 2. 目標、非目標、反目標

**目標**
- `npm run dev:backend` 啟動的是 FastAPI，跑在 `:5000`，前端的 `setupProxy.js` 不用改。
- 連上 Atlas；`GET /api/health` 回 200，`GET /api/ready` 在資料庫可以連線時回 200、無法連線時回 503。
- Swagger 一樣在 `http://localhost:5000/api-docs`。
- 有 pytest 測試，CI 改跑 Python。
- 舊 Node 後端完整保留在 `backend-legacy/`，搬遷時當作參考。

**非目標（本輪不做）**
- 搬遷 auth、pets、adoptions 等業務 API。
- 改寫 `seed.js`。
- 資料搬遷：Atlas 從空資料庫開始，之後由 Python 版 seed 載入測資。
- 改前端程式。

**反目標（技術上做得到，仍算失敗）**
- 前端必須因為後端換語言而改 API 路徑、回應格式或 token 格式。
- 既有使用者的密碼雜湊或 JWT 在新後端失效。
- 任何金鑰、連線帳密進入 repo。

## 3. 已知風險（組內需要知道）

- **骨架合併到 `dev` 後，前端除了 mock 模式都無法運作**，直到 auth、pets、adoptions 搬完。前端組員在這段期間用 mock 模式開發（`shouldUseMockData`／`toggleMockData`）。
- 12/5 功能截止前要搬完展示主線需要的 API（§7 第 1 到 7 項），否則 12/6 無法展示。
- 後端組員現有的實作計畫 [T07/T08/T12](../plans/2026-11-25-後端組員任務-T07-T08-T12.md) 是照 Node 寫的，需要另外改寫成 Python 版（本輪不做，列為後續）。
- Atlas 預設只允許白名單 IP 連線。每位組員和展示機的 IP 都要加進 Network Access，否則會連不上。

## 4. 做法比較

| 做法 | 內容 | 取捨 |
|---|---|---|
| 新舊並行，逐支搬 | FastAPI 跑 `:8000`，proxy 依路徑分流，共用 JWT 與資料庫 | 主線隨時可以跑；過渡期要開兩個後端 |
| **直接取代（採用）** | Node 移到 `backend-legacy/`，FastAPI 接手 `backend/` 與 `:5000` | 結構最乾淨，沒有雙後端；搬完之前前端無法運作 |
| 只建骨架、不接前端 | 只做 FastAPI 與健康檢查，proxy 不動 | 只是把過渡期的決定往後延 |

組內選擇**直接取代**。

## 5. 本輪骨架設計

### 5.1 目錄

```
backend-legacy/          # 原 backend/ 整個搬過來（git mv），不再修改，搬完後刪除
backend/
  app/
    __init__.py
    main.py              # 建立 FastAPI app、CORS、/api-docs、lifespan 中連線與關閉 MongoDB
    config.py            # 從環境變數讀設定
    db.py                # AsyncMongoClient 與取得 database 的函式
    responses.py         # 統一回應格式與錯誤處理
    routers/
      __init__.py
      health.py          # /api/health、/api/ready
  tests/
    test_health.py
  requirements.txt
  .env.example
  AGENTS.md              # 改寫為 Python 後端規則
  CLAUDE.md              # 內容維持 @AGENTS.md
```

### 5.2 技術選擇

| 項目 | 選擇 | 理由 |
|---|---|---|
| Python | 3.11 以上（本機為 3.14） | FastAPI 與 PyMongo 目前版本都支援 |
| Web 框架 | `fastapi`、`uvicorn[standard]` | 組內決定 |
| MongoDB 驅動 | `pymongo` 內建的非同步 API（`AsyncMongoClient`） | Motor 已由 MongoDB 官方宣告停止維護，官方建議改用 PyMongo 的非同步 API |
| 設定 | `pydantic-settings`，讀取 `backend/.env` | 與 FastAPI 同一套型別驗證，缺少必要變數時啟動就報錯 |
| 測試 | `pytest`、`httpx`（FastAPI `TestClient` 需要） | Python 標準做法 |
| 套件管理 | `requirements.txt`＋`venv`（`.venv/`、`__pycache__/`、`.pytest_cache/` 加入 `.gitignore`） | 組員最熟悉，不需要另外安裝工具 |

### 5.3 環境變數（`backend/.env.example`，值留空或為本機預設）

```
MONGODB_URI=            # Atlas 格式：mongodb+srv://<user>:<password>@pet-haven.r1angoh.mongodb.net/?compressors=zlib
MONGODB_DB=pet_haven    # 連線字串裡沒有資料庫名稱，必須另外指定
CORS_ORIGINS=http://localhost:3000
```

埠號固定寫在啟動指令（`--port 5000`），不放環境變數。`JWT_SECRET` 等其他變數（Google OAuth、上傳、LLM）等搬到對應功能時再加；舊 `.env` 裡 Node 用的變數可以留著，新後端會忽略。`MONGODB_URI` 只放在 `backend/.env`，不進 repo。

### 5.4 端點

| 端點 | 行為 |
|---|---|
| `GET /api/health` | 不碰資料庫，回 `{ "success": true, "data": { "status": "ok" } }` |
| `GET /api/ready` | 對 MongoDB 執行 `ping`。成功回 200，失敗回 503 與 `{ "success": false, "message": "資料庫無法連線" }` |
| `GET /api-docs` | Swagger UI（`FastAPI(docs_url="/api-docs", openapi_url="/api-docs.json")`） |

### 5.5 回應格式

沿用 Node 版格式，前端不用改：
- 成功：`{ "success": true, "data": ... }`
- 失敗：`{ "success": false, "message": "繁體中文訊息" }`

`responses.py` 註冊 `HTTPException` 與 `RequestValidationError` 的處理函式，轉成失敗格式。驗證錯誤一律回 400（Node 版的行為），不使用 FastAPI 預設的 422。

### 5.6 檔案搬移

1. `git mv backend backend-legacy`。
2. 未進版控的檔案會跟著搬到 `backend-legacy/`，以下要搬回 `backend/`：
   - `.env`（只搬檔案，不讀內容；搬回後由組員補上 `MONGODB_DB`）
   - `uploads/`（動物照片，執行時資料）
3. `backend-legacy/node_modules` 保留在本機，不影響版控。

### 5.7 根目錄指令（`package.json`）

| 指令 | 新內容 |
|---|---|
| `setup` | 前端照舊 `npm ci`；後端改為建立 `backend/.venv` 並 `pip install -r backend/requirements.txt` |
| `dev:backend` | 使用 `backend/.venv` 裡的 Python 執行 `uvicorn app.main:app --reload --port 5000` |
| `test:backend` | 使用 `backend/.venv` 裡的 Python 執行 `pytest` |

Windows 與 Linux 的 venv 路徑不同（`Scripts/` 和 `bin/`），由實作者決定怎麼寫（例如一支小的 Node 腳本判斷平台）。

### 5.8 測試

- `test_health.py`：
  - `/api/health` 回 200 且格式正確。
  - `/api/ready`：資料庫 `ping` 成功時回 200，失敗時回 503（用 monkeypatch 或 dependency override 模擬，不連真的資料庫）。
  - 驗證錯誤與 404 回傳 `{ success: false, message }` 格式。
- 單元測試不連 Atlas。

### 5.9 CI（`.github/workflows/integration-tests.yml`）

- 改用 `actions/setup-python`，安裝 `backend/requirements.txt`，執行 `pytest`。
- 保留 `mongo:5.0` service，`MONGODB_URI=mongodb://localhost:27017`、`MONGODB_DB=pet_haven_test`。CI 不連 Atlas。
- 啟動 uvicorn 後等待 `/api/ready` 回 200。
- 原本的 Node 整合測試（`test-integration.js`）與 seed 步驟移除；Python 版 seed 完成後再加回 seed 步驟。

### 5.10 文件同步

本輪要更新：
- `AGENTS.md`：指令、技術組成，以及「一定要做」中重用 Node 檔案的規則（改成「搬遷時以 `backend-legacy/` 的實作為準，不另寫一套不同的邏輯」）。
- `backend/AGENTS.md`：改寫成 Python 規則（路由、權限、回應格式、LLM 呼叫、pytest）。
- `README.md`：安裝與啟動方式。
- `docs/architecture/現況架構.md` 與 `docs/architecture/diagrams/*.puml`：技術標示從 Node／Express／Mongoose 改為 FastAPI／PyMongo，重新輸出 `.svg` 一起 commit。
- `需求與展示範圍` 的 T20 與相關段落：展示機改為 Python＋Atlas。

不在本輪：後端組員實作計畫改寫（見 §9）。

## 6. 搬遷時的相容規則

每支 API 搬到 FastAPI 時都要遵守，目的是前端與既有資料都不用改：

| 項目 | 規則 |
|---|---|
| 路徑 | 與 Node 版相同（例如 `/api/auth/login`、`/api/pets/:id`） |
| 回應格式 | 見 §5.5；欄位名稱與 Node 版相同（包含 `_id`） |
| JWT | HS256，用同一個 `JWT_SECRET`；payload 為 `{ userId, role }`，效期 7 天；前端用 `Authorization: Bearer <token>` |
| 密碼 | Node 版用 `bcryptjs`（cost 12）產生的 `$2a$`／`$2b$` 雜湊，Python 用 `bcrypt` 套件驗證，新密碼也用 cost 12 |
| 資料表 | 沿用 Mongoose 的 collection 名稱（`users`、`pets`、`adoptions`、`notifications`、`messages` 等）與欄位名稱，不改 schema |
| 即時通知 | 用 `python-socketio` 掛在同一個 ASGI app；事件名稱與 payload 沿用 Node 版（`join`、`sendMessage`、`messageRead`、`typing`；伺服器發送 `newMessage`、`messageReadConfirm`、`userTyping` 與通知事件，實際清單以 `backend-legacy/` 為準） |
| 上傳檔案 | 靜態路徑沿用 `/uploads/...`，檔案放在 `backend/uploads/` |
| 權限 | 會改資料的 API 一律驗證登入與角色；只能處理自己的資源，`admin` 例外 |
| Swagger | FastAPI 會從路由自動產生；每支路由要寫 `summary` 與回應範例 |
| 測試 | 每支搬好的 API 附 pytest 測試 |

## 7. 搬遷順序（依展示主線）

| 順序 | 範圍 | 對應任務 |
|---|---|---|
| 1 | Python 版 seed（同一組測試帳號與動物，可重複執行不產生重複資料） | T08 |
| 2 | auth：註冊、登入、取得目前使用者 | 主線 ① |
| 3 | pets：列表、篩選、詳情、照片 | 主線 ③ |
| 4 | adoptions：送出申請、審核、完成，加上擁有者權限 | T07，主線 ⑤ 到 ⑧ |
| 5 | notifications＋Socket.IO | 主線 ⑥ |
| 6 | matching profile、規則配對、Top 3 與回饋重排 | T09、T13 |
| 7 | AI 聊天、LLM 呼叫層與備援 | T12、T14 |
| 8 | messages、recommendations、browsing-history、stats、shelters、users | 既有功能 |
| 9 | posts、comments（社群討論區）、data-import、Google 登入 | 簡報提到的延伸功能，視時間決定 |

`debug-notifications` 不搬。第 1 到 7 項要在 12/5 前完成。

## 8. 交給實作者決定

- `package.json` 跨平台呼叫 venv Python 的寫法。
- `config.py`、`db.py` 的內部結構；資料庫連線要在 lifespan 中建立與關閉。
- 本輪骨架的分支名稱：需求文件沒有對應的任務編號，暫定 `chore/fastapi-skeleton`。

## 9. 未決事項

- **Atlas 上能不能放 seed 測試帳號**：AGENTS.md 規定 `seed.js` 的測試帳號只能用在本機與 CI。Atlas 是共用的雲端資料庫，需要組內決定是否視為「本機開發」。建議：開發用 `pet_haven_dev`，展示用另一個資料庫名稱，展示機的測試帳號另設密碼。
- **後端組員實作計畫**：T07、T08、T12 要改寫成 Python 版，並依 §7 重新分配搬遷工作。
