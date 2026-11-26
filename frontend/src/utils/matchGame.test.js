import { computeGameResult } from './matchGame';
import { questions, petTypes } from '../data/matchGameQuestions';

// 用 8 個字母表示 q1 到 q8 的選項，例如 'CCCBBBAB'
// （q5 到 q8 只有 A、B 兩個選項，不能每題都選 C）
const answer = (letters) =>
  letters.split('').map((optionId, i) => ({ questionId: `q${i + 1}`, optionId }));

const typeOf = (letters) => computeGameResult(questions, answer(letters)).petType.code;

test('8 題選項寫入契約規定的欄位與英文值', () => {
  expect(questions).toHaveLength(8);

  expect(computeGameResult(questions, answer('AAAAAAAA'))).toMatchObject({
    lifestyle: { activityLevel: 'high', availableTime: 'extensive', housingType: 'house-with-yard' },
    experience: { petOwnershipExperience: 'experienced' },
    environment: { hasChildren: true, hasOtherPets: true, noiseSensitive: true, hasAllergies: true },
  });
  expect(computeGameResult(questions, answer('BBBBBBBB'))).toMatchObject({
    lifestyle: { activityLevel: 'low', availableTime: 'moderate', housingType: 'house-no-yard' },
    experience: { petOwnershipExperience: 'intermediate' },
    environment: { hasChildren: false, hasOtherPets: false, noiseSensitive: false, hasAllergies: false },
  });
  expect(computeGameResult(questions, answer('CCCCBBBB'))).toMatchObject({
    lifestyle: { activityLevel: 'medium', availableTime: 'minimal', housingType: 'apartment' },
    experience: { petOwnershipExperience: 'none' },
  });
});

test('毛孩類型取 typeScore 總分最高者', () => {
  expect(typeOf('AAAAAAAA')).toBe('outdoor-buddy'); // 戶外 5、隨和 2、宅宅 1
  expect(typeOf('BBBBBBBB')).toBe('balanced-buddy'); // 戶外 0、隨和 3、宅宅 2
  expect(typeOf('BCCCBBAB')).toBe('couch-buddy'); // 戶外 0、隨和 0、宅宅 6

  // petType 要帶完整的 code、label、description，給 saveGameResult 使用
  expect(petTypes).toContainEqual(computeGameResult(questions, answer('AAAAAAAA')).petType);
});

test('同分時依隨和 → 戶外 → 宅宅的順序決定', () => {
  expect(typeOf('CCCBBBAB')).toBe('balanced-buddy'); // 隨和 3、宅宅 3：隨和優先
  expect(typeOf('ABBCBBBB')).toBe('balanced-buddy'); // 戶外 2、隨和 2：隨和優先
  expect(typeOf('ACCABBAB')).toBe('outdoor-buddy'); // 戶外 3、宅宅 3：戶外優先
  expect(typeOf('ABCBBBAB')).toBe('balanced-buddy'); // 三種都是 2：隨和優先
});

test('同一個欄位被多題影響時，以後面的題目為準', () => {
  // 正式 8 題沒有兩題寫同一個欄位，這裡用自訂題目確認規則
  const overlapping = [
    { id: 'x1', question: '', options: [{ id: 'A', label: '', effects: { lifestyle: { activityLevel: 'high' } }, typeScore: {} }] },
    { id: 'x2', question: '', options: [{ id: 'A', label: '', effects: { lifestyle: { activityLevel: 'low' } }, typeScore: {} }] },
  ];
  const answers = [{ questionId: 'x1', optionId: 'A' }, { questionId: 'x2', optionId: 'A' }];
  expect(computeGameResult(overlapping, answers).lifestyle.activityLevel).toBe('low');
});

test('沒有答完所有題目或選了不存在的選項時丟出錯誤', () => {
  expect(() => computeGameResult(questions, answer('AAAAAAAA').slice(1))).toThrow('尚未完成所有題目');
  expect(() => computeGameResult(questions, answer('CCCCCCCC'))).toThrow('尚未完成所有題目'); // q5 沒有 C
});
