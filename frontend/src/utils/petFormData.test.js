import { appendGoodWith } from './petFormData';

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
