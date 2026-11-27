import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { EyeOff, Gamepad2, RotateCcw, SearchX } from 'lucide-react';
import { Button, Skeleton } from '../components/ui';
import EmptyState from '../components/EmptyState';
import Top3Card from '../components/Top3Card';
import { aiService, errorMessage } from '../services/aiService';

// Top 3 推薦與回饋（T15）：按「不適合」時用回應的 items 直接換掉卡片，不重新整理頁面
const RecommendationsPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false); // 送出回饋期間停用所有卡片的按鈕，避免連點送出兩次

  const load = useCallback(async () => {
    setStatus('loading');
    try {
      setData((await aiService.getTop3()).data.data);
      setStatus('ready');
    } catch (e) {
      setError(errorMessage(e));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const dislike = async (pet) => {
    if (busy) return;
    setBusy(true);
    try {
      const next = (await aiService.sendFeedback(pet._id, 'dislike')).data.data;
      setData(next);
      if (next.avoided?.[0]?.note) toast.success(next.avoided[0].note);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const like = async (pet) => {
    if (busy) return;
    setBusy(true);
    try {
      await aiService.sendFeedback(pet._id, 'like');
    } catch {
      // 「適合」只是記錄，失敗也照樣帶去動物頁面
    }
    navigate(`/pets/${pet._id}`);
  };

  const restart = async () => {
    setBusy(true);
    try {
      await aiService.resetFeedback();
      await load();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const items = data?.items || [];
  const avoided = data?.avoided || [];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">為你推薦的 3 隻毛孩</h1>
            <p className="mt-1 text-gray-600">依你的配對檔案排序；按「不適合」會換一批，並降低相似動物的排序</p>
          </div>
          <Button variant="outline" onClick={() => navigate('/match-game')} className="inline-flex items-center gap-2 self-start">
            <Gamepad2 className="w-4 h-4" aria-hidden="true" />
            玩配對遊戲讓推薦更準
          </Button>
        </div>

        {status === 'loading' && (
          <div className="grid gap-6 md:grid-cols-3" role="status" aria-label="載入中">
            {[0, 1, 2].map((i) => <Skeleton key={i} variant="rect" height="28rem" />)}
          </div>
        )}

        {status === 'error' && (
          <div role="alert" className="bg-white rounded-lg border border-red-200 p-8 text-center">
            <p className="text-red-600">{error}</p>
            <Button className="mt-4" onClick={load}>重試</Button>
          </div>
        )}

        {status === 'ready' && (
          <>
            {avoided.length > 0 && (
              <div className="mb-6 rounded-lg bg-white border border-gray-200 p-4" aria-live="polite">
                <p className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <EyeOff className="w-4 h-4" aria-hidden="true" />
                  已避開 {avoided.length} 隻
                </p>
                <ul className="mt-2 space-y-1 text-sm text-gray-600">
                  {avoided.slice(0, 3).map((a) => <li key={a.petId}>{a.note}</li>)}
                </ul>
              </div>
            )}

            {items.length > 0 ? (
              <div className="grid gap-6 md:grid-cols-3">
                {items.map((item, i) => (
                  <Top3Card key={item.pet._id} item={item} rank={i + 1} onLike={like} onDislike={dislike} disabled={busy} />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200">
                <EmptyState
                  icon={SearchX}
                  title="目前沒有符合條件的毛孩"
                  description="可能是條件太嚴格，或你已經避開了所有動物。可以清除「不適合」紀錄重新開始，或到「尋找毛小孩」看看全部動物。"
                  showAction={false}
                />
                <div className="flex flex-col sm:flex-row justify-center gap-3 pb-10">
                  <Button onClick={restart} disabled={busy} className="inline-flex items-center justify-center gap-2">
                    <RotateCcw className="w-4 h-4" aria-hidden="true" />
                    重新開始
                  </Button>
                  <Button variant="outline" onClick={() => navigate('/pets')}>尋找毛小孩</Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default RecommendationsPage;
