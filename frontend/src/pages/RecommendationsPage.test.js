import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import RecommendationsPage from './RecommendationsPage';
import { aiService } from '../services/aiService';

jest.mock('react-hot-toast', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('../services/api', () => ({ matchingAPI: {}, aiAPI: {} }));
jest.mock('../services/aiService', () => ({
  ...jest.requireActual('../services/aiService'),
  aiService: { getTop3: jest.fn(), sendFeedback: jest.fn(), resetFeedback: jest.fn() },
}));

const pet = (id, name) => ({ _id: id, name, species: 'dog', breed: '米克斯', age: { value: 2, unit: 'years' }, size: 'medium', activityLevel: 'high', photo: '' });
const item = (id, name) => ({ pet: pet(id, name), score: 80, matchLevel: 'excellent', reason: { summary: `${name}的理由`, highlights: [], cautions: [], source: 'ai' } });
const top3 = (items, avoided = []) => ({ data: { success: true, data: { items, avoided, generatedAt: '2026-12-01T08:00:00.000Z' } } });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/recommendations']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/pets/:id" element={<div>動物詳情頁</div>} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => jest.clearAllMocks());

test('按「不適合」用回應直接換掉卡片並顯示「已避開」，送出期間按鈕停用、不會送兩次', async () => {
  aiService.getTop3.mockResolvedValue(top3([item('a', '小黑'), item('b', '豆豆'), item('c', '奶茶')]));
  let resolve;
  aiService.sendFeedback.mockReturnValue(new Promise((r) => { resolve = r; }));
  renderPage();

  const dislike = await screen.findByRole('button', { name: '小黑 不適合' });
  fireEvent.click(dislike);
  fireEvent.click(dislike); // 連點第二下
  expect(screen.getByRole('button', { name: '豆豆 適合' })).toBeDisabled();
  expect(aiService.sendFeedback).toHaveBeenCalledTimes(1);
  expect(aiService.sendFeedback).toHaveBeenCalledWith('a', 'dislike');

  resolve(top3([item('b', '豆豆'), item('c', '奶茶'), item('d', '雪球')],
    [{ petId: 'a', name: '小黑', note: '已避開：小黑（狗，活動量高），並降低相似動物的排序' }]));
  expect(await screen.findByRole('heading', { name: '雪球' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: '小黑' })).not.toBeInTheDocument();
  expect(screen.getByText('已避開：小黑（狗，活動量高），並降低相似動物的排序')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '豆豆 適合' })).toBeEnabled();
  expect(aiService.getTop3).toHaveBeenCalledTimes(1); // 沒有重新讀取整頁
});

test('沒有任何推薦時顯示空狀態，「重新開始」會清除回饋並重新讀取', async () => {
  aiService.getTop3.mockResolvedValueOnce(top3([], [{ petId: 'a', name: '小黑', note: '已避開：小黑' }]))
    .mockResolvedValueOnce(top3([item('a', '小黑')]));
  aiService.resetFeedback.mockResolvedValue({ data: { success: true, data: { cleared: 1 } } });
  renderPage();

  expect(await screen.findByText('目前沒有符合條件的毛孩')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '重新開始' }));
  expect(await screen.findByRole('heading', { name: '小黑' })).toBeInTheDocument();
  expect(aiService.resetFeedback).toHaveBeenCalledTimes(1);
});

test('按「適合」記錄後前往動物詳情頁', async () => {
  aiService.getTop3.mockResolvedValue(top3([item('a', '小黑')]));
  aiService.sendFeedback.mockResolvedValue({ data: { success: true, data: { recorded: true } } });
  renderPage();

  fireEvent.click(await screen.findByRole('button', { name: '小黑 適合' }));
  expect(await screen.findByText('動物詳情頁')).toBeInTheDocument();
  expect(aiService.sendFeedback).toHaveBeenCalledWith('a', 'like');
});

test('讀取失敗時顯示後端訊息，沒有訊息時顯示連線失敗，可以重試', async () => {
  aiService.getTop3.mockRejectedValueOnce({ response: { data: { success: false, message: '呼叫太頻繁，請稍後再試' } } })
    .mockRejectedValueOnce(new Error('Network Error'))
    .mockResolvedValueOnce(top3([item('a', '小黑')]));
  renderPage();

  expect(await screen.findByRole('alert')).toHaveTextContent('呼叫太頻繁，請稍後再試');
  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('連線失敗，請稍後再試'));
  fireEvent.click(screen.getByRole('button', { name: '重試' }));
  expect(await screen.findByRole('heading', { name: '小黑' })).toBeInTheDocument();
});
