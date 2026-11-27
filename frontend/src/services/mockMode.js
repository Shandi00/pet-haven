// 假資料開關：設定 REACT_APP_USE_MOCK=true，或在瀏覽器把 localStorage 的 useMockData 設為 'true'。
// 只有 aiService.js（配對遊戲、推薦、聊天）會用到；假資料在 aiMock.js。
export const shouldUseMockData = () =>
  import.meta.env.REACT_APP_USE_MOCK === 'true' || window.localStorage.getItem('useMockData') === 'true';
