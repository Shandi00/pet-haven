import { appendGoodWith, pickPhotos } from './petFormData';

const file = (name, type, mb) => {
  const f = new File(['x'], name, { type });
  Object.defineProperty(f, 'size', { value: mb * 1024 * 1024 });
  return f;
};

test('照片超過 5MB 或格式不對會被擋下並說明原因', () => {
  const { photos, errors } = pickPhotos([
    file('ok.jpg', 'image/jpeg', 4.9), file('big.png', 'image/png', 5.1), file('doc.pdf', 'application/pdf', 1),
  ]);
  expect(photos.map((p) => p.name)).toEqual(['ok.jpg']);
  expect(errors).toEqual(['「big.png」超過 5MB，請壓縮後再上傳', '「doc.pdf」不是 JPG、PNG、GIF 或 WEBP 圖片']);
});

test('加上已有的照片最多 5 張，多的略過並提示', () => {
  const { photos, errors } = pickPhotos([1, 2, 3].map((i) => file(`${i}.webp`, 'image/webp', 1)), 3);
  expect(photos).toHaveLength(2);
  expect(errors).toEqual(['每隻動物最多 5 張照片，已略過 1 張']);
});

test('適合送 true、不適合送 false', () => {
  const fd = new FormData();
  appendGoodWith(fd, { children: true, otherPets: false, strangers: true });

  expect(fd.get('personality[goodWith][children]')).toBe('true');
  expect(fd.get('personality[goodWith][otherPets]')).toBe('false');
  expect(fd.has('personality[goodWith][strangers]')).toBe(false); // 表單沒有這一項
});

test('不確定（null）不送出，讓後端存成未填，不會被 Top 3 排除', () => {
  const fd = new FormData();
  appendGoodWith(fd, { children: null, otherPets: null });

  expect(fd.has('personality[goodWith][children]')).toBe(false);
  expect(fd.has('personality[goodWith][otherPets]')).toBe(false);
});

test('編輯時不確定送空字串，讓後端把舊值清回 null', () => {
  const fd = new FormData();
  appendGoodWith(fd, { children: null, otherPets: false }, { clearUnknown: true });

  expect(fd.get('personality[goodWith][children]')).toBe('');
  expect(fd.get('personality[goodWith][otherPets]')).toBe('false');
});

test('舊資料沒有 goodWith 也不會出錯', () => {
  const fd = new FormData();
  appendGoodWith(fd, undefined, { clearUnknown: true });

  expect(fd.get('personality[goodWith][children]')).toBe('');
});
