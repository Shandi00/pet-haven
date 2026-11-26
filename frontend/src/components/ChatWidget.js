import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Bot, Send, X } from 'lucide-react';
import { Button } from './ui';
import { aiService, errorMessage } from '../services/aiService';

// AI 助理聊天視窗（T15）：登入後在右下角顯示。後端不保存聊天內容，關掉分頁就清空
const MESSAGE_MAX = 500;
const HISTORY_MAX = 10;
const GREETING = '你好，我是 Pet Haven 小幫手。可以問我認養流程、平台操作，或貓狗的基本照顧。';
// 契約 §4 的 source：只有 ai 是 Gemini 產生，其他要標示清楚，不能假裝是 AI
const SOURCE_LABEL = { rule: '規則回覆（未使用 AI）', fallback: '暫時無法使用 AI' };

const ChatWidget = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]); // { role, content, sources?, actions?, source? }
  const [waiting, setWaiting] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages, waiting]);

  const text = input.trim();
  const canSend = !waiting && text.length > 0 && input.length <= MESSAGE_MAX;

  const send = async (e) => {
    e.preventDefault();
    if (!canSend) return;
    const history = messages.slice(-HISTORY_MAX).map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: 'user', content: text }]);
    setInput('');
    setWaiting(true);
    try {
      const d = (await aiService.chat(text, history)).data.data;
      setMessages((m) => [...m, { role: 'assistant', content: d.reply, sources: d.sources, actions: d.actions, source: d.source }]);
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: errorMessage(err), source: 'fallback', error: true }]);
    } finally {
      setWaiting(false);
    }
  };

  const go = (to) => {
    setOpen(false);
    navigate(to);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="問小幫手"
        className="fixed bottom-4 right-4 sm:bottom-5 sm:right-5 z-40 inline-flex items-center gap-2 rounded-full bg-primary-600 p-3 sm:px-4 text-white shadow-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      >
        <Bot className="w-5 h-5" aria-hidden="true" />
        {/* 手機只顯示圖示，少擋一點內容 */}
        <span className="hidden sm:inline">問小幫手</span>
      </button>
    );
  }

  return (
    <section
      role="dialog"
      aria-label="AI 小幫手"
      className="fixed z-40 inset-x-2 bottom-2 sm:inset-x-auto sm:right-5 sm:bottom-5 sm:w-96 flex flex-col max-h-[80vh] rounded-xl bg-white shadow-2xl border border-gray-200"
    >
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <h2 className="font-semibold text-gray-900">AI 小幫手</h2>
          <p className="text-xs text-gray-500">只根據標示出處的資料回答，不做醫療判斷</p>
        </div>
        <button type="button" onClick={() => setOpen(false)} aria-label="關閉小幫手" className="p-1 rounded text-gray-500 hover:text-gray-800">
          <X className="w-5 h-5" aria-hidden="true" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[12rem]" aria-live="polite">
        <p className="rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-800 mr-8">{GREETING}</p>
        {messages.map((m, i) =>
          m.role === 'user' ? (
            <p key={i} className="ml-8 rounded-lg bg-primary-600 px-3 py-2 text-sm text-white whitespace-pre-wrap">{m.content}</p>
          ) : (
            <div key={i} className="mr-8 space-y-2">
              <p className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${m.error ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-800'}`}>
                {m.content}
              </p>
              {SOURCE_LABEL[m.source] && <p className="text-xs text-gray-500">{SOURCE_LABEL[m.source]}</p>}
              {m.sources?.length > 0 && (
                <div className="text-xs text-gray-600">
                  <p className="flex items-center gap-1 font-medium"><BookOpen className="w-3.5 h-3.5" aria-hidden="true" />資料來源</p>
                  <ul className="list-disc pl-5">
                    {m.sources.map((s) => <li key={s.ref}>{s.title}</li>)}
                  </ul>
                </div>
              )}
              {m.actions?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {m.actions.map((a) => (
                    <Button key={a.to} size="sm" variant="outline" onClick={() => go(a.to)}>{a.label}</Button>
                  ))}
                </div>
              )}
            </div>
          )
        )}
        {waiting && <p className="mr-8 text-sm text-gray-500" role="status">小幫手思考中…</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="border-t border-gray-200 p-3">
        <div className="flex gap-2">
          <label htmlFor="chat-input" className="sr-only">輸入問題</label>
          <input
            id="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="例如：第一次養貓要準備什麼？"
            className="flex-1 min-w-0 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <Button type="submit" disabled={!canSend} aria-label="送出" className="inline-flex items-center">
            <Send className="w-4 h-4" aria-hidden="true" />
          </Button>
        </div>
        {input.length > MESSAGE_MAX && (
          <p className="mt-1 text-xs text-red-600">最多 {MESSAGE_MAX} 字（目前 {input.length} 字）</p>
        )}
      </form>
    </section>
  );
};

export default ChatWidget;
