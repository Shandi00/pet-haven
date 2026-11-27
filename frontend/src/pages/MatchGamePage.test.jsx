import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, within, fireEvent } from '@testing-library/react';
import MatchGamePage from './MatchGamePage';
import { matchingAPI } from '../services/api';
import { aiService } from '../services/aiService';

vi.mock('../services/api', () => ({
  matchingAPI: {
    getProfile: vi.fn(),
    updateLifestyleProfile: vi.fn(),
    updateExperienceProfile: vi.fn(),
    updateEnvironmentProfile: vi.fn(),
  },
}));
vi.mock('../services/aiService', () => ({ aiService: { saveGameResult: vi.fn() } }));

const ok = () => Promise.resolve({ data: { success: true } });

const renderPage = () =>
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <MatchGamePage />
    </MemoryRouter>
  );

// 頁面用 Date.now() 判斷換題後的連點，測試用可控制的時鐘
let now;

const optionButtons = () => within(screen.getByRole('group')).getAllByRole('button');

// 等 waitMs 毫秒後，在目前這一題點第 index 個選項；預設等 1 秒，模擬一般作答速度
const pickOption = (index, waitMs = 1000) => {
  now += waitMs;
  fireEvent.click(optionButtons()[index]);
};

afterEach(() => {
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.clearAllMocks();
  now = 1000000;
  vi.spyOn(Date, 'now').mockImplementation(() => now);
  matchingAPI.getProfile.mockResolvedValue({ data: { success: true, data: {} } });
  matchingAPI.updateLifestyleProfile.mockImplementation(ok);
  matchingAPI.updateExperienceProfile.mockImplementation(ok);
  matchingAPI.updateEnvironmentProfile.mockImplementation(ok);
  aiService.saveGameResult.mockImplementation(ok);
});

test('答完 8 題後依序寫入三份配對檔案、保存遊戲結果，並顯示毛孩類型', async () => {
  renderPage();
  for (let i = 1; i <= 8; i += 1) {
    expect(screen.getByText(`第 ${i} 題／共 8 題`)).toBeInTheDocument();
    pickOption(0);
  }

  expect(await screen.findByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '看推薦' })).toBeInTheDocument();

  expect(matchingAPI.updateLifestyleProfile).toHaveBeenCalledWith({
    activityLevel: 'high', availableTime: 'extensive', housingType: 'house-with-yard',
  });
  expect(matchingAPI.updateExperienceProfile).toHaveBeenCalledWith({ petOwnershipExperience: 'experienced' });
  expect(matchingAPI.updateEnvironmentProfile).toHaveBeenCalledWith({
    hasChildren: true, hasOtherPets: true, noiseSensitive: true, hasAllergies: true,
  });
  const saved = aiService.saveGameResult.mock.calls[0][0];
  expect(saved.answers).toHaveLength(8);
  expect(saved.answers[0]).toEqual({ questionId: 'q1', optionId: 'A' });
  expect(saved.petType.code).toBe('outdoor-buddy');

  // 三支既有 API 要在 saveGameResult 之前呼叫
  const order = (fn) => fn.mock.invocationCallOrder[0];
  expect(order(matchingAPI.updateEnvironmentProfile)).toBeLessThan(order(aiService.saveGameResult));
});

test('玩完遊戲後，已經手動填過、遊戲沒問到的欄位還在', async () => {
  matchingAPI.getProfile.mockResolvedValue({
    data: {
      success: true,
      data: {
        lifestyleProfile: { activityLevel: 'low', availableTime: 'minimal', housingType: 'condo' },
        experienceProfile: {
          petOwnershipExperience: 'beginner',
          previousPets: [{ species: 'dog', yearsOwned: 3 }],
          trainingExperience: true,
        },
        environmentProfile: {
          hasChildren: false, childrenAges: ['4-6'],
          hasOtherPets: false, otherPets: [{ species: 'cat', temperament: '溫和' }],
          noiseSensitive: false, hasAllergies: false,
        },
      },
    },
  });
  renderPage();
  for (let i = 0; i < 8; i += 1) pickOption(0);
  await screen.findByRole('heading', { name: '戶外冒險型' });

  // 遊戲問到的欄位換成遊戲的答案，沒問到的欄位維持原值
  expect(matchingAPI.updateLifestyleProfile).toHaveBeenCalledWith(expect.objectContaining({
    activityLevel: 'high', availableTime: 'extensive', housingType: 'house-with-yard',
  }));
  expect(matchingAPI.updateExperienceProfile).toHaveBeenCalledWith(expect.objectContaining({
    petOwnershipExperience: 'experienced',
    previousPets: [{ species: 'dog', yearsOwned: 3 }],
    trainingExperience: true,
  }));
  expect(matchingAPI.updateEnvironmentProfile).toHaveBeenCalledWith(expect.objectContaining({
    hasChildren: true, hasOtherPets: true, noiseSensitive: true, hasAllergies: true,
    childrenAges: ['4-6'],
    otherPets: [{ species: 'cat', temperament: '溫和' }],
  }));
});

test.each([
  ['讀取失敗', () => Promise.reject(new Error('Network Error'))],
  ['回應沒有資料', () => Promise.resolve({ data: { success: true } })],
])('存檔前讀取目前的配對檔案時%s，不存檔並顯示錯誤，重試成功後才寫入', async (_, firstRead) => {
  matchingAPI.getProfile.mockImplementationOnce(firstRead);
  renderPage();
  for (let i = 0; i < 8; i += 1) pickOption(0);

  expect(await screen.findByRole('alert')).toHaveTextContent('連線失敗，請稍後再試');
  expect(matchingAPI.updateLifestyleProfile).not.toHaveBeenCalled();
  expect(matchingAPI.updateExperienceProfile).not.toHaveBeenCalled();
  expect(matchingAPI.updateEnvironmentProfile).not.toHaveBeenCalled();
  expect(aiService.saveGameResult).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  expect(await screen.findByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
  expect(matchingAPI.getProfile).toHaveBeenCalledTimes(2);
  expect(matchingAPI.updateExperienceProfile).toHaveBeenCalledTimes(1);
});

test('回到上一題時，已選的選項標示 aria-pressed="true"', () => {
  renderPage();
  pickOption(1); // q1 選 B
  fireEvent.click(screen.getByRole('button', { name: '上一題' }));

  expect(screen.getByText('第 1 題／共 8 題')).toBeInTheDocument();
  const options = optionButtons();
  expect(options[1]).toHaveAttribute('aria-pressed', 'true');
  expect(options[0]).toHaveAttribute('aria-pressed', 'false');
});

test('連點兩下不會跳題：換題後短時間內的點擊會被忽略', () => {
  renderPage();
  pickOption(0); // q1 選 A，換到第 2 題
  pickOption(0, 150); // 150 毫秒後的第二下落在第 2 題的選項上，應該被忽略

  expect(screen.getByText('第 2 題／共 8 題')).toBeInTheDocument();
  expect(optionButtons().every((b) => b.getAttribute('aria-pressed') === 'false')).toBe(true);

  pickOption(0); // 過了鎖定時間就能正常作答
  expect(screen.getByText('第 3 題／共 8 題')).toBeInTheDocument();
});

test('儲存失敗時顯示後端訊息，按重試不必重玩就能完成', async () => {
  matchingAPI.updateLifestyleProfile.mockImplementationOnce(() =>
    Promise.reject({ response: { data: { success: false, message: '更新失敗：資料格式錯誤' } } })
  );
  renderPage();
  for (let i = 0; i < 8; i += 1) pickOption(0);

  expect(await screen.findByRole('alert')).toHaveTextContent('更新失敗：資料格式錯誤');
  expect(aiService.saveGameResult).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  expect(await screen.findByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
  expect(aiService.saveGameResult).toHaveBeenCalledTimes(1);
});

test('後端沒有回應時顯示「連線失敗，請稍後再試」', async () => {
  aiService.saveGameResult.mockImplementationOnce(() => Promise.reject(new Error('Network Error')));
  renderPage();
  for (let i = 0; i < 8; i += 1) pickOption(0);

  expect(await screen.findByRole('alert')).toHaveTextContent('連線失敗，請稍後再試');
});
