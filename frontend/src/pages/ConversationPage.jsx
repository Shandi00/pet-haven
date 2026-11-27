import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { ArrowLeft, Send, Check, CheckCheck } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useAuth } from '../services/auth';
import { displayName } from '../utils/displayName';

const ConversationPage = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const scrollRef = useRef(null);
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const { user } = useAuth();
  const currentUserId = user?._id;
  const isSelf = Boolean(currentUserId && currentUserId === userId);

  // 獲取對話記錄
  const { data: conversationData, isLoading, isError } = useQuery(
    ['conversation', userId],
    async () => {
      const response = await fetch(
        `http://localhost:5000/api/messages/conversation/${userId}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      );
      if (!response.ok) throw new Error('載入失敗');
      return response.json();
    },
    {
      select: (response) => response.data,
      refetchInterval: 3000, // 每3秒重新取得
      enabled: !isSelf,
    }
  );

  // 標記對話為已讀
  useEffect(() => {
    if (conversationData?.messages?.length > 0) {
      fetch(`http://localhost:5000/api/messages/conversation/${userId}/read-all`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      }).catch(err => console.error('標記已讀失敗:', err));
    }
  }, [userId, conversationData?.messages?.length]);

  // 發送訊息
  const sendMessageMutation = useMutation(
    async (content) => {
      const response = await fetch('http://localhost:5000/api/messages', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content,
          receiver: userId,
          type: 'text'
        })
      });

      if (!response.ok) {
        const error = await response.json();
        // 顯示後端返回的具體錯誤訊息
        throw new Error(error.message || error.error || '發送失敗');
      }

      return response.json();
    },
    {
      onSuccess: () => {
        setMessage('');
        queryClient.invalidateQueries(['conversation', userId]);
        queryClient.invalidateQueries(['conversations']);
      },
      onError: (error) => {
        toast.error(error.message || '發送失敗');
      },
      onSettled: () => {
        setIsSending(false);
      }
    }
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!message.trim() || isSending) return;

    setIsSending(true);
    sendMessageMutation.mutate(message.trim());
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString('zh-TW', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatDate = (date) => {
    const messageDate = new Date(date);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (messageDate.toDateString() === today.toDateString()) {
      return '今天';
    } else if (messageDate.toDateString() === yesterday.toDateString()) {
      return '昨天';
    } else {
      return messageDate.toLocaleDateString('zh-TW', {
        month: 'long',
        day: 'numeric'
      });
    }
  };

  // 群組訊息依日期
  const groupMessagesByDate = (messages) => {
    if (!messages) return {};
    
    return messages.reduce((groups, message) => {
      const date = new Date(message.createdAt).toDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(message);
      return groups;
    }, {});
  };

  const messages = conversationData?.messages || [];
  const otherUser = conversationData?.otherUser;
  const groupedMessages = groupMessagesByDate(messages);

  // 只有訊息數變多（新訊息或剛載入）時才捲到底；每 3 秒的重新讀取不會把正在往上看的使用者拉回底部
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  if (isSelf) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <p className="text-gray-700">不能私訊自己。</p>
        <Link to="/messages" className="mt-4 inline-block text-primary-600 hover:underline">回到訊息中心</Link>
      </div>
    );
  }

  return (
    // 高度扣掉上方導覽列（4rem），訊息只在卡片內捲動，輸入框固定在卡片底部，不會蓋住頁尾
    <div className="max-w-4xl mx-auto sm:px-4 sm:py-6">
      <div className="flex flex-col h-[calc(100vh-4rem)] sm:h-[calc(100vh-7rem)] bg-white sm:rounded-xl sm:border sm:border-gray-200 sm:shadow-sm overflow-hidden">
        {/* 頭部 */}
        <div className="border-b border-gray-200 p-4 flex items-center gap-3">
          <button
            onClick={() => navigate('/messages')}
            className="text-gray-600 hover:text-gray-900"
            aria-label="回到訊息中心"
          >
            <ArrowLeft className="w-6 h-6" />
          </button>
          {otherUser && (
            <>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-500 flex items-center justify-center text-white font-semibold">
                {displayName(otherUser)[0]}
              </div>
              <div className="flex-1 min-w-0">
                <h1 className="font-semibold text-gray-900 truncate">{displayName(otherUser)}</h1>
                {otherUser.username && <p className="text-sm text-gray-500 truncate">@{otherUser.username}</p>}
              </div>
            </>
          )}
        </div>

        {/* 訊息區域 */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto bg-gray-50 px-4 py-6 space-y-6">
          {isLoading ? (
            <div className="animate-pulse space-y-4" role="status" aria-label="載入中">
              {[...Array(4)].map((_, i) => (
                <div key={i} className={`flex ${i % 2 ? 'justify-end' : ''}`}>
                  <div className="h-10 w-48 bg-gray-200 rounded-2xl" />
                </div>
              ))}
            </div>
          ) : isError ? (
            <p role="alert" className="text-center py-12 text-red-600">載入對話失敗，請稍後再試</p>
          ) : Object.keys(groupedMessages).length > 0 ? (
            Object.entries(groupedMessages).map(([date, dateMessages]) => (
              <div key={date}>
                {/* 日期分隔線 */}
                <div className="flex items-center justify-center mb-4">
                  <span className="px-3 py-1 bg-gray-200 text-gray-600 text-xs rounded-full">
                    {formatDate(dateMessages[0].createdAt)}
                  </span>
                </div>

                {/* 該日期的訊息 */}
                <div className="space-y-3">
                  {dateMessages.map((msg) => {
                    const isCurrentUser = (msg.sender?._id || msg.sender) === currentUserId;

                    return (
                      <div
                        key={msg._id}
                        className={`flex gap-2 ${isCurrentUser ? 'flex-row-reverse' : 'flex-row'}`}
                      >
                        {/* 頭像 */}
                        {!isCurrentUser && (
                          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-400 to-primary-500 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                            {displayName(msg.sender)[0]}
                          </div>
                        )}

                        {/* 訊息氣泡 */}
                        <div className={`max-w-[75%] lg:max-w-md ${isCurrentUser ? 'items-end' : 'items-start'} flex flex-col`}>
                          <div
                            className={`px-4 py-2 rounded-2xl ${
                              isCurrentUser
                                ? 'bg-primary-600 text-white rounded-tr-sm'
                                : 'bg-white text-gray-900 rounded-tl-sm shadow-sm'
                            }`}
                          >
                            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                          </div>

                          {/* 時間和狀態 */}
                          <div className={`flex items-center gap-1 mt-1 text-xs text-gray-500 ${isCurrentUser ? 'flex-row-reverse' : 'flex-row'}`}>
                            <span>{formatTime(msg.createdAt)}</span>
                            {isCurrentUser && (
                              msg.status === 'read'
                                ? <CheckCheck className="w-3 h-3 text-primary-500" aria-label="已讀" />
                                : <Check className="w-3 h-3" aria-label="已送出" />
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-12 text-gray-500">
              <p>還沒有訊息，開始對話吧！</p>
            </div>
          )}
        </div>

        {/* 輸入框 */}
        <form onSubmit={handleSubmit} className="border-t border-gray-200 p-3 sm:p-4 flex items-center gap-2 bg-white">
          <label htmlFor="conversation-input" className="sr-only">輸入訊息</label>
          <input
            id="conversation-input"
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="輸入訊息..."
            disabled={isSending}
            className="flex-1 min-w-0 px-4 py-2 border border-gray-300 rounded-full focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!message.trim() || isSending}
            aria-label="送出訊息"
            className="w-10 h-10 shrink-0 bg-primary-600 text-white rounded-full flex items-center justify-center hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </div>
  );
};

export default ConversationPage;
