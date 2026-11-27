import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import MessagesPage from './MessagesPage';
import NotificationsPage from './NotificationsPage';

jest.mock('react-hot-toast', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

// 讀取失敗時要顯示錯誤，不能顯示成「沒有資料」（原本 API 失敗也顯示「還沒有任何對話」）
const renderPage = (Page) => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false, json: async () => ({}) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><Page /></MemoryRouter>
    </QueryClientProvider>
  );
};

test('對話列表讀取失敗時顯示錯誤', async () => {
  renderPage(MessagesPage);
  expect(await screen.findByRole('alert')).toHaveTextContent('對話載入失敗');
  expect(screen.queryByText('還沒有任何對話')).not.toBeInTheDocument();
});

test('通知讀取失敗時顯示錯誤並可重試', async () => {
  renderPage(NotificationsPage);
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('通知載入失敗');
  expect(screen.getByRole('button', { name: '重試' })).toBeInTheDocument();
  expect(screen.queryByText('目前還沒有任何通知')).not.toBeInTheDocument();
});
