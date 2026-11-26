// 假資料開關：設定 REACT_APP_USE_MOCK=true，或在瀏覽器把 localStorage 的 useMockData 設為 'true'。
// 獨立成小模組，讓 aiService.js 等檔案不必載入 mockAPI.js 的整包假資料。
export const shouldUseMockData = () =>
  process.env.REACT_APP_USE_MOCK === 'true' || window.localStorage.getItem('useMockData') === 'true';
