// 配對小遊戲的 8 題題目（T05 定案）
// 對照表：docs/features/配對遊戲題目對照表.md
// effects 的欄位名稱與英文值照 docs/api/新增API契約.md §1，不可自行更改；
// 題目有異動時，對照表、本檔、utils/matchGame.test.js 與選項的圖示和回應（matchGameDisplay.js）要一起更新。

export const petTypes = [
  { code: 'outdoor-buddy', label: '戶外冒險型', description: '適合活動量高、喜歡出門散步和玩耍的毛孩' },
  { code: 'balanced-buddy', label: '隨和陪伴型', description: '適合個性穩定、能配合家人作息的毛孩' },
  { code: 'couch-buddy', label: '居家宅宅型', description: '適合安靜、喜歡待在家陪你的毛孩' },
];

// 總分相同時，排在前面的類型優先
export const tieBreakOrder = ['balanced-buddy', 'outdoor-buddy', 'couch-buddy'];

export const questions = [
  {
    id: 'q1',
    question: '週末早上你通常在做什麼？',
    options: [
      { id: 'A', label: '出門爬山或運動', effects: { lifestyle: { activityLevel: 'high' } }, typeScore: { 'outdoor-buddy': 2 } },
      { id: 'B', label: '在家追劇放鬆', effects: { lifestyle: { activityLevel: 'low' } }, typeScore: { 'couch-buddy': 2 } },
      { id: 'C', label: '看心情', effects: { lifestyle: { activityLevel: 'medium' } }, typeScore: { 'balanced-buddy': 2 } },
    ],
  },
  {
    id: 'q2',
    question: '下班或下課後，每天能陪毛孩多久？',
    options: [
      { id: 'A', label: '兩小時以上', effects: { lifestyle: { availableTime: 'extensive' } }, typeScore: { 'outdoor-buddy': 1 } },
      { id: 'B', label: '一小時左右', effects: { lifestyle: { availableTime: 'moderate' } }, typeScore: { 'balanced-buddy': 1 } },
      { id: 'C', label: '很少，常常很晚回家', effects: { lifestyle: { availableTime: 'minimal' } }, typeScore: { 'couch-buddy': 1 } },
    ],
  },
  {
    id: 'q3',
    question: '你現在住在哪裡？',
    options: [
      { id: 'A', label: '有院子的透天', effects: { lifestyle: { housingType: 'house-with-yard' } }, typeScore: { 'outdoor-buddy': 1 } },
      { id: 'B', label: '沒院子的透天', effects: { lifestyle: { housingType: 'house-no-yard' } }, typeScore: { 'balanced-buddy': 1 } },
      { id: 'C', label: '公寓、大樓或套房', effects: { lifestyle: { housingType: 'apartment' } }, typeScore: { 'couch-buddy': 1 } },
    ],
  },
  {
    id: 'q4',
    question: '你養過寵物嗎？',
    options: [
      { id: 'A', label: '養過好幾隻', effects: { experience: { petOwnershipExperience: 'experienced' } }, typeScore: { 'outdoor-buddy': 1 } },
      { id: 'B', label: '養過一兩隻', effects: { experience: { petOwnershipExperience: 'intermediate' } }, typeScore: { 'balanced-buddy': 1 } },
      { id: 'C', label: '從來沒養過', effects: { experience: { petOwnershipExperience: 'none' } }, typeScore: { 'couch-buddy': 1 } },
    ],
  },
  {
    id: 'q5',
    question: '家裡有小孩嗎？',
    options: [
      { id: 'A', label: '有', effects: { environment: { hasChildren: true } }, typeScore: { 'balanced-buddy': 1 } },
      { id: 'B', label: '沒有', effects: { environment: { hasChildren: false } }, typeScore: {} },
    ],
  },
  {
    id: 'q6',
    question: '家裡還有其他寵物嗎？',
    options: [
      { id: 'A', label: '有', effects: { environment: { hasOtherPets: true } }, typeScore: { 'balanced-buddy': 1 } },
      { id: 'B', label: '沒有', effects: { environment: { hasOtherPets: false } }, typeScore: {} },
    ],
  },
  {
    id: 'q7',
    question: '住的地方需要特別安靜嗎？（例如鄰居會在意吵鬧聲）',
    options: [
      { id: 'A', label: '需要', effects: { environment: { noiseSensitive: true } }, typeScore: { 'couch-buddy': 1 } },
      { id: 'B', label: '還好', effects: { environment: { noiseSensitive: false } }, typeScore: {} },
    ],
  },
  {
    // 一定要明確問「對貓過敏」：選「會」時，Top 3 推薦會完全排除貓（契約 §0 硬條件 5）
    id: 'q8',
    question: '你或家人會對貓過敏嗎？',
    options: [
      { id: 'A', label: '會', effects: { environment: { hasAllergies: true } }, typeScore: {} },
      { id: 'B', label: '不會', effects: { environment: { hasAllergies: false } }, typeScore: {} },
    ],
  },
];
