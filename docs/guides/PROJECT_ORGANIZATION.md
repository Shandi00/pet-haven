# 專案維護與整理規則

## 本次整理

- 根目錄操作文件依主題移入 docs；歷史測試、實作與修復報告移入 docs/archive/reports。
- 舊備份與依賴快照移入 archive/snapshots，保留原內容。程式仍由 backend/server.js 與 frontend/src/index.js 啟動。
- 根目錄 package.json 集中安裝、開發、建置與測試指令，不改變前後端依賴管理方式。
- 修正後端 seed 指令，整理重複的環境範本，修正 Windows 啟動腳本的工作目錄與全域停止 Node 行為。
- 補上 frontend/src/setupTests.js 載入 jest-dom，修正既有前端測試缺少 toBeInTheDocument matcher 的問題。
- .gitignore 新增瀏覽器測試輸出、PID、本機 token 與臨時備份規則。已追蹤的檔案不會因 ignore 規則而自動取消追蹤。
- 每次搬移的來源、目的與內容 SHA-256 記錄在 [organization-moves.json](../organization-moves.json)。備份內容未改寫。

## 放置規則

| 內容 | 放置位置 |
| --- | --- |
| 安裝、開發與環境說明 | docs/guides |
| 登入設定與排查 | docs/auth |
| 匯入與審核流程 | docs/data-import |
| 功能與操作說明 | docs/features |
| 部署與 QA 規則 | docs/deployment、docs/qa |
| 已完成的階段報告 | docs/archive/reports |
| 必須保存的舊程式快照 | archive/snapshots |
| 單元測試 | backend/tests、前端元件旁的 *.test.js |
| 瀏覽器測試 | frontend/e2e |

新文件請使用相對連結，並加入 docs/README.md。功能與設定說明要持續更新；歷史報告不作為目前通過測試或安全狀態的依據。新增備份優先使用 Git，而非將 .backup 檔放回 src。

## 建議的下一階段

1. 將後端根目錄的工具分為 scripts/import、scripts/maintenance、scripts/diagnostics，以及 tests/integration。搬移時必須同時處理 require 相對路徑、dotenv 的工作目錄、npm scripts 與 CI，本次保留原位置。
2. 釐清 auth-fixed.js、巢狀 pet-adoption-platform 目錄與重複元件的用途，確認引用後再合併。檔名相近不表示可以直接刪除。
3. 依領域整理前端功能，例如 pets、adoptions、community、notifications；共用 UI 留在 components/ui。以單一功能逐步重構。
4. 拆分 backend/server.js 的應用設定、資料庫啟動與 Socket.IO 初始化，讓測試與啟動流程更容易獨立驗證。
5. 處理 docs/deployment 的兩份僅大小寫不同的檢查表。Git 同時追蹤 DEPLOYMENT_CHECKLIST.md 與 deployment-checklist.md，在 Windows 上會有路徑衝突；應在可區分大小寫的工作目錄比較內容後再合併。
6. backend/admin-token.txt、backend/server.pid 與前端測試輸出原先已被 Git 追蹤。ignore 規則只能防止新增；後續應確認 token 是否仍有效，並處理取消追蹤與必要的憑證撤銷。本次未讀取或輸出 token 內容。

## 本次驗證（2026-10-12）

- 從根目錄執行 npm.cmd test：後端 4 個 suites、50 個測試；前端 1 個 suite、3 個測試，全部通過。
- npm.cmd run build：成功，仍有既有的 BOM、未使用變數、Hook 依賴與其他 lint 警告。
- 38 個搬移目的檔案的 SHA-256 與搬移前一致；檢查 76 個文件相對連結均指向存在的檔案。
- 環境範本沒有重複變數；git diff --check 通過。
- 未執行需要服務與資料庫的整合、E2E 或負載測試，也未執行資料寫入工具。