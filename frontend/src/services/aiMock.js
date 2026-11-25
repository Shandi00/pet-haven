// 本期新增 API 的假資料，格式依 docs/api/新增API契約.md。
// 後端 T12、T13 完成前，前端用 shouldUseMockData() 切換到這裡開發；契約變更時同步修改。
// 回傳值模擬 axios 回應（{ data: { success, data } }），與 services/api.js 用法一致。

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const ok = (data) => ({ data: { success: true, data } });

const ACTIVITY_LABEL = { low: '低', moderate: '中', high: '高' };
const SPECIES_LABEL = { dog: '狗', cat: '貓' };

const pets = [
  { _id: 'mock-pet-1', name: '小黑', species: 'dog', breed: '米克斯', age: { value: 2, unit: 'years' }, ageCategory: 'adult', size: 'medium', activityLevel: 'high', photo: '' },
  { _id: 'mock-pet-2', name: '奶茶', species: 'cat', breed: '橘貓', age: { value: 8, unit: 'months' }, ageCategory: 'young', size: 'small', activityLevel: 'moderate', photo: '' },
  { _id: 'mock-pet-3', name: '豆豆', species: 'dog', breed: '柴犬', age: { value: 4, unit: 'years' }, ageCategory: 'adult', size: 'medium', activityLevel: 'moderate', photo: '' },
  { _id: 'mock-pet-4', name: '雪球', species: 'cat', breed: '米克斯', age: { value: 6, unit: 'years' }, ageCategory: 'adult', size: 'small', activityLevel: 'low', photo: '' },
];

let disliked = []; // 最新的在前，與契約 avoided 的順序相同

const ageText = ({ value, unit }) => `${value} ${unit === 'months' ? '個月' : '歲'}`;

const toItem = (pet, i) => ({
  pet,
  score: 92 - i * 7,
  matchLevel: i === 0 ? 'perfect' : 'excellent',
  reason: {
    summary: `${pet.name}的活動量${ACTIVITY_LABEL[pet.activityLevel]}，和你填寫的作息相符。`,
    highlights: [`活動量：${ACTIVITY_LABEL[pet.activityLevel]}`, `年齡：${ageText(pet.age)}`],
    cautions: pet.species === 'dog' ? ['住公寓需留意吠叫'] : [],
    source: i === 2 ? 'rule' : 'ai', // 第 3 筆示範 LLM 失敗時的規則理由
  },
});

const avoided = () =>
  disliked.map((petId) => {
    const pet = pets.find((p) => p._id === petId);
    return {
      petId,
      name: pet ? pet.name : '',
      note: pet
        ? `已避開：${pet.name}（${SPECIES_LABEL[pet.species]}，活動量${ACTIVITY_LABEL[pet.activityLevel]}），並降低相似動物的排序`
        : '已避開這隻動物',
    };
  });

const top3 = () => pets.filter((p) => !disliked.includes(p._id)).slice(0, 3).map(toItem);
const top3Data = () => ({ items: top3(), avoided: avoided(), generatedAt: new Date().toISOString() });

export const aiMock = {
  saveGameResult: async (data) => {
    await delay(300);
    return ok({ gameProfile: { ...data, completedAt: new Date().toISOString() } });
  },

  getTop3: async () => {
    await delay(500);
    return ok(top3Data());
  },

  sendFeedback: async (petId, verdict) => {
    await delay(400);
    if (verdict === 'like') return ok({ recorded: true });
    disliked = [petId, ...disliked.filter((id) => id !== petId)];
    return ok(top3Data());
  },

  resetFeedback: async () => {
    const cleared = disliked.length;
    disliked = [];
    return ok({ cleared });
  },

  chat: async (message) => {
    await delay(800);
    // 醫療問題：後端不呼叫 LLM，source 為 rule（契約 §4）
    if (/生病|發燒|嘔吐|拉肚子|腹瀉|咳嗽|受傷|流血|藥|症狀/.test(message)) {
      return ok({
        reply: '這可能和健康狀況有關，建議盡快帶牠去看獸醫。',
        sources: [],
        actions: [{ label: '看推薦動物', to: '/recommendations' }],
        refused: true,
        source: 'rule',
      });
    }
    return ok({
      reply: '建議先準備：貓砂盆與貓砂、飼料與水碗、貓抓板、外出籠。想知道哪隻貓適合你嗎？',
      sources: [{ title: '新手養貓準備清單', ref: 'faq-cat-001' }],
      actions: [
        { label: '去玩配對遊戲', to: '/match-game' },
        { label: '看推薦動物', to: '/recommendations' },
      ],
      refused: false,
      source: 'ai',
    });
  },
};
