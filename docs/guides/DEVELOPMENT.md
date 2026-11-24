# 開發指南

所有指令都從專案根目錄執行；PowerShell 可以使用 `npm.cmd` 取代 `npm`。

## 本機開發

```powershell
npm.cmd run setup
Copy-Item backend/.env.example backend/.env
# 編輯 backend/.env 後，在兩個終端分別執行：
npm.cmd run dev:backend
npm.cmd run dev:frontend
```

`setup` 使用 npm ci，依照兩個 package-lock.json 安裝依賴。根目錄沒有需要安裝的依賴。前端輸出位於 frontend/build。

## 驗證

```powershell
npm.cmd run test:backend
npm.cmd run test:frontend
npm.cmd run build
```

`npm.cmd test` 依序執行兩邊測試，任一失敗即回傳失敗狀態。這些單元測試不需啟動正式資料庫。

整合測試需先設定測試資料庫並啟動後端，再執行：

```powershell
Set-Location backend
node test-integration.js
```

E2E 測試需先啟動後端，再於根目錄執行 `npm.cmd run test:e2e`。Playwright 會啟動前端，或在本機重用已啟動的前端服務。首次使用需在 frontend 目錄執行 `npx.cmd playwright install chromium`。

更多測試說明：[後端測試](../../backend/README_TESTING.md)、[E2E 指南](../../frontend/E2E_TESTING_GUIDE.md)。其中舊的通過數量是歷史紀錄。

## 資料操作

後端根目錄與 backend/scripts 包含匯入、清理、補值等工具，可能寫入或刪除資料。執行前先檢查該腳本的連線來源與作用範圍，使用測試資料庫驗證。

`npm --prefix backend run seed` 現在正確指向 backend/seed.js；本次整理未執行任何資料匯入、清理或 seed。

## Windows 啟動入口

`start.bat`、`quick-start.bat`、`start-frontend.bat` 會先切換至腳本所在目錄。quick-start.bat 不再停止所有 Node 程序；啟動前請自行關閉占用 3000、5000 埠的專案服務。
