// 登入後的 ?redirect= 只接受站內路徑：要以單一 / 開頭，不能是 //evil.com 或 /\evil.com 這種會被瀏覽器當成外站的寫法，
// 也不能夾帶換行等控制字元
export const safeRedirect = (value) => {
  if (typeof value !== 'string' || !/^\/(?![/\\])/.test(value)) return null;
  return [...value].some((ch) => ch.charCodeAt(0) < 32) ? null : value;
};
