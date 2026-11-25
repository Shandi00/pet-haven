# 愛心動物認養平台 · Pet Haven

提供寵物搜尋、認養申請、使用者與收容所管理，並包含社群、訊息、通知及政府資料匯入功能。

前端使用 React 18、React Router、React Query 與 Tailwind CSS；後端使用 Python FastAPI、MongoDB Atlas（PyMongo）、JWT 與 Socket.IO（python-socketio），已從舊 Node.js 版完整搬遷（舊程式在 `backend-legacy/` 只供參考），規則見[後端改用 FastAPI 規格](docs/superpowers/specs/2026-11-25-後端改用FastAPI-design.md)。

## 開始開發

組員與 AI 工具請先讀 [AGENTS.md](AGENTS.md)。

以下指令在專案根目錄執行。需要 Node.js 22（前端）、Python 3.11 以上（後端）與 npm；資料庫使用 MongoDB Atlas，請先請管理者把你的 IP 加進 Atlas 的 Network Access，否則會連不上。

1. 執行 `npm run setup`，建立 `backend/.venv` 並安裝後端 Python 套件，再依前端 lockfile 安裝依賴。
2. 將 `backend/.env.example` 複製成 `backend/.env`，填入 `MONGODB_URI`（Atlas 連線字串）、`MONGODB_DB` 與 `JWT_SECRET`。
3. 第一次使用時執行 `npm run seed` 載入展示測資。
4. 在第一個終端執行 `npm run dev:backend`。
5. 在第二個終端執行 `npm run dev:frontend`。

也可以用 Docker：準備好 `backend/.env` 後執行 `docker compose up --build`。

PowerShell 若無法執行 `npm.ps1`，上述指令改用 `npm.cmd` 即可。

- 前端：http://localhost:3000
- 後端：http://localhost:5000
- API 文件：http://localhost:5000/api-docs
- 就緒檢查：http://localhost:5000/api/ready

Windows 也可執行 `start.bat`。詳見[開發指南](docs/guides/DEVELOPMENT.md)與[環境設定](docs/guides/ENVIRONMENT.md)。

## 常用指令

| 指令 | 用途 |
| --- | --- |
| `npm run setup` | 安裝前後端依賴 |
| `npm run dev:backend` | 啟動後端開發伺服器 |
| `npm run dev:frontend` | 啟動前端開發伺服器 |
| `npm run seed` | 載入展示測資（可重複執行） |
| `npm run build` | 建置前端 |
| `npm test` | 依序執行前後端單元測試，失敗時停止 |
| `npm run test:backend` | 執行後端單元測試 |
| `npm run test:frontend` | 執行前端單元測試，不進入監看模式 |
| `npm run test:e2e` | 執行 Playwright，需先啟動後端 |

根目錄的 package.json 只集中開發指令；後端依賴在 `backend/requirements.txt`，前端依賴與 lockfile 在 `frontend/`。

## 專案結構

```text
pet-haven/
├── backend/             FastAPI 後端（app/、tests/、requirements.txt）
├── backend-legacy/      舊 Node.js 後端，只供搬遷參考，搬完後刪除
├── frontend/            React 頁面、元件、API 服務與 E2E 測試
├── scripts/             專案診斷工具
├── docs/
│   ├── guides/          開發、啟動與環境設定
│   ├── auth/            Google 登入設定與排查
│   ├── data-import/     政府資料匯入操作
│   ├── features/        功能清單與使用說明
│   ├── deployment/      部署檢查表
│   ├── qa/              QA gates 與追溯評估
│   └── presentation/    提案簡報大綱
├── .github/             CI 與 PR 範本
├── .claude/             Claude Code 共用設定
└── AGENTS.md            組員與 AI 工具的開發指引
```

完整入口請見[文件索引](docs/README.md)；整理規則與後續建議請見[專案維護指南](docs/guides/PROJECT_ORGANIZATION.md)。歷史報告已移除（可於 git 歷史查閱），目前狀態以重新執行測試為準。
