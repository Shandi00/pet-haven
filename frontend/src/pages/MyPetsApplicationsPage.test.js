import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

const renderPage = (applications, ok = true) => {
  global.fetch = jest.fn().mockResolvedValue({ ok, json: async () => ({ data: { applications } }) });
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
    window.confirm = jest.fn(() => true);
  });

  test('只有已通過的申請顯示「完成認養」按鈕', async () => {
    renderPage([app('approved'), app('pending'), app('completed')]);
    await screen.findByText('小白-approved');
    expect(screen.getAllByRole('button', { name: '完成認養' })).toHaveLength(1);
  });

  test('按下並確認後呼叫完成認養 API', async () => {
    renderPage([app('approved')]);
    fireEvent.click(await screen.findByRole('button', { name: '完成認養' }));
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(adoptionAPI.completeAdoption).toHaveBeenCalledWith('app-approved', {}));
  });

  test('取消確認時不呼叫 API', async () => {
    window.confirm = jest.fn(() => false);
    renderPage([app('approved')]);
    fireEvent.click(await screen.findByRole('button', { name: '完成認養' }));
    expect(adoptionAPI.completeAdoption).not.toHaveBeenCalled();
  });
});

describe('MyPetsApplicationsPage 載入狀態', () => {
  test('載入失敗時顯示錯誤，而不是「暫無申請記錄」', async () => {
    renderPage([], false);
    expect(await screen.findByRole('alert')).toHaveTextContent('載入失敗，請稍後再試');
    expect(screen.queryByText('暫無申請記錄')).not.toBeInTheDocument();
  });
});
