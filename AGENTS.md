# AGENTS.md

給 AI 開發工具（Claude Code、Codex、Cursor、Copilot 等）與組員的共同開發指引。開始任何工作前先讀完本檔。

## 專案

Pet Haven（寵愛有家）是寵物配對認養平台，也是「智慧型資訊系統」課程的期末專題，**2026-12-09 展示**。認養者、送養者、收容機構可以在同一個平台完成尋找、配對、申請、審核到完成認養。本期重點是 AI：配對小遊戲、可解釋的 Top 3 推薦、具資料來源的 AI 助理。

## 先讀這些

| 文件 | 內容 |
|---|---|
| [需求與展示範圍](docs/superpowers/specs/2026-11-25-需求與展示範圍-design.md) | **需求來源**：任務 01 到 22、完成定義、必做與選做、展示主線、非功能需求 |
| [現況架構](docs/architecture/現況架構.md) | 技術組成、目錄、資料模型、API、主要流程、已知缺口 |
| [docs/README.md](docs/README.md) | 其他文件索引 |
| `http://localhost:5000/api-docs` | 執行中的 Swagger API 文件 |

做任何功能前，先在需求文件找到對應的**任務編號**和**完成定義**。需求文件沒寫的功能不要做；需要的話先提出，不要自行加入。

## 指令

```bash
npm run setup          # 安裝前後端套件
npm run dev:backend    # 後端 :5000（需要 backend/.env，可參考 backend/.env.example）
npm run dev:frontend   # 前端 :3000，API 由 setupProxy 轉給 :5000
npm --prefix backend run seed   # 載入測試資料
npm test               # 後端 jest＋前端單元測試
npm run test:e2e       # Playwright e2e（需要前後端都在執行）
```

## 開發流程

1. **規劃**：新功能用 Superpowers：需求規格放 `docs/superpowers/specs/`，實作計畫放 `docs/superpowers/plans/`。小修改不需要。
2. **分支**：從 `dev` 開 `feat/T<任務編號>-<簡短名稱>`，例如 `feat/T13-top3-ai-reason`；修 bug 用 `fix/T<編號>-<名稱>`。
3. **PR**：合併回 `dev`，標題格式 `[T13] Top 3 與 AI 理由`；說明中寫出對應的完成定義與測試方式。至少一位組員審查。
4. **發布**：`dev` 驗收通過後才合併到 `main`，展示版加上 tag（例如 `v1.0-demo`）。不要直接 push 到 `main`。
5. **commit 訊息**：`feat:`、`fix:`、`docs:`、`test:`、`chore:` 開頭，內容用繁體中文。

`.bmad-core/` 和程式註解中的「Story x.x」是之前使用 BMAD 框架留下的，保留作為參考；**目前流程以 Superpowers 加任務編號為準**，不要再新增 BMAD story。

## 規則

### 一定要做

- 先重用既有程式：`services/advancedMatchingService.js`（規則配對）、`services/recommendationService.js`（熱門推薦）、`PUT /api/matching/profile/*`（配對檔案）、`components/MatchAnalysisPanel.js`。不要另寫一套功能相同的程式。
- 會改資料的 API 一律驗證登入與角色；只能處理自己的資源（自己的申請、自己的動物）。`admin` 例外。
- 改動 API 時同步更新 swagger 註解。
- 新增的邏輯要附測試；動到展示主線時要跑 e2e。

### 不可以做

- 金鑰、`.env`、token、測試帳號密碼都不能進 repo。新的環境變數只寫進 `.env.example`，值留空。
- 真實姓名、電話、Email 等個資不進 repo、不寫進 log、不送給 LLM。本 repo 是**公開的**，文件中的組員一律以角色稱呼（PM／AI、前端、後端）。
- AI 產生的推薦理由與回答，只能引用資料庫中真實存在的欄位或知識庫中有標示來源的內容；沒有資料時要明確說不知道，不可以編造。疾病與醫療問題不做判斷，提醒使用者就醫。
- LLM 呼叫只能在後端進行；前端不可以直接呼叫 LLM，也不可以拿到金鑰。LLM 失敗或逾時時，要退回既有的規則理由，不能讓主線中斷。

## 回報

完成工作時說明：對應哪個任務編號、改了什麼、跑了哪些測試、哪些地方沒有驗證。測試失敗時照實回報，不要略過。
