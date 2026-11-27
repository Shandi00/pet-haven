import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import MyPetsApplicationsPage from './MyPetsApplicationsPage';
import { adoptionAPI } from '../services/api';

jest.mock('../services/auth', () => ({ useAuth: () => ({ user: { _id: 'shelter1', role: 'shelter' } }) }));
jest.mock('../services/api', () => ({ adoptionAPI: { completeAdoption: jest.fn() } }));
jest.mock('react-hot-toast', () => ({ __esModule: true, default: { success: jest.fn(), error: jest.fn() } }));

const app = (status) => ({
  _id: `app-${status}`, status, pet: { _id: 'p1', name: `小白-${status}` }, applicant: { _id: 'u1', username: 'adopter1' },
});

const renderPage = (applications, ok = true, pagination) => {
  global.fetch = jest.fn().mockResolvedValue({ ok, json: async () => ({ data: { applications, pagination } }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><MyPetsApplicationsPage /></MemoryRouter>
    </QueryClientProvider>
  );
};

describe('MyPetsApplicationsPage 完成認養', () => {
  beforeEach(() => {
    adoptionAPI.completeAdoption.mockReset().mockResolvedValue({ data: { adoption: { status: 'completed' } } });
  });

  test('只有已通過的申請顯示「完成認養」按鈕', async () => {
    renderPage([app('approved'), app('pending'), app('completed')]);
    await screen.findByText('小白-approved');
    expect(screen.getAllByRole('button', { name: '完成認養' })).toHaveLength(1);
  });

  test('在確認視窗按「確認完成」才呼叫完成認養 API，成功後關閉視窗', async () => {
    renderPage([app('approved')]);
    fireEvent.click(await screen.findByRole('button', { name: '完成認養' }));
    const dialog = screen.getByRole('dialog', { name: '確認完成認養' });
    expect(dialog).toHaveTextContent('小白-approved');
    expect(dialog).toHaveTextContent('adopter1');
    expect(adoptionAPI.completeAdoption).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '確認完成' }));
    await waitFor(() => expect(adoptionAPI.completeAdoption).toHaveBeenCalledWith('app-approved', {}));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  test('同一隻動物還有其他進行中的申請時，確認視窗說明會一併結束', async () => {
    renderPage([app('approved')]);
    const listFetch = global.fetch;
    global.fetch = jest.fn((url) => (url.includes('/details')
      ? Promise.resolve({ ok: true, json: async () => ({ data: { reviewInsights: { pet: { otherActiveApplications: 2 } } } }) })
      : listFetch(url)));
    fireEvent.click(await screen.findByRole('button', { name: '完成認養' }));
    const dialog = screen.getByRole('dialog', { name: '確認完成認養' });
    await waitFor(() => expect(dialog).toHaveTextContent('另外 2 份這隻動物進行中的申請會一併結束，並通知申請人。'));
  });

  test('按取消或 Esc 關閉視窗，不呼叫 API', async () => {
    renderPage([app('approved')]);
    fireEvent.click(await screen.findByRole('button', { name: '完成認養' }));
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '完成認養' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(adoptionAPI.completeAdoption).not.toHaveBeenCalled();
  });
});

describe('MyPetsApplicationsPage 拒絕申請', () => {
  const reviewCalls = () => global.fetch.mock.calls.filter(([url]) => url.includes('/review'));

  test('要填原因才能送出，點常用原因會填進輸入框', async () => {
    renderPage([app('pending')]);
    fireEvent.click(await screen.findByRole('button', { name: '拒絕' }));
    screen.getByRole('dialog', { name: '拒絕 小白-pending 的申請' });
    const submit = screen.getByRole('button', { name: '確定拒絕' });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '照顧時間不足' }));
    expect(screen.getByLabelText('拒絕原因')).toHaveValue('照顧時間不足');
    fireEvent.click(submit);
    await waitFor(() => expect(reviewCalls()).toHaveLength(1));
    const [url, options] = reviewCalls()[0];
    expect(url).toContain('/api/adoptions/app-pending/review');
    expect(JSON.parse(options.body)).toEqual({ decision: 'rejected', reason: '照顧時間不足' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  test('動物已被認養時不顯示「通過」，只能拒絕', async () => {
    renderPage([{ ...app('pending'), pet: { _id: 'p1', name: '咪咪', adoptionStatus: 'adopted' } }]);
    expect(await screen.findByText('咪咪 已被認養，這份申請只能拒絕。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '通過' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '拒絕' })).toBeInTheDocument();
  });

  test('只填空白不能送出', async () => {
    renderPage([app('pending')]);
    fireEvent.click(await screen.findByRole('button', { name: '拒絕' }));
    fireEvent.change(screen.getByLabelText('拒絕原因'), { target: { value: '   ' } });
    expect(screen.getByRole('button', { name: '確定拒絕' })).toBeDisabled();
    expect(reviewCalls()).toHaveLength(0);
  });
});

describe('MyPetsApplicationsPage 分頁', () => {
  const listUrls = () => global.fetch.mock.calls.map(([url]) => url).filter((u) => u.includes('my-pets-applications'));

  beforeEach(() => { window.scrollTo = jest.fn(); });

  test('帶頁碼向後端查詢；超過一頁時可以換頁，換篩選會回到第 1 頁', async () => {
    renderPage([app('pending')], true, { totalPages: 3 });
    await screen.findByText('小白-pending');
    expect(listUrls()[0]).toContain('?page=1&limit=10');
    const pager = screen.getByRole('navigation', { name: '分頁' });
    fireEvent.click(within(pager).getByRole('button', { name: '第 2 頁' }));
    await waitFor(() => expect(listUrls().at(-1)).toContain('?page=2&limit=10'));
    fireEvent.click(screen.getByRole('button', { name: '已完成' }));
    await waitFor(() => expect(listUrls().at(-1)).toContain('?page=1&limit=10&status=completed'));
  });

  test('只有一頁時不顯示分頁', async () => {
    renderPage([app('pending')], true, { totalPages: 1 });
    await screen.findByText('小白-pending');
    expect(screen.queryByRole('navigation', { name: '分頁' })).not.toBeInTheDocument();
  });
});

describe('MyPetsApplicationsPage 載入狀態', () => {
  test('載入失敗時顯示錯誤，而不是「暫無申請記錄」', async () => {
    renderPage([], false);
    expect(await screen.findByRole('alert')).toHaveTextContent('載入失敗，請稍後再試');
    expect(screen.queryByText('暫無申請記錄')).not.toBeInTheDocument();
  });
});
