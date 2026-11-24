# 新增 API 契約（草案）

- **對應任務**：04 API 契約與權限設計（後端主責確認後定稿）
- **使用者**：前端（T10、T15）、後端（T12、T13）、PM／AI（T13、T14）
- **狀態**：草案，由 PM／AI 於 2026-11-25 先行提供，讓前後端可以同時開工。欄位有異動時改這份文件，並同步更新前端假資料 `frontend/src/services/aiMock.js`。

既有 API 不在此列，請看 Swagger（`http://localhost:5000/api-docs`）。

## 共通規則

- 下列 API 都要登入：在 `Authorization: Bearer <JWT>` 帶上 token，沒帶回 401。
- 成功：`{ "success": true, "data": ... }`；失敗：`{ "success": false, "message": "給使用者看的繁中訊息" }`。
- `source` 欄位說明理由或回答的來源：`"ai"`＝LLM 產生；`"rule"`＝規則理由（LLM 逾時或失敗時的備援）；`"fallback"`＝聊天備援訊息。前端遇到 `rule`、`fallback` 要顯示提示，不能假裝是 AI 產生的。
- LLM 逾時上限暫定 8 秒，最終值由 T06 決定。逾時**不回錯誤**，改用備援內容並回 200。

| 狀態碼 | 情況 |
|---|---|
| 400 | 參數錯誤，例如 `verdict` 不是 `like` 或 `dislike` |
| 401 | 沒登入或 token 失效 |
| 404 | 找不到動物 |
| 429 | 呼叫太頻繁（速率限制） |

---

## 1. 儲存遊戲結果（T10）

`PUT /api/matching/profile/game`

小遊戲的 8 題答案經對照表（T05）轉換後，前端**先呼叫既有的三支 API** 寫入配對欄位，再呼叫這支 API 保存原始答案和毛孩類型：

| 既有 API | 遊戲要寫入的欄位與可用值 |
|---|---|
| `PUT /api/matching/profile/lifestyle` | `activityLevel`：`low`／`medium`／`high`；`availableTime`：`minimal`／`moderate`／`extensive`；`housingType`：`apartment`／`condo`／`townhouse`／`house-no-yard`／`house-with-yard` |
| `PUT /api/matching/profile/experience` | `petOwnershipExperience`：`none`／`beginner`／`intermediate`／`experienced` |
| `PUT /api/matching/profile/environment` | `hasChildren`、`hasOtherPets`、`noiseSensitive`、`hasAllergies`（布林值） |

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

回應：`{ "success": true, "data": { "gameProfile": { ...請求內容, "completedAt": "2026-12-01T08:00:00.000Z" } } }`

## 2. 取得 Top 3 推薦（T13）

`GET /api/matching/top3`

先依硬條件篩選（T06 定稿），再用既有計分排序，排除使用者按過「不適合」的動物，取前 3 名並附上理由。

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
          "age": 2,
          "size": "medium",
          "photo": "/uploads/pets/sample.jpg"
        },
        "score": 92,
        "matchLevel": "excellent",
        "reason": {
          "summary": "牠每天需要散步一小時，跟你週末喜歡戶外活動的習慣很合。",
          "highlights": ["活動量相符：你選擇高活動量，小黑活動量高", "你有養狗經驗"],
          "cautions": ["住公寓需留意吠叫，建議先了解社區規定"],
          "source": "ai"
        }
      }
    ],
    "avoided": [],
    "generatedAt": "2026-12-01T08:00:00.000Z"
  }
}
```

- `highlights`、`cautions` 只能引用真實欄位（見 AGENTS.md）。
- 符合條件的動物不足 3 隻時，`items` 可以少於 3 筆；沒有任何結果時回傳空陣列，前端顯示空狀態。

## 3. 回饋「適合／不適合」（T13、T15）

`POST /api/matching/feedback`

請求：`{ "petId": "65f0c0ffee0000000000a001", "verdict": "dislike" }`（`verdict`：`like` 或 `dislike`）

- `dislike`：寫入使用者的回饋紀錄，**直接回傳重排後的 Top 3**，前端不必再呼叫一次 `GET /top3`。
- `like`：只記錄，回傳 `{ "success": true, "data": { "recorded": true } }`；前端接著導向動物詳情或申請頁。

`dislike` 的回應：

```json
{
  "success": true,
  "data": {
    "items": ["…與 GET /top3 的 items 相同格式…"],
    "avoided": [
      { "petId": "65f0c0ffee0000000000a001", "note": "已避開活動量高的狗" }
    ],
    "generatedAt": "2026-12-01T08:01:00.000Z"
  }
}
```

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

- `history` 最多帶最近 10 則；後端不保存聊天內容。
- `message` 長度上限 500 字，超過回 400。

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

- 醫療或疾病問題：`refused: true`，`reply` 提醒就醫，`sources` 為空陣列。
- 知識庫查不到：`reply` 明確說不知道，不編造，`sources` 為空陣列。
- LLM 逾時：`source: "fallback"`，`reply` 為「小幫手暫時無法回答，請稍後再試」，`actions` 仍提供導覽按鈕。
- `actions[].to` 的前端路徑由 T05 的畫面設計決定，上面的值只是範例。

## 5. AI 推薦理由（T12，後端內部使用）

`POST /api/ai/explain` 由 `GET /top3` 在後端內部呼叫，前端不直接使用。輸入為一隻動物和使用者配對欄位（不含個資），輸出為上面 `reason` 的格式。若決定改成函式呼叫而非 HTTP 端點，後端可以自行調整，不影響前端。
