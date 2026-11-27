// 本期新增 API 的統一入口：依假資料開關決定呼叫 aiMock.js 或真的後端。
// 介面見 docs/superpowers/plans/2026-11-25-前端組員任務-T09-T10-T11-T15.md Task 4。
import { aiAPI, matchingAPI } from './api';
import { aiMock } from './aiMock';
import { shouldUseMockData } from './mockMode';

// 每次呼叫時才檢查開關，在瀏覽器切換 localStorage 的 useMockData 後重新整理即可生效
const matching = () => (shouldUseMockData() ? aiMock : matchingAPI);

export const aiService = {
  // 推薦頁用來判斷有沒有玩過配對遊戲（gameProfile 為 null 表示沒玩過）
  getProfile: () => matching().getProfile(),
  saveGameResult: (data) => matching().saveGameResult(data),
  getTop3: () => matching().getTop3(),
  sendFeedback: (petId, verdict) => matching().sendFeedback(petId, verdict),
  resetFeedback: () => matching().resetFeedback(),
  chat: (message, history) => (shouldUseMockData() ? aiMock : aiAPI).chat(message, history),
};

// 顯示用的錯誤訊息：後端的 message，沒有時（例如後端沒開）用通用訊息
export const errorMessage = (error) => error?.response?.data?.message || '連線失敗，請稍後再試';
