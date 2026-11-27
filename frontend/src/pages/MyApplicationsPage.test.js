import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import MyApplicationsPage from './MyApplicationsPage';

jest.mock('react-hot-toast', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('framer-motion', () => ({ motion: { div: ({ children, initial, animate, ...rest }) => <div {...rest}>{children}</div> } }));
// ApplicationDetailModal 會連後端；這裡只測列表、篩選與取消
jest.mock('../components/ApplicationDetailModal', () => () => null);

const application = (status) => ({ _id: `app-${status}`, status, pet: { _id: 'p1', name: `小白-${status}` } });

const renderPage = (applications) => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ applications }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><MyApplicationsPage /></MemoryRouter>
    </QueryClientProvider>
  );
};

const listUrls = () => global.fetch.mock.calls.map(([url]) => url).filter((u) => u.includes('my-applications'));

describe('MyApplicationsPage 狀態篩選', () => {
  test('點狀態分頁會依狀態向後端查詢，回到第 1 頁', async () => {
    renderPage([application('pending')]);
    await screen.findByText('小白-pending');
    expect(listUrls()[0]).not.toContain('status=');
    fireEvent.click(screen.getByRole('button', { name: '已通過' }));
    await waitFor(() => expect(listUrls().at(-1)).toContain('page=1&limit=10&status=approved'));
    expect(screen.getByRole('button', { name: '已通過' })).toHaveAttribute('aria-pressed', 'true');
  });

  test('篩選後沒有資料時說明是哪個狀態，並可回到全部', async () => {
    renderPage([]);
    expect(await screen.findByText('還沒有認養申請')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '已拒絕' }));
    expect(await screen.findByText('沒有「已拒絕」的申請')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '看全部申請' }));
    expect(await screen.findByText('還沒有認養申請')).toBeInTheDocument();
  });
});

describe('MyApplicationsPage 取消申請', () => {
  const cancelCalls = () => global.fetch.mock.calls.filter(([url]) => url.includes('/cancel'));

  test('按「取消申請」先跳確認視窗，按「先不要」不會取消', async () => {
    renderPage([application('pending')]);
    fireEvent.click(await screen.findByRole('button', { name: '取消申請' }));
    expect(screen.getByRole('dialog', { name: '確定要取消申請？' })).toHaveTextContent('小白-pending');
    fireEvent.click(screen.getByRole('button', { name: '先不要' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(cancelCalls()).toHaveLength(0);
  });

  test('按「確定取消」才呼叫取消 API，成功後關閉視窗', async () => {
    renderPage([application('pending')]);
    fireEvent.click(await screen.findByRole('button', { name: '取消申請' }));
    fireEvent.click(screen.getByRole('button', { name: '確定取消' }));
    await waitFor(() => expect(cancelCalls()).toHaveLength(1));
    expect(cancelCalls()[0][0]).toContain('/api/adoptions/app-pending/cancel');
    expect(cancelCalls()[0][1].method).toBe('PUT');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
