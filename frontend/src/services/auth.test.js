import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from './auth';
import { authAPI } from './api';

jest.mock('./api', () => ({ authAPI: { getCurrentUser: jest.fn() } }));
jest.mock('react-hot-toast', () => ({ __esModule: true, default: { success: jest.fn(), error: jest.fn() } }));

const Name = () => {
  const { user } = useAuth();
  return <p>{user?.firstName || '沒有登入'}</p>;
};

beforeEach(() => {
  localStorage.setItem('token', 't');
  localStorage.setItem('user', JSON.stringify({ _id: 'u1', firstName: '舊名字' }));
});
afterEach(() => localStorage.clear());

test('重新開啟網站時先顯示存下來的資料，再換成後端最新的資料', async () => {
  authAPI.getCurrentUser.mockResolvedValue({ data: { user: { _id: 'u1', firstName: '新名字' } } });
  render(<AuthProvider><Name /></AuthProvider>);
  expect(await screen.findByText('新名字')).toBeInTheDocument();
  expect(JSON.parse(localStorage.getItem('user')).firstName).toBe('新名字');
});

test('讀不到後端時保留原本的資料', async () => {
  authAPI.getCurrentUser.mockRejectedValue(new Error('offline'));
  render(<AuthProvider><Name /></AuthProvider>);
  expect(await screen.findByText('舊名字')).toBeInTheDocument();
  await waitFor(() => expect(authAPI.getCurrentUser).toHaveBeenCalled());
  expect(JSON.parse(localStorage.getItem('user')).firstName).toBe('舊名字');
});
