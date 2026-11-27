import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider, setLogger } from 'react-query';
import { render, screen, fireEvent } from '@testing-library/react';
import MatchingProfileTab from './MatchingProfileTab';
import { matchingAPI } from '../services/api';

vi.mock('../services/api', () => ({
  matchingAPI: {
    getProfile: vi.fn(),
    updateLifestyleProfile: vi.fn(),
    updateExperienceProfile: vi.fn(),
    updateEnvironmentProfile: vi.fn(),
  },
}));

const baseProfile = {
  recommendationProfile: {},
  lifestyleProfile: { activityLevel: 'high', availableTime: 'extensive', housingType: 'apartment' },
  experienceProfile: {},
  environmentProfile: {},
};

const respondWith = (data) => matchingAPI.getProfile.mockResolvedValue({ data: { success: true, data } });

const renderTab = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<MatchingProfileTab />} />
          <Route path="/match-game" element={<div>配對小遊戲頁</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );

const gameProfileWith = (petType) => ({
  ...baseProfile,
  gameProfile: { answers: [], petType, completedAt: '2026-12-01T08:00:00.000Z' },
});

test('有 gameProfile 時顯示毛孩類型卡片，名稱與說明取自 petTypes，下方是「再玩一次」', async () => {
  // API 的說明故意不同，確認畫面用的是 matchGameQuestions.js 的 petTypes
  respondWith(gameProfileWith({ code: 'couch-buddy', label: '居家宅宅型', description: 'API 的舊說明' }));
  renderTab();

  const button = await screen.findByRole('button', { name: '再玩一次' });
  const heading = screen.getByRole('heading', { name: '居家宅宅型' });
  expect(screen.getByText('適合安靜、喜歡待在家陪你的毛孩')).toBeInTheDocument();
  expect(screen.queryByText('API 的舊說明')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '去玩配對遊戲' })).not.toBeInTheDocument();
  // 按鈕在卡片下方（DOM 順序在後）
  expect(heading.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test('毛孩類型的 code 對應不到時，顯示 API 回傳的名稱與說明', async () => {
  respondWith(gameProfileWith({ code: 'unknown-buddy', label: '神秘型', description: '題目改版前的類型' }));
  renderTab();

  expect(await screen.findByRole('heading', { name: '神秘型' })).toBeInTheDocument();
  expect(screen.getByText('題目改版前的類型')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '再玩一次' })).toBeInTheDocument();
});

test.each([
  ['gameProfile 是 null', { ...baseProfile, gameProfile: null }],
  ['回應沒有 gameProfile 欄位（後端計畫 Task 4 完成前）', baseProfile],
])('%s 時當成沒玩過：沒有毛孩類型，按鈕是「去玩配對遊戲」', async (_, data) => {
  respondWith(data);
  renderTab();

  expect(await screen.findByRole('button', { name: '去玩配對遊戲' })).toBeInTheDocument();
  expect(screen.queryByText('你的毛孩類型')).not.toBeInTheDocument();
  expect(screen.queryByRole('heading', { level: 2, name: /型$/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '再玩一次' })).not.toBeInTheDocument();
});

test('點遊戲按鈕前往 /match-game', async () => {
  respondWith(baseProfile);
  renderTab();

  fireEvent.click(await screen.findByRole('button', { name: '去玩配對遊戲' }));
  expect(screen.getByText('配對小遊戲頁')).toBeInTheDocument();
});

test('配對檔案表單預設收起，按「手動修改配對檔案」展開並帶入既有的資料', async () => {
  respondWith(baseProfile);
  renderTab();

  const toggle = await screen.findByRole('button', { name: '手動修改配對檔案' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByDisplayValue('高 - 每天需要大量運動')).not.toBeInTheDocument();

  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('想改其中一項，不用重玩遊戲，直接在這裡修改')).toBeInTheDocument();
  expect(screen.getByDisplayValue('高 - 每天需要大量運動')).toBeInTheDocument();
});

test('讀取失敗時顯示後端的訊息', async () => {
  setLogger({ log: () => {}, warn: () => {}, error: () => {} }); // react-query 會把錯誤印到 console
  matchingAPI.getProfile.mockRejectedValue({ response: { data: { success: false, message: '找不到使用者' } } });
  renderTab();

  expect(await screen.findByRole('alert')).toHaveTextContent('找不到使用者');
  setLogger(console);
});
