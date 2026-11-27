import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { EyeOff, Gamepad2, PawPrint, RotateCcw, SearchX } from 'lucide-react';
import { Button, Card, Skeleton } from '../components/ui';
import EmptyState from '../components/EmptyState';
import GameMascot from '../components/GameMascot';
import { TYPE_ICONS } from '../components/PetTypeCard';
import Top3Card from '../components/Top3Card';
import { petTypes } from '../data/matchGameQuestions';
import { aiService, errorMessage } from '../services/aiService';

// Top 3 推薦與回饋（T15）：按「不適合」時用回應的 items 直接換掉卡片，不重新整理頁面。
// 沒玩過配對遊戲（T10）時先請使用者玩遊戲：遊戲是填配對欄位的主要方式，沒玩過的推薦沒有依據
const RecommendationsPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | error
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false); // 送出回饋期間停用所有卡片的按鈕，避免連點送出兩次
  const [gate, setGate] = useState('checking'); // checking | needs-game | open
  const [petType, setPetType] = useState(null);

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
    let cancelled = false;
    (async () => {
      try {
        const profile = (await aiService.getProfile()).data?.data;
        if (cancelled) return;
        if (profile && !profile.gameProfile) {
          setGate('needs-game');
          return;
        }
        setPetType(profile?.gameProfile?.petType || null);
      } catch {
        // 讀不到配對檔案時不擋，照常顯示推薦，主線不中斷
      }
      if (cancelled) return;
      setGate('open');
      load();
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const skipGame = () => {
    setGate('open');
    load();
  };

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
  const typeLabel = petType && (petTypes.find((t) => t.code === petType.code)?.label || petType.label);
  const TypeIcon = (petType && TYPE_ICONS[petType.code]) || PawPrint;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">為你推薦的 3 隻毛孩</h1>
            <p className="mt-1 text-gray-600">依你的配對檔案排序；按「不適合」會換一批，並降低相似動物的排序</p>
            {typeLabel && (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-primary-50 px-3 py-1 text-sm font-medium text-primary-700">
                <TypeIcon className="h-4 w-4" aria-hidden="true" />
                你的毛孩類型：{typeLabel}
              </p>
            )}
          </div>
          {gate !== 'needs-game' && (
            <Button variant="outline" onClick={() => navigate('/match-game')} className="inline-flex items-center gap-2 self-start">
              <Gamepad2 className="w-4 h-4" aria-hidden="true" />
              玩配對遊戲讓推薦更準
            </Button>
          )}
        </div>

        {gate === 'needs-game' && (
          <div className="mx-auto max-w-2xl">
            <Card>
              <GameMascot size="lg">
                <h2 className="text-lg font-semibold text-gray-900">先陪我玩個小遊戲吧！</h2>
                <p className="mt-1 text-gray-700">
                  你還沒玩過配對小遊戲。回答 8 個生活小問題，我才知道哪幾隻毛孩跟你最合拍。
                </p>
              </GameMascot>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <Button
                  size="lg"
                  onClick={() => navigate('/match-game', { state: { start: true } })}
                  className="inline-flex items-center justify-center gap-2"
                >
                  <Gamepad2 className="h-5 w-5" aria-hidden="true" />
                  開始配對遊戲
                </Button>
                <Button size="lg" variant="ghost" onClick={skipGame}>先看推薦</Button>
              </div>
              <p className="mt-3 text-sm text-gray-600">不玩也可以先看，推薦會依你在個人檔案填的資料排序。</p>
            </Card>
          </div>
        )}

        {gate !== 'needs-game' && status === 'loading' && (
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
