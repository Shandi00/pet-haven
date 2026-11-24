import { aiMock } from './aiMock';

// 確認假資料符合 docs/api/新增API契約.md 的重點行為
test('按不適合後，該動物不再出現在 Top 3，並說明避開了什麼', async () => {
  await aiMock.resetFeedback();
  const before = (await aiMock.getTop3()).data.data.items;
  expect(before).toHaveLength(3);

  const target = before[0].pet._id;
  const after = (await aiMock.sendFeedback(target, 'dislike')).data.data;
  expect(after.items.map((i) => i.pet._id)).not.toContain(target);
  expect(after.avoided[0].petId).toBe(target);

  await aiMock.resetFeedback();
});

test('醫療問題會拒答並提醒就醫', async () => {
  const res = (await aiMock.chat('我的貓一直嘔吐怎麼辦')).data.data;
  expect(res.refused).toBe(true);
  expect(res.sources).toEqual([]);
});
