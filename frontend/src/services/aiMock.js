// 本期新增 API 的假資料，格式依 docs/api/新增API契約.md。
// 後端 T12、T13 完成前，前端用 shouldUseMockData() 切換到這裡開發；契約變更時同步修改。
// 回傳值模擬 axios 回應（{ data: { success, data } }），與 services/api.js 用法一致。

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const ok = (data) => ({ data: { success: true, data } });

const pets = [
  { _id: 'mock-pet-1', name: '小黑', species: 'dog', breed: '米克斯', age: 2, size: 'medium', photo: '', activity: '高' },
  { _id: 'mock-pet-2', name: '奶茶', species: 'cat', breed: '橘貓', age: 1, size: 'small', photo: '', activity: '中' },
  { _id: 'mock-pet-3', name: '豆豆', species: 'dog', breed: '柴犬', age: 4, size: 'medium', photo: '', activity: '中' },
  { _id: 'mock-pet-4', name: '雪球', species: 'cat', breed: '米克斯', age: 6, size: 'small', photo: '', activity: '低' },
];

let disliked = [];

const toItem = ({ activity, ...pet }, i) => ({
  pet,
  score: 92 - i * 7,
  matchLevel: i === 0 ? 'excellent' : 'good',
  reason: {
    summary: `${pet.name}的活動量${activity}，和你填寫的作息相符。`,
    highlights: [`活動量：${activity}`, `年齡：${pet.age} 歲`],
    cautions: pet.species === 'dog' ? ['住公寓需留意吠叫'] : [],
    source: i === 2 ? 'rule' : 'ai', // 第 3 筆示範 LLM 失敗時的規則理由
  },
});

const top3 = () => pets.filter((p) => !disliked.includes(p._id)).slice(0, 3).map(toItem);

export const aiMock = {
  saveGameResult: async (data) => {
    await delay(300);
    return ok({ gameProfile: { ...data, completedAt: new Date().toISOString() } });
  },

  getTop3: async () => {
    await delay(500);
    return ok({ items: top3(), avoided: [], generatedAt: new Date().toISOString() });
  },

  sendFeedback: async (petId, verdict) => {
    await delay(400);
    if (verdict === 'like') return ok({ recorded: true });
    disliked = [...disliked, petId];
    const pet = pets.find((p) => p._id === petId);
    return ok({
      items: top3(),
      avoided: [{ petId, note: pet ? `已避開活動量${pet.activity}的${pet.species === 'dog' ? '狗' : '貓'}` : '已避開這隻動物' }],
      generatedAt: new Date().toISOString(),
    });
  },

  resetFeedback: async () => {
    const cleared = disliked.length;
    disliked = [];
    return ok({ cleared });
  },

  chat: async (message) => {
    await delay(800);
    if (/生病|發燒|嘔吐|拉肚子|藥/.test(message)) {
      return ok({ reply: '這可能和健康狀況有關，建議盡快帶牠去看獸醫。', sources: [], actions: [], refused: true, source: 'ai' });
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
