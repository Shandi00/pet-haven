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

// 「相處」下拉選單的選項值與表單狀態互換：不確定 = null
export const GOOD_WITH_VALUE = { null: '', true: 'true', false: 'false' };
export const GOOD_WITH_STATE = { '': null, true: true, false: false };
export const GOOD_WITH_FIELDS = [
  { key: 'children', id: 'goodWithChildren', label: '適合有小孩的家庭' },
  { key: 'otherPets', id: 'goodWithOtherPets', label: '適合與其他寵物相處' },
];
