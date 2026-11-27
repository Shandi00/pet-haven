import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowLeft, CheckCircle2, PawPrint, RotateCcw } from 'lucide-react';
import { Button, Card } from '../components/ui';
import Confetti from '../components/Confetti';
import GameMascot from '../components/GameMascot';
import PetTypeCard, { TYPE_ICONS } from '../components/PetTypeCard';
import { petTypes, questions } from '../data/matchGameQuestions';
import { displayFor } from '../data/matchGameDisplay';
import { computeGameResult } from '../utils/matchGame';
import { matchingAPI } from '../services/api';
import { aiService } from '../services/aiService';

// 配對小遊戲（T10）：題目與計分見 docs/features/配對遊戲題目對照表.md，選項圖示與小狗的回應見 data/matchGameDisplay.js
// 選完後停一下再換題，讓人看到打勾和小狗的回應；這段時間的點擊一律忽略，連點兩下也不會把下一題答掉
export const ADVANCE_MS = 900;
// 「比對中」至少顯示這麼久，結果揭曉才有節奏（存檔通常不到一秒）
export const MIN_ANALYZE_MS = 1200;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// 8 個腳印當進度：答過的填滿、目前這題是外框、還沒到的是灰色；左右交錯像一路走過來
const PawTrail = ({ total, done, current }) => (
  <div
    role="progressbar"
    aria-valuemin={1}
    aria-valuemax={total}
    aria-valuenow={current + 1}
    aria-label={`第 ${current + 1} 題，共 ${total} 題`}
    className="mt-3 mb-6 flex items-center gap-2.5"
  >
    {Array.from({ length: total }, (_, i) => (
      <span key={i} className={`inline-flex ${i % 2 ? 'translate-y-1 rotate-12' : '-translate-y-1 -rotate-12'}`}>
        <PawPrint
          aria-hidden="true"
          className={`h-6 w-6 transition-colors ${
            i < done ? 'fill-primary-500 text-primary-500 motion-safe:animate-pop-in' : i === current ? 'text-primary-500' : 'text-gray-300'
          }`}
        />
      </span>
    ))}
  </div>
);

const MatchGamePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  // 從推薦頁「開始配對遊戲」或結果頁「再玩一次」進來時直接開始，不再看一次開場
  const [status, setStatus] = useState(location.state?.start ? 'playing' : 'intro'); // intro | playing | saving | error | done
  const [step, setStep] = useState(0); // 目前第幾題，從 0 開始
  const [answers, setAnswers] = useState({}); // { q1: 'A', ... }；只存在 state，離開頁面就清空
  const [pending, setPending] = useState(null); // 剛選的選項，換題前顯示打勾與回應
  const [errorMessage, setErrorMessage] = useState('');
  const [petType, setPetType] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  // 先用三支既有 API 寫入配對欄位，再保存原始答案與毛孩類型（契約 §1）
  const save = async (finalAnswers) => {
    const answerList = questions.map((q) => ({ questionId: q.id, optionId: finalAnswers[q.id] }));
    const result = computeGameResult(questions, answerList);
    setStatus('saving');
    const started = Date.now();
    try {
      // 後端的 PUT 會整包取代、沒帶的欄位設回預設值，所以先讀目前的檔案再合併遊戲答案，
      // 遊戲沒問到的欄位（過往養過的寵物、訓練經驗、孩子年齡、其他寵物等）才不會被清掉。
      // 讀取失敗或沒有拿到資料時不存檔，交給錯誤畫面讓使用者重試
      const current = (await matchingAPI.getProfile()).data?.data;
      if (!current) {
        throw new Error('讀不到目前的配對檔案');
      }
      await matchingAPI.updateLifestyleProfile({ ...current.lifestyleProfile, ...result.lifestyle });
      await matchingAPI.updateExperienceProfile({ ...current.experienceProfile, ...result.experience });
      await matchingAPI.updateEnvironmentProfile({ ...current.environmentProfile, ...result.environment });
      await aiService.saveGameResult({ answers: answerList, petType: result.petType });
      const left = MIN_ANALYZE_MS - (Date.now() - started);
      if (left > 0) await wait(left);
      setPetType(result.petType);
      setStatus('done');
    } catch (error) {
      setErrorMessage(error.response?.data?.message || '連線失敗，請稍後再試');
      setStatus('error');
    }
  };

  const choose = (optionId) => {
    if (pending) return;
    const question = questions[step];
    const next = { ...answers, [question.id]: optionId };
    setAnswers(next);
    setPending(optionId);
    timerRef.current = setTimeout(() => {
      setPending(null);
      if (step < questions.length - 1) {
        setStep(step + 1);
      } else {
        save(next);
      }
    }, ADVANCE_MS);
  };

  const restart = () => {
    clearTimeout(timerRef.current);
    setStep(0);
    setAnswers({});
    setPending(null);
    setPetType(null);
    setErrorMessage('');
    setStatus('playing');
  };

  const question = questions[step];
  const reaction = pending ? displayFor(question.id, pending).reaction : '';

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <h1 className="mb-6 text-3xl font-bold text-gray-900">配對小遊戲</h1>

        {status === 'intro' && (
          <Card>
            <GameMascot size="lg">
              <p className="text-lg font-semibold">嗨！我來幫你找最合拍的毛孩</p>
              <p className="mt-1 text-gray-700">
                回答 {questions.length} 個生活小問題，大約 1 分鐘，就知道你適合哪一型的毛孩。
              </p>
            </GameMascot>
            <p className="mt-8 text-sm font-medium text-gray-700">你會是這三型的哪一型？</p>
            <ul className="mt-3 grid gap-3 sm:grid-cols-3">
              {petTypes.map((t) => {
                const Icon = TYPE_ICONS[t.code] || PawPrint;
                return (
                  <li key={t.code} className="flex items-center gap-3 rounded-xl border border-gray-200 p-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <span className="font-medium text-gray-900">{t.label}</span>
                  </li>
                );
              })}
            </ul>
            <p className="mt-8 text-sm text-gray-600">答案會更新你的配對檔案，推薦的毛孩也會跟著改變。</p>
            <Button size="lg" onClick={restart} className="mt-4 inline-flex w-full items-center justify-center gap-2 sm:w-auto">
              <PawPrint className="h-5 w-5" aria-hidden="true" />
              開始遊戲
            </Button>
          </Card>
        )}

        {status === 'playing' && (
          <Card>
            <div className="flex items-center justify-between min-h-[2rem]">
              {step > 0 ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setStep(step - 1)}
                  disabled={Boolean(pending)}
                  className="inline-flex items-center gap-1 -ml-3"
                >
                  <ArrowLeft className="w-4 h-4" aria-hidden="true" />
                  上一題
                </Button>
              ) : (
                <span />
              )}
              <span className="text-sm text-gray-600">
                第 {step + 1} 題／共 {questions.length} 題
              </span>
            </div>
            <PawTrail total={questions.length} done={pending ? step + 1 : step} current={step} />
            <div key={question.id} className="motion-safe:animate-slide-up">
              <GameMascot bounceKey={pending ? `${question.id}-${pending}` : question.id}>
                <h2 id="match-game-question" className="text-lg sm:text-xl font-semibold text-gray-900">
                  {question.question}
                </h2>
                <p aria-live="polite" className={`mt-1 min-h-[1.5rem] text-sm ${pending ? 'font-medium text-primary-700' : 'text-gray-600'}`}>
                  {pending ? reaction : '選一個最像你的答案'}
                </p>
              </GameMascot>
              <div
                role="group"
                aria-labelledby="match-game-question"
                className={`mt-6 grid gap-3 ${question.options.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}
              >
                {question.options.map((option) => {
                  const selected = answers[question.id] === option.id;
                  const Icon = displayFor(question.id, option.id).icon;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => choose(option.id)}
                      className={`group relative flex items-center gap-3 rounded-xl border-2 p-4 text-left transition duration-200 sm:flex-col sm:py-6 sm:text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 ${
                        selected
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 bg-white hover:border-primary-300 hover:shadow-md motion-safe:hover:-translate-y-0.5'
                      }`}
                    >
                      <span
                        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full transition-colors ${
                          selected ? 'bg-primary-500 text-white' : 'bg-primary-50 text-primary-600 group-hover:bg-primary-100'
                        }`}
                      >
                        <Icon className="h-6 w-6" aria-hidden="true" />
                      </span>
                      <span className="font-medium text-gray-900">{option.label}</span>
                      {selected && (
                        <CheckCircle2
                          aria-hidden="true"
                          className="absolute right-2 top-2 h-5 w-5 text-primary-600 motion-safe:animate-pop-in"
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>
        )}

        {status === 'saving' && (
          <Card>
            <div role="status" className="flex flex-col items-center gap-4 py-10 text-center">
              <div className="flex items-center gap-4" aria-hidden="true">
                {petTypes.map((t, i) => {
                  const Icon = TYPE_ICONS[t.code] || PawPrint;
                  return (
                    <span
                      key={t.code}
                      className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-50 text-primary-600 motion-safe:animate-pulse"
                      style={{ animationDelay: `${i * 0.25}s` }}
                    >
                      <Icon className="h-7 w-7" />
                    </span>
                  );
                })}
              </div>
              <p className="text-lg font-semibold text-gray-900">正在比對你的答案…</p>
              <p className="text-sm text-gray-600">同時把結果存進你的配對檔案</p>
            </div>
          </Card>
        )}

        {status === 'error' && (
          <Card>
            <div role="alert" className="flex flex-col items-center text-center py-4">
              <AlertCircle className="w-10 h-10 text-red-600 mb-3" aria-hidden="true" />
              <p className="font-medium text-red-600">{errorMessage}</p>
              <p className="mt-1 text-sm text-gray-600">你的答案還在，可以直接重試。</p>
              <div className="mt-6 flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <Button onClick={() => save(answers)} className="inline-flex items-center justify-center gap-2">
                  <RotateCcw className="w-4 h-4" aria-hidden="true" />
                  重試
                </Button>
                <Button variant="outline" onClick={restart}>
                  重新開始
                </Button>
              </div>
            </div>
          </Card>
        )}

        {status === 'done' && petType && (
          <Card className="relative overflow-hidden">
            <Confetti />
            <PetTypeCard petType={petType} className="relative py-4 motion-safe:animate-pop-in">
              <p className="mt-4 flex items-center gap-2 text-sm text-green-700">
                <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
                已更新你的配對檔案
              </p>
              <div className="mt-6 flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
                <Button onClick={() => navigate('/recommendations')}>看推薦</Button>
                <Button variant="outline" onClick={restart}>
                  再玩一次
                </Button>
              </div>
            </PetTypeCard>
          </Card>
        )}
      </div>
    </div>
  );
};

export default MatchGamePage;
