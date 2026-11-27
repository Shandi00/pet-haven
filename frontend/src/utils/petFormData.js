// 建檔表單「適合有小孩的家庭／適合與其他寵物相處」轉成送給後端的欄位（T09）。
// 適合送 'true'、不適合送 'false'；不確定（null）就不送，後端存成 null（未填）。
// 不適合（false）會讓 Top 3 把這隻動物從有小孩或有其他寵物的認養者的推薦中排除
// （docs/api/新增API契約.md §0 硬條件 3、4），不確定則不排除。
// 編輯時傳 clearUnknown：不確定改送空字串，後端會把舊的適合／不適合清回 null。
export const appendGoodWith = (formData, goodWith = {}, { clearUnknown = false } = {}) => {
  ['children', 'otherPets'].forEach((key) => {
    const value = goodWith?.[key];
    if (typeof value === 'boolean') {
      formData.append(`personality[goodWith][${key}]`, String(value));
    } else if (clearUnknown) {
      formData.append(`personality[goodWith][${key}]`, '');
    }
  });
};

// 寵物照片限制：格式與每張大小和後端 app/core/uploads.py 一致；每隻最多 5 張沿用刊登頁原本的規則
export const PHOTO_MAX_COUNT = 5;
export const PHOTO_MAX_MB = 5;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
export const PHOTO_ACCEPT = PHOTO_TYPES.join(',');
export const PHOTO_HINT = `JPG、PNG、GIF 或 WEBP，每張最多 ${PHOTO_MAX_MB}MB，最多 ${PHOTO_MAX_COUNT} 張`;

// 選了檔案之後先在前端檢查，不合格的直接說原因，不要等送出後才失敗；current 是已經有的張數
export const pickPhotos = (files, current = 0) => {
  const errors = [];
  const ok = [];
  files.forEach((f) => {
    if (!PHOTO_TYPES.includes(f.type)) errors.push(`「${f.name}」不是 JPG、PNG、GIF 或 WEBP 圖片`);
    else if (f.size > PHOTO_MAX_MB * 1024 * 1024) errors.push(`「${f.name}」超過 ${PHOTO_MAX_MB}MB，請壓縮後再上傳`);
    else ok.push(f);
  });
  const room = Math.max(PHOTO_MAX_COUNT - current, 0);
  if (ok.length > room) errors.push(`每隻動物最多 ${PHOTO_MAX_COUNT} 張照片，已略過 ${ok.length - room} 張`);
  return { photos: ok.slice(0, room), errors };
};

// 「相處」下拉選單的選項值與表單狀態互換：不確定 = null
export const GOOD_WITH_VALUE = { null: '', true: 'true', false: 'false' };
export const GOOD_WITH_STATE = { '': null, true: true, false: false };
export const GOOD_WITH_FIELDS = [
  { key: 'children', id: 'goodWithChildren', label: '適合有小孩的家庭' },
  { key: 'otherPets', id: 'goodWithOtherPets', label: '適合與其他寵物相處' },
];
