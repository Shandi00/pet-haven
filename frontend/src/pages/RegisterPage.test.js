import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RegisterPage from './RegisterPage';

const mockRegister = jest.fn();
jest.mock('../services/auth', () => ({ useAuth: () => ({ register: mockRegister }) }));

// 前端規則要跟後端 REGISTER_SCHEMA 一致，否則畫面可送出、後端卻擋下
describe('RegisterPage 欄位規則與後端一致', () => {
  beforeEach(() => {
    mockRegister.mockReset();
    render(<MemoryRouter><RegisterPage /></MemoryRouter>);
  });

  const submit = () => fireEvent.submit(screen.getByRole('button', { name: /建立帳號/ }).closest('form'));

  test('使用者名稱有底線時擋下', async () => {
    fireEvent.change(screen.getByLabelText('使用者名稱'), { target: { value: 'pet_lover' } });
    submit();
    expect(await screen.findByText('使用者名稱只能包含英文字母和數字')).toBeInTheDocument();
    expect(mockRegister).not.toHaveBeenCalled();
  });

  test('密碼沒有大寫字母時擋下', async () => {
    fireEvent.change(screen.getByLabelText('密碼'), { target: { value: 'abc12345' } });
    submit();
    expect(await screen.findByText('密碼必須包含大小寫字母和數字')).toBeInTheDocument();
    expect(mockRegister).not.toHaveBeenCalled();
  });

  test('密碼欄先寫出規則', () => {
    expect(screen.getByText(/至少 6 個字元，需包含大寫、小寫字母和數字/)).toBeInTheDocument();
  });
});
