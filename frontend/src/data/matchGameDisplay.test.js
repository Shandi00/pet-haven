import { questions } from './matchGameQuestions';
import { displayFor, optionDisplay } from './matchGameDisplay';

// 題目檔和畫面檔是分開的，改題目時忘了補圖示或回應，這裡會失敗
test('每一題的每個選項都有圖示和回應', () => {
  for (const q of questions) {
    for (const o of q.options) {
      const display = optionDisplay[q.id]?.[o.id];
      expect(display, `${q.id} ${o.id}`).toBeDefined();
      expect(display.icon, `${q.id} ${o.id} 圖示`).toBeTruthy();
      expect(display.reaction, `${q.id} ${o.id} 回應`).not.toBe('');
    }
  }
});

test('畫面檔沒有題目檔不存在的題目或選項', () => {
  for (const [qid, opts] of Object.entries(optionDisplay)) {
    const q = questions.find((x) => x.id === qid);
    expect(q, qid).toBeDefined();
    for (const oid of Object.keys(opts)) expect(q.options.some((o) => o.id === oid), `${qid} ${oid}`).toBe(true);
  }
});

test('對應不到時退回預設圖示、沒有回應', () => {
  const fallback = displayFor('q99', 'Z');
  expect(fallback.icon).toBeTruthy();
  expect(fallback.reaction).toBe('');
});
