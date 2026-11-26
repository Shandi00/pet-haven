import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowLeft, CheckCircle2, RotateCcw } from 'lucide-react';
import { Button, Card, LoadingSpinner, ProgressBar } from '../components/ui';
import PetTypeCard from '../components/PetTypeCard';
import { questions } from '../data/matchGameQuestions';
import { computeGameResult } from '../utils/matchGame';
import { matchingAPI } from '../services/api';
import { aiService } from '../services/aiService';

// 配對小遊戲（T10）：題目與計分見 docs/features/配對遊戲題目對照表.md

// 換題後這段時間內忽略選項點擊，避免連點兩下時第二下落在下一題、把下一題也答掉。
// 涵蓋換題動畫 animate-slide-up（0.3 秒），再多留一點給較慢的連點
const SWITCH_LOCK_MS = 400;

// 選項按鈕：平常灰色外框、深灰字，滑鼠移上去變橘色外框；已選時是實心橘色
const OPTION_BASE = 'flex items-center gap-3 text-left border-2';
const OPTION_IDLE = `${OPTION_BASE} border-gray-300 hover:border-orange-500`;
const OPTION_SELECTED = `${OPTION_BASE} border-orange-500`;

const MatchGamePage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0); // 目前第幾題，從 0 開始
  const [answers, setAnswers] = useState({}); // { q1: 'A', ... }；只存在 state，離開頁面就清空
  const [status, setStatus] = useState('playing'); // playing | saving | error | done
  const [errorMessage, setErrorMessage] = useState('');
  const [petType, setPetType] = useState(null);
  const lastSwitchRef = useRef(0); // 上次換題的時間（Date.now()）

  const goTo = (nextStep) => {
    lastSwitchRef.current = Date.now();
    setStep(nextStep);
  };

  // 先用三支既有 API 寫入配對欄位，再保存原始答案與毛孩類型（契約 §1）
  const save = async (finalAnswers) => {
    const answerList = questions.map((q) => ({ questionId: q.id, optionId: finalAnswers[q.id] }));
    const result = computeGameResult(questions, answerList);
    setStatus('saving');
    try {
      await matchingAPI.updateLifestyleProfile(result.lifestyle);
      await matchingAPI.updateExperienceProfile(result.experience);
      await matchingAPI.updateEnvironmentProfile(result.environment);
      await aiService.saveGameResult({ answers: answerList, petType: result.petType });
      setPetType(result.petType);
      setStatus('done');
    } catch (error) {
      setErrorMessage(error.response?.data?.message || '連線失敗，請稍後再試');
      setStatus('error');
    }
  };

  const choose = (optionId) => {
    if (Date.now() - lastSwitchRef.current < SWITCH_LOCK_MS) return;
    const question = questions[step];
    const next = { ...answers, [question.id]: optionId };
    setAnswers(next);
    if (step < questions.length - 1) {
      goTo(step + 1);
    } else {
      save(next);
    }
  };

  const restart = () => {
    goTo(0);
    setAnswers({});
    setPetType(null);
    setErrorMessage('');
    setStatus('playing');
  };

  const question = questions[step];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">配對小遊戲</h1>
          <p className="mt-2 text-gray-600">回答 {questions.length} 個問題，找出適合你的毛孩類型</p>
        </div>

        {status === 'playing' && (
          <Card>
            <div key={question.id} className="animate-slide-up">
              <div className="flex items-center justify-between mb-3 min-h-[2rem]">
                {step > 0 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => goTo(step - 1)}
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
              <ProgressBar value={step + 1} max={questions.length} label={`第 ${step + 1} 題，共 ${questions.length} 題`} />

              <h2 id="match-game-question" className="mt-6 mb-4 text-xl font-semibold text-gray-900">
                {question.question}
              </h2>
              <div role="group" aria-labelledby="match-game-question" className="space-y-3">
                {question.options.map((option) => {
                  const selected = answers[question.id] === option.id;
                  return (
                    <Button
                      key={option.id}
                      variant={selected ? 'primary' : 'ghost'}
                      fullWidth
                      aria-pressed={selected}
                      onClick={() => choose(option.id)}
                      className={selected ? OPTION_SELECTED : OPTION_IDLE}
                    >
                      <span className="font-bold" aria-hidden="true">{option.id}</span>
                      <span>{option.label}</span>
                    </Button>
                  );
                })}
              </div>
            </div>
          </Card>
        )}

        {status === 'saving' && (
          <Card>
            <div role="status" className="flex flex-col items-center gap-4 py-8">
              <LoadingSpinner />
              <p className="text-gray-600">正在儲存你的配對結果…</p>
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
          <Card>
            <PetTypeCard petType={petType} className="animate-fade-in py-4">
              <p className="mt-4 flex items-center gap-2 text-sm text-green-600">
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
