import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, within, fireEvent } from '@testing-library/react';
import MatchGamePage from './MatchGamePage';
import { matchingAPI } from '../services/api';
import { aiService } from '../services/aiService';

jest.mock('../services/api', () => ({
  matchingAPI: {
    updateLifestyleProfile: jest.fn(),
    updateExperienceProfile: jest.fn(),
    updateEnvironmentProfile: jest.fn(),
  },
}));
jest.mock('../services/aiService', () => ({ aiService: { saveGameResult: jest.fn() } }));

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
  jest.restoreAllMocks();
});

beforeEach(() => {
  jest.clearAllMocks();
  now = 1000000;
  jest.spyOn(Date, 'now').mockImplementation(() => now);
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
