# Pet Haven API 清單

- **對應任務**：04 API 契約與權限設計（「既有 API 引用 swagger，不重寫」）
- **用途**：一頁看完所有 API 的方法、路徑與權限。**請求與回應格式**：既有 API 看執行中的 Swagger（`http://localhost:5000/api-docs`），本期新增的 API 看[新增 API 契約](新增API契約.md)。
- **來源**：2026-11-25 解析 `backend/app/routers/*.py` 自動產生（共 100 支既有 API），與程式不一致時以程式為準。

## 權限欄的意思

| 權限 | 意思 |
|---|---|
| 公開 | 不需要登入 |
| 登入 | 需要 `Authorization: Bearer <JWT>`，沒帶或失效回 401。**說明欄寫「本人」「擁有者」「作者」的，路由內還會檢查是不是自己的資源**，不是的話回 403；`admin` 例外 |
| 登入＋admin | 只有 `admin` |
| 登入＋admin／shelter | 只有 `admin` 或 `shelter` |

## 本期新增（尚未實作）

格式、驗證、錯誤碼見[新增 API 契約](新增API契約.md)。

| 方法 | 路徑 | 說明 | 權限 | 任務 |
|---|---|---|---|---|
| PUT | `/api/matching/profile/game` | 保存 8 題遊戲答案與毛孩類型 | 登入（本人） | T10（後端計畫 Task 4） |
| GET | `/api/matching/top3` | Top 3 推薦與理由 | 登入（本人） | T13 |
| POST | `/api/matching/feedback` | 適合／不適合回饋；不適合時回傳重排後的 Top 3 | 登入（本人） | T13 |
| DELETE | `/api/matching/feedback` | 清除自己的回饋紀錄 | 登入（本人） | T13 |
| POST | `/api/ai/chat` | AI 助理問答（附來源） | 登入 | T12、T14 |
| POST | `/api/ai/explain` | 為一隻動物產生推薦理由 | 登入 | T12 |
| GET | `/api/resources/licensed-shops` | 持照寵物業者依縣市列表（選做） | 公開 | T16 |

既有的 `GET /api/matching/profile` 回應會多一個 `gameProfile` 欄位（T10）。

## Socket.IO 事件（既有，本期不新增）

連線時要帶 JWT，只能加入自己的房間（`app/realtime.py`）。

| 方向 | 事件 | 說明 |
|---|---|---|
| 前端 → 後端 | `join`、`sendMessage`、`messageRead`、`typing` | 加入房間、私訊、已讀、輸入中 |
| 後端 → 前端 | `newMessage`、`messageReadConfirm`、`userTyping` | 私訊相關 |
| 後端 → 前端 | `newNotification` | 新通知（認養審核結果等），由 `create_notification` 推送 |

## 既有 API（依路由檔）

### `adoptions.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| POST | `/api/adoptions` | 提交認養申請（舊格式） | 登入 |
| POST | `/api/adoptions/apply/{pet_id}` | 提交認養申請（前端使用） | 登入 |
| GET | `/api/adoptions/my-applications` | 我的認養申請 | 登入 |
| GET | `/api/adoptions/my-pets-applications` | 我的動物收到的申請 | 登入 |
| GET | `/api/adoptions/admin/all` | 所有認養申請（管理員） | 登入＋admin |
| GET | `/api/adoptions/admin/stats` | 認養統計（管理員） | 登入＋admin |
| GET | `/api/adoptions/{adoption_id}` | 認養申請詳情（申請人或管理員） | 登入 |
| PUT | `/api/adoptions/{adoption_id}/status` | 更新申請狀態（寵物擁有者或管理員） | 登入 |
| POST | `/api/adoptions/{adoption_id}/complete` | 完成認養（寵物擁有者或管理員）；同一隻動物其他進行中的申請一併結束並通知，回傳 `closedApplications` | 登入 |
| PUT | `/api/adoptions/{adoption_id}/cancel` | 取消申請（申請人） | 登入 |
| POST | `/api/adoptions/{adoption_id}/notes` | 新增審核備註（寵物擁有者或管理員） | 登入 |
| POST | `/api/adoptions/{adoption_id}/review` | 審核申請（寵物擁有者或管理員） | 登入 |
| GET | `/api/adoptions/{adoption_id}/details` | 申請詳情（申請人、寵物擁有者或管理員）；審核者另外取得 `reviewInsights`（[契約 §7](新增API契約.md)） | 登入 |

### `auth.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| POST | `/api/auth/register` | 註冊 | 公開 |
| POST | `/api/auth/login` | 登入 | 公開 |
| GET | `/api/auth/me` | 取得目前使用者 | 登入 |
| PUT | `/api/auth/profile` | 更新個人資料 | 登入 |
| PUT | `/api/auth/change-password` | 變更密碼 | 登入 |
| DELETE | `/api/auth/account` | 停用帳號 | 登入 |
| POST | `/api/auth/verify-token` | 驗證 token | 公開 |
| POST | `/api/auth/google/verify` | Google 登入（ID token） | 公開 |
| GET | `/api/auth/google` | Google 登入（轉址） | 公開 |
| GET | `/api/auth/google/callback` | Google 登入回呼 | 公開 |

### `browsing_history.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| POST | `/api/browsing-history` | 記錄瀏覽 | 登入 |
| GET | `/api/browsing-history` | 瀏覽歷史（只回傳仍可認養的寵物） | 登入 |
| DELETE | `/api/browsing-history` | 清除瀏覽歷史 | 登入 |

### `comments.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/comments/post/{post_id}` | 貼文的留言（不含回覆） | 公開 |
| GET | `/api/comments/user/{user_id}` | 某使用者的留言 | 公開 |
| GET | `/api/comments/{comment_id}/replies` | 留言的回覆 | 公開 |
| POST | `/api/comments` | 留言 | 登入 |
| POST | `/api/comments/{comment_id}/reply` | 回覆留言 | 登入 |
| PUT | `/api/comments/{comment_id}` | 編輯留言（15 分鐘內） | 登入 |
| DELETE | `/api/comments/{comment_id}` | 刪除留言（隱藏） | 登入＋admin |
| POST | `/api/comments/{comment_id}/like` | 留言按讚／取消 | 登入 |
| POST | `/api/comments/{comment_id}/report` | 檢舉留言 | 登入 |

### `data_import.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/data-import/animal-recognition` | 取得政府動物認領養資料（admin/shelter） | 登入＋admin／shelter |
| POST | `/api/data-import/import-animals` | 匯入選定的動物（admin/shelter） | 登入＋admin／shelter |
| GET | `/api/data-import/legal-pet-shops` | 取得政府合法特定寵物業名單 | 登入 |
| GET | `/api/data-import/legal-pet-shops-db` | 已匯入的合法寵物業（admin/shelter） | 登入＋admin／shelter |

### `health.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/health` | 健康檢查（不檢查資料庫） | 公開 |
| GET | `/api/ready` | 就緒檢查（資料庫可連線時回 200，否則 503） | 公開 |

### `matching.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/matching/analyze/{pet_id}` | 單一寵物配對分析 | 登入 |
| GET | `/api/matching/best-matches` | 最佳配對 | 登入 |
| POST | `/api/matching/batch-analyze` | 批次配對分析 | 登入 |
| PUT | `/api/matching/profile/lifestyle` | 更新生活方式檔案 | 登入 |
| PUT | `/api/matching/profile/experience` | 更新經驗檔案 | 登入 |
| PUT | `/api/matching/profile/environment` | 更新環境檔案 | 登入 |
| GET | `/api/matching/profile` | 取得配對檔案 | 登入 |

### `messages.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/messages/conversations` | 對話列表 | 登入 |
| GET | `/api/messages/unread-count` | 未讀訊息數 | 登入 |
| GET | `/api/messages/conversation/{user_id}` | 與某人的對話 | 登入 |
| POST | `/api/messages` | 發送訊息（文字或 multipart 檔案欄位 file） | 登入 |
| PUT | `/api/messages/{message_id}` | 編輯訊息（5 分鐘內） | 登入 |
| DELETE | `/api/messages/{message_id}` | 刪除訊息（軟刪除） | 登入 |
| POST | `/api/messages/{message_id}/read` | 標記訊息已讀 | 登入 |
| POST | `/api/messages/conversation/{user_id}/read-all` | 整段對話標記已讀 | 登入 |

### `notifications.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/notifications` | 我的通知 | 登入 |
| GET | `/api/notifications/unread-count` | 未讀數量 | 登入 |
| POST | `/api/notifications/read-all` | 全部標記已讀 | 登入 |
| POST | `/api/notifications/{notification_id}/read` | 標記已讀 | 登入 |
| DELETE | `/api/notifications/{notification_id}` | 刪除通知 | 登入 |
| DELETE | `/api/notifications` | 刪除所有已讀通知 | 登入 |

### `pets.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/pets/my-pets` | 我發布的寵物 | 登入 |
| GET | `/api/pets` | 寵物列表（篩選、分頁） | 公開 |
| GET | `/api/pets/featured` | 特色寵物 | 公開 |
| GET | `/api/pets/featured/list` | 特色寵物（舊端點） | 公開 |
| GET | `/api/pets/stats/overview` | 寵物統計 | 公開 |
| GET | `/api/pets/{pet_id}` | 寵物詳情 | 公開 |
| POST | `/api/pets` | 新增寵物（multipart，照片欄位 photos） | 登入 |
| PUT | `/api/pets/{pet_id}` | 更新寵物（multipart，新照片欄位 newPhotos） | 登入 |
| POST | `/api/pets/{pet_id}/like` | 切換喜愛 | 登入 |
| DELETE | `/api/pets/{pet_id}` | 刪除寵物（軟刪除） | 登入 |
| POST | `/api/pets/{pet_id}/sponsorship/click` | 記錄助養連結點擊 | 公開 |

### `posts.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/posts` | 貼文列表 | 選擇性登入 |
| GET | `/api/posts/categories/list` | 貼文分類 | 公開 |
| GET | `/api/posts/{post_id}` | 貼文詳情（含留言） | 選擇性登入 |
| POST | `/api/posts` | 發表貼文（multipart，圖片欄位 images，最多 5 張） | 登入 |
| PUT | `/api/posts/{post_id}` | 編輯貼文（作者或管理員） | 登入 |
| DELETE | `/api/posts/{post_id}` | 刪除貼文（軟刪除） | 登入 |
| POST | `/api/posts/{post_id}/like` | 按讚／取消按讚 | 登入 |
| PATCH | `/api/posts/{post_id}/status` | 更新貼文狀態（例如走失協尋標記已尋獲） | 登入 |

### `recommendations.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/recommendations` | 推薦寵物（登入時依偏好，否則熱門） | 選擇性登入 |
| POST | `/api/recommendations/refresh` | 清除我的推薦快取 | 登入 |

### `stats.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/stats` | 首頁公開統計 | 公開 |
| GET | `/api/shelters/{shelter_id}/stats` | 收容所統計（本人或管理員） | 登入 |

### `users.py`

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/api/users/me/stats` | 我的統計 | 登入 |
| GET | `/api/users/me/activities` | 我的活動時間軸 | 登入 |
| GET | `/api/users/profile` | 取得我的資料 | 登入 |
| PUT | `/api/users/profile` | 更新我的資料（含推薦偏好） | 登入 |
| GET | `/api/users/favorites` | 我收藏的寵物 | 登入 |
| POST | `/api/users/favorites/{pet_id}` | 加入／移除收藏 | 登入 |
| GET | `/api/users/saved-posts` | 我收藏的貼文 | 登入 |
| POST | `/api/users/saved-posts/{post_id}` | 收藏／取消收藏貼文 | 登入 |
| GET | `/api/users/admin/all` | 所有使用者（管理員） | 登入＋admin |
| GET | `/api/users/admin/search` | 搜尋使用者（管理員） | 登入＋admin |
| GET | `/api/users/admin/stats/overview` | 使用者統計（管理員） | 登入＋admin |
| GET | `/api/users/admin/{user_id}` | 使用者詳情（管理員） | 登入＋admin |
| PUT | `/api/users/admin/{user_id}/role` | 更新角色（管理員） | 登入＋admin |
| PUT | `/api/users/admin/{user_id}/active` | 啟用／停用帳號（管理員） | 登入＋admin |
| GET | `/api/users/{user_id}/adoptions` | 使用者的認養申請（本人或管理員） | 登入 |

