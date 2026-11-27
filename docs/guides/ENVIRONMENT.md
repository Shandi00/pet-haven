# 環境設定

> **注意**：後端已改為 Python FastAPI（2026-11-25），本文件中後端相關的 Node 指令是舊版說明，只適用於 `backend-legacy/`。目前的安裝與啟動方式以 [README](../../README.md) 與 [backend/AGENTS.md](../../backend/AGENTS.md) 為準。

後端設定範本位於 [backend/.env.example](../../backend/.env.example)。複製到同一目錄的 .env 後填入本機值；不要將 .env 納入版本控制。

| 變數 | 用途 |
| --- | --- |
| NODE_ENV、PORT | 執行模式與後端埠號 |
| MONGODB_URI | MongoDB 連線字串 |
| JWT_SECRET、SESSION_SECRET | JWT 與 Session 密鑰 |
| FRONTEND_URL、CORS_ORIGINS | 前端網址與允許的來源；多來源以逗號分隔 |
| GOOGLE_CLIENT_ID、GOOGLE_CLIENT_SECRET、GOOGLE_CALLBACK_URL | Google OAuth；未使用時留空 |
| UPLOAD_PATH、MAX_FILE_SIZE | 上傳位置與檔案大小設定 |
| DB_CONNECT_MAX_RETRIES、DB_CONNECT_DELAY_MS | 資料庫重試設定 |
| READINESS_RETRIES、READINESS_DELAY_MS | 整合測試就緒等待設定 |

JWT_SECRET 與 SESSION_SECRET 請使用各自獨立的隨機值。開發時可分別執行 `node -e "process.stdout.write(require('crypto').randomBytes(32).toString('hex'))"` 產生。

前端預設連到 http://localhost:5000/api。若需覆寫，建立 frontend/.env.local 並設定 `REACT_APP_API_URL`；環境變數更新後要重新啟動前端。實際支援的其他前端變數可在 frontend/src 搜尋 import.meta.env（前端用 Vite，只會讀取 `REACT_APP_` 開頭的變數）。

Google 登入流程詳見 [Google 登入](../auth/GOOGLE_LOGIN.md)。日誌詳見 [LOGGING.md](../../backend/LOGGING.md)。
