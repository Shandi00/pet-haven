// 使用者的顯示名稱：有姓名用姓名，沒有就用 name 或帳號，避免畫面出現 undefined
export const displayName = (u) =>
  [u?.firstName, u?.lastName].filter(Boolean).join(' ') || u?.name || u?.username || '使用者';
