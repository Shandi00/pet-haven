// 本期新增 API 的統一入口：依假資料開關決定呼叫 aiMock.js 或真的後端。
// 介面見 docs/superpowers/plans/2026-11-25-前端組員任務-T09-T10-T11-T15.md Task 4。
// 目前只有 saveGameResult（T10）；getTop3、sendFeedback、resetFeedback、chat 由 Task 4 加入。
import { matchingAPI } from './api';
import { aiMock } from './aiMock';
import { shouldUseMockData } from './mockMode';

// 每次呼叫時才檢查開關，在瀏覽器切換 localStorage 的 useMockData 後重新整理即可生效
export const aiService = {
  saveGameResult: (data) => (shouldUseMockData() ? aiMock : matchingAPI).saveGameResult(data),
};
