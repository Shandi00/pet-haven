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
