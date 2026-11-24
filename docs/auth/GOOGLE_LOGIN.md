# Google 登入

平台支援兩種 Google 登入方式，都由 [backend/routes/auth.js](../../backend/routes/auth.js) 處理：

| 方式 | 端點 | 說明 |
| --- | --- | --- |
| Google One Tap（前端 `GoogleLoginButton` 元件） | `POST /api/auth/google/verify` | 前端取得 Google ID token 後交給後端驗證，回傳平台 JWT |
| 重新導向 OAuth | `GET /api/auth/google` → `GET /api/auth/google/callback` | 後端完成授權後導回前端 `/auth/callback` |

後端使用 google-auth-library 驗證 token；登入成功後發放效期 7 天的 JWT。若 email 已有帳號，會自動綁定 Google；新帳號的 `authProvider` 為 `google`。

## 設定步驟

1. 在 [Google Cloud Console](https://console.cloud.google.com/) 建立或選擇專案。
2. 「API 和服務 → OAuth 同意畫面」：使用者類型選「外部」，填寫應用程式名稱與聯絡 email。測試模式下，要把測試用的 Google 帳號加入「測試使用者」。
3. 「API 和服務 → 憑證 → 建立憑證 → OAuth 用戶端 ID」，類型選「網頁應用程式」：
   - 授權的 JavaScript 來源：`http://localhost:3000`
   - 授權的重新導向 URI：`http://localhost:5000/api/auth/google/callback`
   - 正式環境另外加入正式網域的對應網址。
4. 複製用戶端 ID 與密鑰，填入環境變數：

   backend/.env

   ```env
   GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=<client-secret>
   GOOGLE_CALLBACK_URL=http://localhost:5000/api/auth/google/callback
   FRONTEND_URL=http://localhost:3000
   ```

   frontend/.env.local

   ```env
   REACT_APP_GOOGLE_CLIENT_ID=<client-id>.apps.googleusercontent.com
   ```

5. 重新啟動前後端（前端環境變數只在啟動時讀取）。新憑證可能要等幾分鐘才生效。

## 驗證

```powershell
node backend/test-oauth-config.js
```

或執行根目錄的 `check-google-login.bat`。檢查通過後，開啟 http://localhost:3000/login 點擊 Google 登入，應會看到帳號選擇畫面，登入後導回平台。

## 常見問題

| 錯誤 | 原因與處理 |
| --- | --- |
| `401 invalid_client`／The OAuth client was not found | Client ID 或密鑰錯誤、用戶端已刪除，或憑證剛建立尚未生效。重新複製憑證並確認前後端使用同一個 Client ID。 |
| `redirect_uri_mismatch` | `GOOGLE_CALLBACK_URL` 與 Console 的重新導向 URI 不一致；協定、主機、埠號、路徑都必須完全相同。 |
| `access_denied`／無法登入測試帳號 | 同意畫面在測試模式，該帳號未加入測試使用者。 |
| 按鈕沒有出現 | frontend/public/index.html 需載入 `https://accounts.google.com/gsi/client`；確認 `REACT_APP_GOOGLE_CLIENT_ID` 已設定並重啟前端，查看瀏覽器主控台錯誤。 |
| `Invalid token` | 密鑰錯誤、token 過期或電腦時間不同步，重新登入一次。 |
