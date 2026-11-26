import { petTypes, tieBreakOrder } from '../data/matchGameQuestions';

/**
 * 把小遊戲的答案轉成配對欄位與毛孩類型（T10）。
 * 規則見 docs/features/配對遊戲題目對照表.md。
 *
 * @param {Array} questions 題目，格式同 data/matchGameQuestions.js 的 questions
 * @param {Array<{ questionId: string, optionId: string }>} answers 每題選的選項
 * @returns {{ lifestyle: object, experience: object, environment: object, petType: { code, label, description } }}
 *   lifestyle／experience／environment 分別送給 matchingAPI 的三支既有 API；
 *   同一個欄位被多題影響時，以後面的題目為準。
 * @throws {Error} 有題目沒作答，或選了不存在的選項
 */
export function computeGameResult(questions, answers) {
  const chosen = new Map(answers.map((a) => [a.questionId, a.optionId]));
  const result = { lifestyle: {}, experience: {}, environment: {} };
  const scores = {};

  questions.forEach((q) => {
    const option = q.options.find((o) => o.id === chosen.get(q.id));
    if (!option) {
      throw new Error('尚未完成所有題目');
    }
    Object.entries(option.effects || {}).forEach(([group, fields]) => {
      Object.assign(result[group], fields);
    });
    Object.entries(option.typeScore || {}).forEach(([code, points]) => {
      scores[code] = (scores[code] || 0) + points;
    });
  });

  // 依 tieBreakOrder 比較，只有分數「嚴格較高」才換人，所以同分時排前面的類型勝出
  const bestCode = tieBreakOrder.reduce((best, code) =>
    (scores[code] || 0) > (scores[best] || 0) ? code : best
  );

  return { ...result, petType: petTypes.find((t) => t.code === bestCode) };
}
