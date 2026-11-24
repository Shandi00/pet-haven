# 愛心動物認養平台 · Pet Haven

提供寵物搜尋、認養申請、使用者與收容所管理，並包含社群、訊息、通知及政府資料匯入功能。

前端使用 React 18、React Router、React Query 與 Tailwind CSS；後端使用 Express、MongoDB / Mongoose、JWT 與 Socket.IO。

## 開始開發

組員與 AI 工具請先讀 [AGENTS.md](AGENTS.md)。

以下指令在專案根目錄執行。需要 Node.js 22（與 CI 相同）、npm 與 MongoDB。

1. 執行 `npm run setup`，依照前後端各自的 lockfile 安裝依賴。
2. 將 `backend/.env.example` 複製成 `backend/.env`，填入資料庫連線與 JWT、Session 密鑰。
3. 在第一個終端執行 `npm run dev:backend`。
4. 在第二個終端執行 `npm run dev:frontend`。

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
| `npm run build` | 建置前端 |
| `npm test` | 依序執行前後端單元測試，失敗時停止 |
| `npm run test:backend` | 執行後端單元測試 |
| `npm run test:frontend` | 執行前端單元測試，不進入監看模式 |
| `npm run test:e2e` | 執行 Playwright，需先啟動後端 |

根目錄的 package.json 只集中開發指令；依賴與 lockfile 分別留在 backend、frontend。

## 專案結構

```text
pet-haven/
├── backend/             Express API、模型、路由、服務與測試
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
