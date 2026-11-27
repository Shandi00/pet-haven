import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import ShelterDashboardPage from './ShelterDashboardPage';

const mockNavigate = jest.fn();
let mockAuth;
jest.mock('react-router-dom', () => ({ ...jest.requireActual('react-router-dom'), useNavigate: () => mockNavigate }));
jest.mock('../services/auth', () => ({ useAuth: () => mockAuth }));

const SHELTER = { _id: 'shelter1', role: 'shelter' };
const APP = { _id: 'a1', status: 'pending', createdAt: '2026-11-26T00:00:00Z', pet: { _id: 'p1', name: '小白' }, applicant: { username: 'adopter1' } };

// 依網址回傳後端真實的格式；後端沒有的路徑回 405、limit 超過 100 回 400（與後端驗證一致）
const mockBackend = (applications = [APP]) => {
  global.fetch = jest.fn(async (url) => {
    const u = new URL(url);
    const reply = (status, body) => ({ ok: status < 400, status, json: async () => body });
    if (Number(u.searchParams.get('limit')) > 100) return reply(400, { success: false });
    if (u.pathname === '/api/adoptions/my-pets-applications') return reply(200, { success: true, data: { applications } });
    if (u.pathname === '/api/pets') return reply(200, { pets: [] });
    if (u.pathname.endsWith('/stats')) return reply(200, { success: true, data: { overview: {} } });
    return reply(405, { success: false, message: '不支援此請求方法' });
  });
};

const renderPage = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><ShelterDashboardPage /></MemoryRouter>
  </QueryClientProvider>
);

describe('ShelterDashboardPage', () => {
  beforeEach(() => { mockNavigate.mockReset(); mockBackend(); });

  test('登入狀態還在載入時不會導回首頁', () => {
    mockAuth = { user: null, loading: true };
    renderPage();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('載入完成且不是收容所或管理員時導回首頁', () => {
    mockAuth = { user: { _id: 'u1', role: 'user' }, loading: false };
    renderPage();
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  test('收容所看到自己動物收到的申請，且不呼叫不存在的 API', async () => {
    mockAuth = { user: SHELTER, loading: false };
    renderPage();
    expect(await screen.findByText('小白')).toBeInTheDocument();
    const urls = global.fetch.mock.calls.map(([url]) => url);
    expect(urls.some((url) => url.includes('/api/adoptions/my-pets-applications'))).toBe(true);
    expect(urls.filter((url) => new URL(url).pathname === '/api/adoptions')).toHaveLength(0);
    expect(urls.every((url) => Number(new URL(url).searchParams.get('limit') || 0) <= 100)).toBe(true);
  });

  test('申請超過 10 筆時分頁顯示，篩選後回到第 1 頁', async () => {
    mockAuth = { user: SHELTER, loading: false };
    const many = Array.from({ length: 25 }, (_, i) => ({
      ...APP, _id: `a${i}`, applicationId: `AD${i}`, status: i < 5 ? 'completed' : 'pending', pet: { _id: 'p1', name: `毛孩${i}` } }));
    mockBackend(many);
    renderPage();
    await screen.findByText('毛孩0');
    const rows = () => screen.getAllByRole('row').length - 1;  // 扣掉表頭
    expect(rows()).toBe(10);
    expect(screen.getByText('共 25 筆')).toBeInTheDocument();
    const pager = screen.getByRole('navigation', { name: '分頁' });
    fireEvent.click(within(pager).getByRole('button', { name: '第 3 頁' }));
    expect(rows()).toBe(5);
    expect(screen.getByText('毛孩24')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('申請狀態'), { target: { value: 'completed' } });
    expect(rows()).toBe(5);  // 只剩 5 筆已完成，回到第 1 頁且不需要分頁
    expect(screen.queryByRole('navigation', { name: '分頁' })).not.toBeInTheDocument();
  });
});
