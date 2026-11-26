// 建檔表單「適合有小孩的家庭／適合與其他寵物相處」轉成送給後端的欄位（T09）。
// 適合送 'true'、不適合送 'false'；不確定（null）就不送，後端存成 null（未填）。
// 不適合（false）會讓 Top 3 把這隻動物從有小孩或有其他寵物的認養者的推薦中排除
// （docs/api/新增API契約.md §0 硬條件 3、4），不確定則不排除。
export const appendGoodWith = (formData, goodWith = {}) => {
  ['children', 'otherPets'].forEach((key) => {
    if (typeof goodWith[key] === 'boolean') {
      formData.append(`personality[goodWith][${key}]`, String(goodWith[key]));
    }
  });
};
