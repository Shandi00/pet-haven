# 專案維護與整理規則

## 整理紀錄

### 第一輪（commit 3a6df08）

- 根目錄操作文件依主題移入 docs；舊 .bak/.backup 備份移出 src。
- 根目錄 package.json 集中安裝、開發、建置與測試指令，不改變前後端依賴管理方式。
- 修正後端 seed 指令、整理重複的環境範本、修正 Windows 啟動腳本的工作目錄與全域停止 Node 行為。
- 補上 frontend/src/setupTests.js 載入 jest-dom。

### 第二輪（清理）

- 停止追蹤 backend/admin-token.txt、server.pid、security-test-results.json 與 Playwright 輸出（檔案仍留在本機）。
- 刪除後端根目錄約 35 個未被引用的一次性腳本（check-*、delete-*、force-delete*、import-* 重複版本、reset*.js 等），以及未被 require 的 routes/auth-fixed.js 與巢狀 backend/pet-adoption-platform/。
- 刪除根目錄 fix-frontend.bat（會刪除 package-lock.json）、test-all.bat（實際只檢查資料庫連線），以及 frontend 未使用的 start-fixed.bat、temp-check.css、空的 data-import.js。
- import-moa-licensed-shops.js 移至 backend/scripts（合法寵物業名單唯一的匯入來源）。
- 合併重疊文件：啟動指南併入 DEVELOPMENT.md；5 份 Google 登入文件合併為 docs/auth/GOOGLE_LOGIN.md；5 份政府資料匯入文件合併為「資料匯入指南」與「審核測試流程」兩份。
- 刪除歷史報告（docs/archive/reports、backend 測試報告）與 archive/snapshots；內容可在 git 歷史 commit 3a6df08 查閱。
- QA 追溯評估移至 docs/qa/assessments；提案簡報大綱移至 docs/presentation。

## 放置規則

| 內容 | 放置位置 |
| --- | --- |
| 安裝、開發與環境說明 | docs/guides |
| 登入設定與排查 | docs/auth |
| 匯入與審核流程 | docs/data-import |
| 功能與操作說明 | docs/features |
| 部署與 QA 規則 | docs/deployment、docs/qa |
| 後端資料工具（匯入、清理、補值） | backend/scripts |
| 單元測試 | backend/tests、前端元件旁的 *.test.js |
| 瀏覽器測試 | frontend/e2e |

新文件請使用相對連結，並加入 docs/README.md。同一主題只保留一份文件，更新時直接修改原文件。測試報告與階段報告不放進版本庫；備份使用 Git，不要建立 .bak/.backup 檔。

## 建議的下一階段

1. backend 根目錄仍有 seed、create-admin 與整合測試腳本。可再將整合測試移至 tests/integration，搬移時必須同時處理 require 相對路徑、dotenv 工作目錄、npm scripts 與 CI。
2. 依領域整理前端功能，例如 pets、adoptions、community、notifications；共用 UI 留在 components/ui。以單一功能逐步重構。
3. 拆分 backend/server.js 的應用設定、資料庫啟動與 Socket.IO 初始化，讓測試與啟動流程更容易獨立驗證。
4. （2026-11-25 已處理）docs/deployment 原有兩份僅大小寫不同的檢查表，已移除英文版 DEPLOYMENT_CHECKLIST.md，保留 deployment-checklist.md；舊內容可在 git 歷史查閱。
5. backend/admin-token.txt 已停止追蹤，但仍存在於 git 歷史。若該 token 仍有效，應撤銷並重新產生；若版本庫曾推送到遠端，也要視為已外洩。
6. 部分文件（功能清單、資料載入、匯入測試流程）列出測試帳號與密碼。這些帳號不可用於正式環境。
7. frontend/server.js 目前沒有被任何腳本引用，確認部署方式後決定保留或刪除。
