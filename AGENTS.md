# AGENTS.md

給 AI 開發工具（Claude Code、Codex、Cursor、Copilot 等）與組員的共同開發指引。開始任何工作前先讀完本檔。

規則分三層，進到哪個資料夾就再讀該資料夾的 AGENTS.md：

| 檔案 | 範圍 |
|---|---|
| `AGENTS.md`（本檔） | 全專案：流程、分支、共通規則 |
| [backend/AGENTS.md](backend/AGENTS.md) | 後端（FastAPI）：路由、權限、回應格式、LLM 呼叫、pytest |
| [frontend/AGENTS.md](frontend/AGENTS.md) | 前端：頁面、API 呼叫、UI 元件、mock、Playwright |

Codex 會自動合併這三層。Claude Code 透過各層的 `CLAUDE.md`（內容只有 `@AGENTS.md`）讀取同一份內容；`.claude/settings.json` 另外禁止 Claude 讀取 `.env` 和強制推送。規則只改 AGENTS.md，不要在 CLAUDE.md 寫另一份。

## 專案

Pet Haven（寵愛有家）是寵物配對認養平台，也是「智慧型資訊系統」課程的期末專題，**2026-12-09 展示**。認養者、送養者、收容機構可以在同一個平台完成尋找、配對、申請、審核到完成認養。本期重點是 AI：配對小遊戲、可解釋的 Top 3 推薦、具資料來源的 AI 助理。

## 先讀這些

| 文件 | 內容 |
|---|---|
| [需求與展示範圍](docs/superpowers/specs/2026-11-25-需求與展示範圍-design.md) | **需求來源**：任務 01 到 22、完成定義、必做與選做、展示主線、非功能需求 |
| [後端改用 FastAPI 規格](docs/superpowers/specs/2026-11-25-後端改用FastAPI-design.md) | 後端搬遷的相容規則與順序；舊 Node 後端在 `backend-legacy/` 只供參考 |
| [現況架構](docs/architecture/現況架構.md) | 系統架構圖、使用案例圖、技術組成、目錄、資料模型、API、主要流程、已知缺口 |
| [資料庫結構](docs/architecture/資料庫結構.md) | 每個 collection 的欄位、型別、可用值與索引；本期新增欄位標示 🆕 |
| [新增 API 契約](docs/api/新增API契約.md)、[API 清單](docs/api/API清單.md) | 本期新增 API 的格式與 AI 規則（定稿）；全部 API 的路徑與權限 |
| [docs/README.md](docs/README.md) | 其他文件索引 |
| `http://localhost:5000/api-docs` | 執行中的 Swagger API 文件 |

做任何功能前，先在需求文件找到對應的**任務編號**和**完成定義**。需求文件沒寫的功能不要做；需要的話先提出，不要自行加入。

## 指令

```bash
npm run setup          # 建立 backend/.venv 並安裝後端 Python 套件、安裝前端套件（需要 Python 3.11+、Node.js 22）
npm run dev:backend    # 後端 :5000（需要 backend/.env，可參考 backend/.env.example）
npm run dev:frontend   # 前端 :3000（前端程式直接呼叫 http://localhost:5000）
npm run seed           # 載入展示測資（收容所帳號與 8 隻動物，可重複執行）
npm test               # 後端 pytest（連 pet_haven_test 資料庫）＋前端單元測試
npm run test:e2e       # Playwright e2e（需要前後端都在執行）
docker compose up --build   # 用 Docker 同時啟動前後端（需要 backend/.env）
```

建立管理員：在 `backend/` 執行 `.venv/Scripts/python -m scripts.create_admin --email <email>`（Linux／macOS 為 `.venv/bin/python`），沒給 `--password` 會產生隨機密碼。

## 開發流程

1. **規劃**：新功能用 Superpowers：需求規格放 `docs/superpowers/specs/`，實作計畫放 `docs/superpowers/plans/`。小修改不需要。
2. **分支**：從 `dev` 開 `feat/T<任務編號>-<簡短名稱>`，例如 `feat/T13-top3-ai-reason`；修 bug 用 `fix/T<編號>-<名稱>`。
3. **PR**：合併回 `dev`，標題格式 `[T13] Top 3 與 AI 理由`；依 PR 範本填寫完成定義與測試方式。CI 要通過，並且至少一位組員審查。
4. **發布**：`dev` 驗收通過後才合併到 `main`，展示版加上 tag（例如 `v1.0-demo`）。不要直接 push 到 `main`。
5. **commit 訊息**：`feat:`、`fix:`、`docs:`、`test:`、`chore:` 開頭，內容用繁體中文。

程式註解中的「Story x.x」是之前使用 BMAD 框架開發時留下的編號；BMAD 設定檔已於 2026-11-25 移除（可在 git 歷史找回）。**目前流程以 Superpowers 加任務編號為準**，不要再新增 BMAD story。

## 規則

### 一定要做

- 先重用既有邏輯：後端搬遷時以 `backend-legacy/` 的實作為準，例如 `services/advancedMatchingService.js`（規則配對）、`services/recommendationService.js`（熱門推薦）、`PUT /api/matching/profile/*`（配對檔案），不要另寫一套邏輯不同的程式；前端重用 `components/MatchAnalysisPanel.js`。
- 會改資料的 API 一律驗證登入與角色；只能處理自己的資源（自己的申請、自己的動物）。`admin` 例外。
- 改動 API 時同步更新 swagger 註解。
- 新增或移除元件、角色、使用案例時，同步更新 `docs/architecture/diagrams/` 的 `.puml`，重新輸出 `.svg`，兩者一起 commit。
- 新增的邏輯要附測試；動到展示主線時要跑 e2e。

### 不可以做

- 金鑰、`.env`、token、真實帳號密碼都不能進 repo。新的環境變數只寫進 `.env.example`，值留空。seed 腳本裡的測試帳號只能用在本機與 CI，不可用在任何對外環境。
- 真實姓名、電話、Email 等個資不進 repo、不寫進 log、不送給 LLM。本 repo 是**公開的**，文件中的組員一律以角色稱呼（PM／AI、前端、後端）。
- AI 產生的推薦理由與回答，只能引用資料庫中真實存在的欄位或知識庫中有標示來源的內容；沒有資料時要明確說不知道，不可以編造。疾病與醫療問題不做判斷，提醒使用者就醫。
- LLM 呼叫只能在後端進行；前端不可以直接呼叫 LLM，也不可以拿到金鑰。LLM 失敗或逾時時，要退回既有的規則理由，不能讓主線中斷。

## 回報

完成工作時說明：對應哪個任務編號、改了什麼、跑了哪些測試、哪些地方沒有驗證。測試失敗時照實回報，不要略過。
