import { safeRedirect } from './safeRedirect';

test('站內路徑照原樣使用', () => {
  expect(safeRedirect('/adopt/123')).toBe('/adopt/123');
  expect(safeRedirect('/messages/abc?tab=1')).toBe('/messages/abc?tab=1');
});

test('外站、協定相對網址與奇怪的值一律不採用', () => {
  // eslint-disable-next-line no-script-url -- 測試資料，確認這種值會被擋下
  ['https://evil.example', '//evil.example', '/\\evil.example', 'javascript:alert(1)', 'adopt/1', '/a\nb', '', null]
    .forEach((value) => expect(safeRedirect(value)).toBeNull());
});
