import React from 'react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import ChatWidget from './ChatWidget';
import { aiService } from '../services/aiService';
import { aiMock } from '../services/aiMock';

jest.mock('../services/api', () => ({ matchingAPI: {}, aiAPI: {} }));
jest.mock('../services/aiService', () => ({
  ...jest.requireActual('../services/aiService'),
  aiService: { chat: jest.fn() },
}));

const ok = (data) => ({ data: { success: true, data } });

const renderWidget = () => {
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<ChatWidget />} />
        <Route path="/match-game" element={<div>配對小遊戲頁</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.click(screen.getByRole('button', { name: '問小幫手' }));
};

const ask = (text) => {
  fireEvent.change(screen.getByLabelText('輸入問題'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: '送出' }));
};

beforeEach(() => {
  jest.clearAllMocks();
  aiService.chat.mockImplementation((message) => aiMock.chat(message));
});

test('送出問題後顯示回答、資料來源與「去玩配對遊戲」，按下會導頁', async () => {
  renderWidget();
  ask('第一次養貓要準備什麼');

  expect(screen.getByText('小幫手思考中…')).toBeInTheDocument();
  expect(await screen.findByText(/建議先準備：貓砂盆/)).toBeInTheDocument();
  expect(screen.getByText('新手養貓準備清單')).toBeInTheDocument();
  expect(aiService.chat).toHaveBeenCalledWith('第一次養貓要準備什麼', []);
  fireEvent.click(screen.getByRole('button', { name: '去玩配對遊戲' }));
  expect(screen.getByText('配對小遊戲頁')).toBeInTheDocument();
});

test('醫療問題顯示就醫提醒，並標示不是 AI 回答', async () => {
  renderWidget();
  ask('我的貓一直嘔吐怎麼辦');
  expect(await screen.findByText(/獸醫/)).toBeInTheDocument();
  expect(screen.getByText('規則回覆（未使用 AI）')).toBeInTheDocument();
});

test('輸入框空白或超過 500 字時，送出按鈕停用、不會呼叫 API', () => {
  renderWidget();
  const send = screen.getByRole('button', { name: '送出' });
  expect(send).toBeDisabled();
  fireEvent.change(screen.getByLabelText('輸入問題'), { target: { value: '   ' } });
  expect(send).toBeDisabled();
  fireEvent.change(screen.getByLabelText('輸入問題'), { target: { value: '字'.repeat(501) } });
  expect(send).toBeDisabled();
  expect(screen.getByText(/最多 500 字/)).toBeInTheDocument();
  fireEvent.submit(send.closest('form'));
  expect(aiService.chat).not.toHaveBeenCalled();
});

test('source 是 fallback 時標示「暫時無法使用 AI」', async () => {
  aiService.chat.mockResolvedValue(ok({ reply: '小幫手暫時無法回答，請稍後再試', sources: [], actions: [], refused: false, source: 'fallback' }));
  renderWidget();
  ask('第一次養貓要準備什麼');
  expect(await screen.findByText('小幫手暫時無法回答，請稍後再試')).toBeInTheDocument();
  expect(screen.getByText('暫時無法使用 AI')).toBeInTheDocument();
});

test('送出時只帶最近 10 則對話', async () => {
  aiService.chat.mockImplementation(async (message) => ok({ reply: `回答${message}`, sources: [], actions: [], refused: false, source: 'rule' }));
  renderWidget();
  for (let i = 0; i < 6; i += 1) {
    ask(`問題${i}`);
    // eslint-disable-next-line no-await-in-loop
    await screen.findByText(`回答問題${i}`);
  }
  // 第 6 次送出前已有 5 問 5 答，共 10 則；第 7 次送出前有 12 則，只取最後 10 則，最早的一問一答被丟掉
  expect(aiService.chat.mock.calls[5][1]).toHaveLength(10);
  ask('問題6');
  await screen.findByText('回答問題6');
  const history = aiService.chat.mock.calls[6][1];
  expect(history).toHaveLength(10);
  expect(history[0]).toEqual({ role: 'user', content: '問題1' });
  expect(history.every((h) => Object.keys(h).join() === 'role,content')).toBe(true);
});
