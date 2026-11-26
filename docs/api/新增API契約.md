# 新增 API 契約

- **對應任務**：04 API 契約與權限設計；T06 的 AI 規則預設值也寫在這裡（§0）
- **使用者**：前端（T10、T15）、後端（T08、T12）、PM／AI（T13、T14）、知識庫（T11）
- **狀態**：**定稿 v1（2026-11-25）**。前後端照這份開發；任何欄位或規則異動都改這份文件，並同步更新前端假資料 `frontend/src/services/aiMock.js`。§0 的數值是預設值，T06 主責可以調整，調整時直接改 §0。

既有 API 不在此列，請看 Swagger（`http://localhost:5000/api-docs`）。

| # | 方法與路徑 | 任務 | 誰呼叫 |
|---|---|---|---|
| 1 | `PUT /api/matching/profile/game` | T10 | 前端小遊戲 |
| 1 | `GET /api/matching/profile`（既有，回應多一個 `gameProfile`） | T10 | 前端 |
| 2 | `GET /api/matching/top3` | T13 | 前端推薦頁 |
| 3 | `POST /api/matching/feedback`、`DELETE /api/matching/feedback` | T13、T15 | 前端推薦頁 |
| 4 | `POST /api/ai/chat` | T12、T14 | 前端聊天 |
| 5 | `POST /api/ai/explain` | T12 | 後端 Top 3 內部共用；前端可選用（例如動物詳情頁） |
| 6 | `GET /api/resources/licensed-shops`（**選做**） | T16 | 前端資源頁 |

既有 100 支 API 的方法、路徑與權限整理在 [API 清單](API清單.md)；資料欄位見 [資料庫結構](../architecture/資料庫結構.md)。

---

## 0. AI 規則（T06 預設值）

| 項目 | 決定 |
|---|---|
| LLM 供應商 | **Google Gemini**（Gemini API，非 Vertex AI） |
| 模型 | 環境變數 `GEMINI_MODEL`，預設 `gemini-3.1-flash-lite`（穩定版 Flash-Lite）。2026-11-26 由 `gemini-3.8-flash` 改：實測 3.8 一直回 503（模型忙碌）／429，3.1-flash-lite 可正常產生理由。換模型只改環境變數，不改程式 |
| 金鑰 | `GEMINI_API_KEY`，只放在 `backend/.env`；前端拿不到，也不直接呼叫 LLM |
| 呼叫方式 | 後端用已安裝的 `httpx` 呼叫 Gemini REST API，不另外加 SDK |
| 逾時 | 環境變數 `LLM_TIMEOUT_SECONDS`，預設 **8 秒**；不重試。逾時、錯誤、空回應、回傳格式不對，一律改用備援，HTTP 仍回 200 |
| 費用上限 | 展示期間使用 Gemini API 免費額度；如果改用付費方案，在 Google Cloud 帳單設定預算警示（建議 NT$300），超過就改回免費額度或只用規則理由。另外由 §0 的速率限制控制呼叫量 |
| 理由快取 | 送給 LLM 的白名單輸入完全相同時，10 分鐘內重用上次的 AI 理由，不再呼叫 Gemini；失敗的結果不快取。存在後端程序記憶體（最多 500 筆），重啟就清空。目的：免費額度每分鐘請求數有限，重排或重新整理 Top 3 時只需要替新的動物呼叫（2026-11-26 加入） |
| 速率限制（每位使用者） | `POST /api/ai/chat`：每分鐘 10 次；`GET /top3`、`POST /feedback`、`POST /api/ai/explain`：合計每分鐘 30 次。超過回 429 |
| 送給 LLM 的欄位（白名單） | 動物：`name`、`species`、`breed`、`ageCategory`、`size`、`personality.traits`、`personality.activityLevel`、`personality.goodWith`、`personality.specialNeeds`。使用者：`lifestyleProfile`、`experienceProfile` 的 `petOwnershipExperience`／`trainingExperience`、`environmentProfile` 的四個布林值、`gameProfile.petType.label`。**白名單以外一律不送**，包括姓名、Email、電話、地址、健康與醫療紀錄 |
| 紀錄 | log 只記 user id、pet id、`source`、耗時；不記錄訊息內容與 LLM 回覆 |
| 醫療問題 | 用關鍵字判斷（生病、發燒、嘔吐、拉肚子、腹瀉、咳嗽、受傷、流血、藥、疫苗副作用、症狀、診斷、獸醫……）。命中時**不呼叫 LLM**，直接拒答並提醒就醫 |
| 知識庫檢索 | 關鍵字比對（中文以字元 bigram 計算重疊），取最相關的前 3 筆，分數低於門檻視為查無資料；**查無資料時不呼叫 LLM**，直接回答不知道。知識庫格式見附錄。實作（T14，`app/services/knowledge_base.py`）：分數＝問題的 bigram 被條目（標題＋tags＋內容）涵蓋的比例，門檻 0.3；「什麼、怎麼、可以」等問句詞不列入比對；門檻在 T19 用實際問題集再調整 |

### Top 3 的硬條件（先篩掉，不計分）

1. 只取 `adoptionStatus = available` 且 `isActive = true` 的動物。
2. 使用者按過「不適合」的動物。
3. 使用者 `environmentProfile.hasChildren = true`，且動物 `personality.goodWith.children = false`。
4. 使用者 `environmentProfile.hasOtherPets = true`，且動物 `personality.goodWith.otherPets = false`。
5. 使用者 `environmentProfile.hasAllergies = true`，且動物是貓（`species = cat`）。
6. 使用者在 `recommendationProfile.species` 指定了物種時，只保留這些物種；沒指定就不限制。

`goodWith` 沒填（`null`）時不篩掉，交給計分扣分並寫進 `cautions`。

### 排序與回饋重排

1. 用既有規則配對 `app/services/advanced_matching.py` 的 `calculate_match(pet, user, normalized=True)` 計分（`matchScore`，0–100）。`normalized=True` 時，相容度只用使用者**有填的** `recommendationProfile` 偏好計算，完全沒填時給中性分 75。原因是既有相容度在偏好沒填時會把分母重設，分數超過 100（實測 150–190），只玩小遊戲的使用者每隻都會顯示 100。既有 API（`/analyze`、`/best-matches`）維持舊算法不變。顯示分數另外夾在 0–100。推薦理由（§5）也用同一個算法。（2026-11-26 調整）
2. **回饋重排**：使用者每按一次「不適合」，其他「物種與 `personality.activityLevel` 都和那隻相同」的動物扣 5 分，同一隻最多扣 15 分。
3. 分數相同時，較新上架（`createdAt` 較晚）的排前面；取前 3 名。

---

## 共通規則

- 下列 API 都要登入：在 `Authorization: Bearer <JWT>` 帶上 token，沒帶或失效回 401。`user`、`shelter`、`admin` 三種角色都可以用，但只能讀寫**自己的**遊戲結果、回饋與推薦。
- 成功：`{ "success": true, "data": ... }`；失敗：`{ "success": false, "message": "給使用者看的繁中訊息" }`。
- `source` 欄位說明理由或回答的來源：`"ai"`＝Gemini 產生；`"rule"`＝規則產生（推薦理由的備援，或聊天中醫療拒答、查無資料這類不呼叫 LLM 的回答）；`"fallback"`＝聊天時 LLM 失敗的備援訊息。前端遇到 `rule`、`fallback` 要顯示提示，不能假裝是 AI 產生的。
- 路徑或 body 裡的 id 不合法時回 400，找不到資料時回 404，不能回 500。
- LLM 出錯**不會**讓 API 回 5xx（見 §0「逾時」）。

| 狀態碼 | 情況 |
|---|---|
| 400 | 參數錯誤，例如 `verdict` 不是 `like` 或 `dislike`、`petId` 不是合法 id、訊息超過 500 字 |
| 401 | 沒登入或 token 失效 |
| 404 | 找不到動物 |
| 429 | 呼叫太頻繁（見 §0 速率限制） |

---

## 1. 儲存遊戲結果（T10）

`PUT /api/matching/profile/game`

小遊戲的 8 題答案經對照表（T05）轉換後，前端**先呼叫既有的三支 API** 寫入配對欄位，再呼叫這支 API 保存原始答案和毛孩類型。這支 API 只保存結果，不會改動配對欄位，所以遊戲答案仍然「沿用 `PUT /api/matching/profile/*`」寫入既有欄位。

| 既有 API | 遊戲要寫入的欄位與可用值 |
|---|---|
| `PUT /api/matching/profile/lifestyle` | `activityLevel`：`low`／`medium`／`high`；`availableTime`：`minimal`／`moderate`／`extensive`；`housingType`：`apartment`／`condo`／`townhouse`／`house-no-yard`／`house-with-yard` |
| `PUT /api/matching/profile/experience` | `petOwnershipExperience`：`none`／`beginner`／`intermediate`／`experienced` |
| `PUT /api/matching/profile/environment` | `hasChildren`、`hasOtherPets`、`noiseSensitive`、`hasAllergies`（布林值） |

注意：使用者的 `activityLevel` 用 `medium`，動物的 `personality.activityLevel` 用 `moderate`，兩者是既有欄位，不要改。

請求：

```json
{
  "answers": [
    { "questionId": "q1", "optionId": "A" },
    { "questionId": "q2", "optionId": "C" }
  ],
  "petType": { "code": "outdoor-buddy", "label": "戶外冒險型", "description": "適合活動量高、喜歡出門的毛孩" }
}
```

驗證規則：

- `answers` 必須剛好 8 筆；`questionId` 為 `q1` 到 `q8`，不可重複；`optionId` 為 `A` 到 `D`。
- `petType.code` 為 1–50 字的英數與 `-`；`label` 1–20 字；`description` 最多 100 字。
- 不符合時回 400，不寫入任何資料。

回應：`{ "success": true, "data": { "gameProfile": { ...請求內容, "completedAt": "2026-12-01T08:00:00.000Z" } } }`

- 結果存在 `User.gameProfile`，再玩一次就整筆覆蓋。
- 既有的 `GET /api/matching/profile` 回應多一個 `gameProfile` 欄位；沒玩過時為 `null`。

## 2. 取得 Top 3 推薦（T13）

`GET /api/matching/top3`

依 §0 的硬條件篩選、計分與回饋重排，取前 3 名，並為每一隻產生理由（與 §5 共用同一個服務函式，3 隻並行產生，整體不超過 `LLM_TIMEOUT_SECONDS`）。

回應：

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "pet": {
          "_id": "65f0c0ffee0000000000a001",
          "name": "小黑",
          "species": "dog",
          "breed": "米克斯",
          "age": { "value": 2, "unit": "years" },
          "ageCategory": "adult",
          "size": "medium",
          "activityLevel": "high",
          "photo": "/uploads/pets/sample.jpg"
        },
        "score": 92,
        "matchLevel": "perfect",
        "reason": {
          "summary": "牠每天需要散步一小時，跟你週末喜歡戶外活動的習慣很合。",
          "highlights": ["活動量相符：你選擇高活動量，小黑活動量高", "你有養狗經驗"],
          "cautions": ["住公寓需留意吠叫，建議先了解社區規定"],
          "source": "ai"
        }
      }
    ],
    "avoided": [
      { "petId": "65f0c0ffee0000000000a009", "name": "阿福", "note": "已避開：阿福（狗，活動量高），並降低相似動物的排序" }
    ],
    "generatedAt": "2026-12-01T08:00:00.000Z"
  }
}
```

- `pet` 是精簡過的動物資料：`age` 沿用 Pet 的 `{ value, unit }`（`unit` 為 `years` 或 `months`）；`activityLevel` 取自 `personality.activityLevel`；`photo` 是第一張照片的網址，沒有照片時為空字串。
- `score` 是四捨五入後的整數 `matchScore`（扣除回饋重排後）。
- `matchLevel` 沿用既有 `match_level()` 的 `level`：`perfect`（85 以上）、`excellent`（70 以上）、`good`（55 以上）、`fair`（40 以上）、`poor`。
- `reason`：`summary` 最多 80 字；`highlights`、`cautions` 各 0–3 筆、每筆最多 40 字（前後空白會去掉），**只能引用 §0 白名單裡的真實欄位**（見 AGENTS.md）。
- `reason.source = "rule"` 時，理由由既有 `generate_analysis()` 的 `strengths`、`highlights`、`concerns` 組成。
- `avoided` 列出這位使用者目前所有按過「不適合」的動物（最新的在前），`note` 由規則產生，說明避開了什麼。沒有回饋時為空陣列。
- 符合條件的動物不足 3 隻時，`items` 可以少於 3 筆；沒有任何結果時回傳空陣列，前端顯示空狀態和「重新開始」按鈕（呼叫 `DELETE /feedback`）。
- 使用者還沒填任何配對欄位時照常計分（既有計分有預設值），不回錯誤。

## 3. 回饋「適合／不適合」（T13、T15）

`POST /api/matching/feedback`

請求：`{ "petId": "65f0c0ffee0000000000a001", "verdict": "dislike" }`（`verdict`：`like` 或 `dislike`）

- 回饋存在 `User.matchFeedback`，同一隻動物只保留最新一筆；重新整理或下次登入，結果仍然一致。
- `dislike`：寫入後**直接回傳重排後的 Top 3**（格式與 `GET /top3` 的 `data` 完全相同），前端不必再呼叫一次 `GET /top3`。
- `like`：只記錄，不觸發重排，回傳 `{ "success": true, "data": { "recorded": true } }`；前端接著導向動物詳情或申請頁。
- `petId` 不合法回 400；動物不存在回 404。

`DELETE /api/matching/feedback`：清除自己的所有回饋紀錄（彩排用），回傳 `{ "success": true, "data": { "cleared": 3 } }`。

## 4. AI 助理聊天（T12、T14）

`POST /api/ai/chat`

請求：

```json
{
  "message": "第一次養貓要準備什麼？",
  "history": [
    { "role": "user", "content": "你好" },
    { "role": "assistant", "content": "你好，我是 Pet Haven 小幫手。" }
  ]
}
```

驗證規則（不符合回 400）：

- `message`：去掉前後空白後 1–500 字。
- `history`：可省略；最多 10 則，超過只取最後 10 則；`role` 只能是 `user` 或 `assistant`；每則 `content` 最多 500 字。
- 後端不保存聊天內容。

回應：

```json
{
  "success": true,
  "data": {
    "reply": "建議先準備：貓砂盆與貓砂、飼料與水碗、貓抓板、外出籠。想知道哪隻貓適合你嗎？",
    "sources": [
      { "title": "新手養貓準備清單", "ref": "faq-cat-001" }
    ],
    "actions": [
      { "label": "去玩配對遊戲", "to": "/match-game" },
      { "label": "看推薦動物", "to": "/recommendations" }
    ],
    "refused": false,
    "source": "ai"
  }
}
```

處理順序與各情況的回應：

| 順序 | 情況 | `reply` | `sources` | `refused` | `source` |
|---|---|---|---|---|---|
| 1 | 醫療或疾病問題（§0 關鍵字） | 提醒這可能和健康有關，建議盡快就醫 | `[]` | `true` | `rule` |
| 2 | 知識庫查無資料 | 明確說不知道，不編造，並建議可以做的事 | `[]` | `false` | `rule` |
| 3 | LLM 逾時或失敗 | 「小幫手暫時無法回答，請稍後再試」 | `[]` | `false` | `fallback` |
| 4 | 正常 | Gemini 只根據檢索到的知識庫內容回答 | 實際引用的條目 | `false` | `ai` |

- `sources[].ref` 是知識庫條目的 `id`，`title` 是條目標題；只列出回答真的用到的條目。
- `actions` 每次都提供（最多 2 個），路徑固定為 `/match-game`（配對遊戲）和 `/recommendations`（推薦），由前端計畫定案；訊息提到「推薦、適合、哪隻」時把「看推薦動物」排第一。

## 5. AI 推薦理由（T12）

`POST /api/ai/explain`

請求：`{ "petId": "65f0c0ffee0000000000a001" }`

回應：`{ "success": true, "data": { "reason": { "summary": "…", "highlights": [], "cautions": [], "source": "ai" } } }`

- 用**目前登入的使用者**的配對欄位，為指定動物產生理由；格式與 §2 的 `reason` 相同，失敗時一樣改用規則理由（`source: "rule"`）。
- `GET /top3` 在後端直接呼叫同一個服務函式，不透過 HTTP。前端可以在動物詳情頁使用這支 API。
- 送給 Gemini 的提示要求回傳 JSON `{ "summary", "highlights", "cautions" }`；解析失敗或欄位不符合長度限制，視同失敗。
- `petId` 不合法回 400；動物不存在回 404。

## 6. 持照寵物業者依縣市列表（T16，選做）

`GET /api/resources/licensed-shops?county=臺北市&page=1&limit=20`

**公開，不需要登入**（資源頁給所有人看）。既有的 `GET /api/data-import/legal-pet-shops-db` 有縣市篩選，但限 `admin`／`shelter`，而且會回傳負責人姓名，所以另開這支只讀、只回公開欄位的 API。12/5 前沒完成就移出展示，不影響主線。

查詢參數：

| 參數 | 說明 |
|---|---|
| `county` | 可省略。22 個縣市名稱之一（`臺北市`、`新北市`、`桃園市`、`臺中市`、`臺南市`、`高雄市`、`基隆市`、`新竹市`、`嘉義市`、`新竹縣`、`苗栗縣`、`彰化縣`、`南投縣`、`雲林縣`、`嘉義縣`、`屏東縣`、`宜蘭縣`、`花蓮縣`、`臺東縣`、`澎湖縣`、`金門縣`、`連江縣`），比對 `address` 開頭；「台」與「臺」視為相同。不在清單內回 400 |
| `page` | 預設 1 |
| `limit` | 預設 20，最大 50 |

回應：

```json
{
  "success": true,
  "data": {
    "shops": [
      {
        "_id": "65f0c0ffee0000000000b001",
        "name": "（範例）毛孩寵物店",
        "address": "臺北市大安區……",
        "businessItem": "買賣",
        "animalType": "犬、貓",
        "validDate": "2027-06-30T00:00:00.000Z",
        "rankText": "甲等"
      }
    ],
    "pagination": { "page": 1, "limit": 20, "total": 135 }
  }
}
```

- **只回傳上面 7 個欄位**；`ownerName`、`bossName`（負責人姓名，屬個資）、`originalData`、`validNumber` 一律不回傳。
- 排序：依 `name` 遞增，分頁結果才穩定。

---

## 附錄：資料欄位（新增到 `User`，T03、T08）

完整欄位與規則見 [資料庫結構](../architecture/資料庫結構.md) 的 User 表（標示 🆕 的列）。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `gameProfile` | `{ answers: [{ questionId, optionId }], petType: { code, label, description }, completedAt }` 或 `null` | §1；預設 `null` |
| `matchFeedback` | `[{ pet: ObjectId, verdict: "like" \| "dislike", createdAt }]` | §3；預設 `[]` |

AI 理由**不存資料庫**，每次請求即時產生。

## 附錄：知識庫格式（T11 產出，T14 使用）

檔案：`backend/app/data/knowledge_base.json`，內容為陣列：

```json
[
  {
    "id": "faq-cat-001",
    "title": "新手養貓準備清單",
    "content": "第一次養貓建議先準備貓砂盆與貓砂、飼料與水碗、貓抓板、外出籠……",
    "source": "（範例）某縣市動物保護處〈認養須知〉",
    "url": "https://example.com/…",
    "tags": ["貓", "新手", "準備"]
  }
]
```

- `id` 唯一，格式 `faq-<主題>-<三位數>`；`content` 每筆最多 500 字；`source` 必填（出處名稱），`url` 有就填。
- 不含任何個資；醫療內容只寫「建議就醫」，不寫診斷或用藥。
- 每筆的 `source` 要經 PM／AI 審核。
