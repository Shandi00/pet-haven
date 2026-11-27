import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { act, render, screen, within, fireEvent } from '@testing-library/react';
import MatchGamePage, { ADVANCE_MS, MIN_ANALYZE_MS } from './MatchGamePage';
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

// start：從推薦頁或「再玩一次」進來時跳過開場，直接第 1 題
const renderPage = ({ start = true } = {}) =>
  render(
    <MemoryRouter
      initialEntries={[{ pathname: '/match-game', state: start ? { start: true } : null }]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <MatchGamePage />
    </MemoryRouter>
  );

const optionButtons = () => within(screen.getByRole('group')).getAllByRole('button');

// 選完會先停 ADVANCE_MS 顯示打勾與小狗的回應，再換下一題
const pickOption = (index) => {
  fireEvent.click(optionButtons()[index]);
  act(() => {
    vi.advanceTimersByTime(ADVANCE_MS);
  });
};
const answerAll = () => {
  for (let i = 0; i < 8; i += 1) pickOption(0);
};
// 等存檔完成與「比對中」畫面結束
const finishSaving = () => act(() => vi.advanceTimersByTimeAsync(MIN_ANALYZE_MS + 100));

beforeEach(() => {
  vi.useFakeTimers();
  matchingAPI.getProfile.mockResolvedValue({ data: { success: true, data: {} } });
  matchingAPI.updateLifestyleProfile.mockImplementation(ok);
  matchingAPI.updateExperienceProfile.mockImplementation(ok);
  matchingAPI.updateEnvironmentProfile.mockImplementation(ok);
  aiService.saveGameResult.mockImplementation(ok);
});

afterEach(() => {
  vi.useRealTimers();
});

test('直接進遊戲頁時先看到開場與三種毛孩類型，按「開始遊戲」才出第 1 題', () => {
  renderPage({ start: false });
  expect(screen.getByText('戶外冒險型')).toBeInTheDocument();
  expect(screen.getByText('隨和陪伴型')).toBeInTheDocument();
  expect(screen.getByText('居家宅宅型')).toBeInTheDocument();
  expect(screen.queryByRole('group')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: '開始遊戲' }));
  expect(screen.getByText('第 1 題／共 8 題')).toBeInTheDocument();
});

test('答完 8 題後先顯示比對中，再依序寫入三份配對檔案、保存遊戲結果，並顯示毛孩類型', async () => {
  renderPage();
  for (let i = 1; i <= 8; i += 1) {
    expect(screen.getByText(`第 ${i} 題／共 8 題`)).toBeInTheDocument();
    pickOption(0);
  }
  expect(screen.getByRole('status')).toHaveTextContent('正在比對你的答案');

  await finishSaving();
  expect(screen.getByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
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

test('選了之後先打勾並顯示小狗的回應，停一下才換下一題', () => {
  renderPage();
  fireEvent.click(optionButtons()[0]);

  expect(optionButtons()[0]).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByText('活力滿點！會優先找活動量高、愛出門的毛孩。')).toBeInTheDocument();
  expect(screen.getByText('第 1 題／共 8 題')).toBeInTheDocument();

  act(() => {
    vi.advanceTimersByTime(ADVANCE_MS);
  });
  expect(screen.getByText('第 2 題／共 8 題')).toBeInTheDocument();
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
  answerAll();
  await finishSaving();
  expect(screen.getByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();

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
  answerAll();
  await finishSaving();

  expect(screen.getByRole('alert')).toHaveTextContent('連線失敗，請稍後再試');
  expect(matchingAPI.updateLifestyleProfile).not.toHaveBeenCalled();
  expect(matchingAPI.updateExperienceProfile).not.toHaveBeenCalled();
  expect(matchingAPI.updateEnvironmentProfile).not.toHaveBeenCalled();
  expect(aiService.saveGameResult).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  await finishSaving();
  expect(screen.getByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
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

test('連點不會跳題也不會改答案：換題前的點擊一律忽略', () => {
  renderPage();
  fireEvent.click(optionButtons()[0]); // q1 選 A
  fireEvent.click(optionButtons()[0]); // 連點第二下
  fireEvent.click(optionButtons()[1]); // 換題前改點 B，也要忽略
  act(() => {
    vi.advanceTimersByTime(ADVANCE_MS);
  });

  expect(screen.getByText('第 2 題／共 8 題')).toBeInTheDocument();
  expect(optionButtons().every((b) => b.getAttribute('aria-pressed') === 'false')).toBe(true);

  fireEvent.click(screen.getByRole('button', { name: '上一題' }));
  expect(optionButtons()[0]).toHaveAttribute('aria-pressed', 'true');
  expect(optionButtons()[1]).toHaveAttribute('aria-pressed', 'false');
});

test('儲存失敗時顯示後端訊息，按重試不必重玩就能完成', async () => {
  matchingAPI.updateLifestyleProfile.mockImplementationOnce(() =>
    Promise.reject({ response: { data: { success: false, message: '更新失敗：資料格式錯誤' } } })
  );
  renderPage();
  answerAll();
  await finishSaving();

  expect(screen.getByRole('alert')).toHaveTextContent('更新失敗：資料格式錯誤');
  expect(aiService.saveGameResult).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  await finishSaving();
  expect(screen.getByRole('heading', { name: '戶外冒險型' })).toBeInTheDocument();
  expect(aiService.saveGameResult).toHaveBeenCalledTimes(1);
});
