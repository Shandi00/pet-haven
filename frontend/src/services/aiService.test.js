import { aiService } from './aiService';
import { matchingAPI } from './api';

jest.mock('./api', () => ({ matchingAPI: { saveGameResult: jest.fn() } }));

const gameResult = {
  answers: [{ questionId: 'q1', optionId: 'A' }],
  petType: { code: 'outdoor-buddy', label: '戶外冒險型', description: '適合活動量高、喜歡出門散步和玩耍的毛孩' },
};

afterEach(() => {
  window.localStorage.removeItem('useMockData');
  jest.clearAllMocks();
});

test('假資料開關打開時，saveGameResult 改用 aiMock，不呼叫後端', async () => {
  window.localStorage.setItem('useMockData', 'true');
  const res = await aiService.saveGameResult(gameResult);

  expect(matchingAPI.saveGameResult).not.toHaveBeenCalled();
  expect(res.data.data.gameProfile).toMatchObject(gameResult);
  expect(res.data.data.gameProfile.completedAt).toBeTruthy();
});

test('假資料開關關閉時，saveGameResult 呼叫真的 API', async () => {
  matchingAPI.saveGameResult.mockResolvedValue({ data: { success: true } });
  await aiService.saveGameResult(gameResult);

  expect(matchingAPI.saveGameResult).toHaveBeenCalledWith(gameResult);
});
