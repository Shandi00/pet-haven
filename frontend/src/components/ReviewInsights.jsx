import React from 'react';
import { AlertTriangle, ClipboardCheck, Info } from 'lucide-react';

// 審核輔助（契約 §7）：後端只給審核者 reviewInsights，全部由規則產生
const PET_STATUS = {
  available: '可認養', pending: '審核中', adopted: '已被認養', hold: '保留中',
  'not-available': '不可認養', pending_review: '待上架審核',
};
const ACTIVITY = { low: '低', moderate: '中等', high: '高' };
const goodWithLabel = (v) => (v === true ? '適合' : v === false ? '不適合' : '未填');

const Row = ({ label, children }) => (
  <div className="flex justify-between gap-3 py-1">
    <dt className="text-sm text-gray-600">{label}</dt>
    <dd className="text-sm font-medium text-gray-900 text-right">{children}</dd>
  </div>
);

const ReviewInsights = ({ insights, pet }) => {
  if (!insights) return null;
  const goodWith = pet?.personality?.goodWith || {};
  const { applicant, match, checks = [] } = insights;

  return (
    <section className="mb-6" aria-labelledby="review-insights-title">
      <h4 id="review-insights-title" className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
        <ClipboardCheck className="w-5 h-5 mr-2 text-primary-600" aria-hidden="true" />
        審核輔助
      </h4>

      <div className="grid gap-4 sm:grid-cols-2 mb-4">
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="font-medium text-gray-900 mb-2">{pet?.name || '這隻動物'}</p>
          <dl>
            <Row label="目前狀態">{PET_STATUS[pet?.adoptionStatus] || '未知'}</Row>
            <Row label="其他進行中的申請">{insights.pet?.otherActiveApplications ?? 0} 份</Row>
            <Row label="和小孩相處">{goodWithLabel(goodWith.children)}</Row>
            <Row label="和其他寵物相處">{goodWithLabel(goodWith.otherPets)}</Row>
            <Row label="活動量">{ACTIVITY[pet?.personality?.activityLevel] || '未填'}</Row>
          </dl>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="font-medium text-gray-900 mb-2">申請人概況</p>
          <dl>
            <Row label="另有進行中的申請">{applicant?.otherActiveApplications ?? 0} 份</Row>
            <Row label="曾在平台完成認養">{applicant?.completedAdoptions ?? 0} 次</Row>
            <Row label="配對檔案">{applicant?.matchingProfileFilled ? '已填' : '未填'}</Row>
            <Row label="配對分數">{match ? `${match.score} 分（${match.label}）` : '沒有配對檔案，無法計算'}</Row>
          </dl>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 p-4">
        <p className="font-medium text-gray-900 mb-2">需要確認的事項</p>
        {checks.length ? (
          <ul className="space-y-2">
            {checks.map((c) => (
              <li key={c.message} className="flex items-start gap-2 text-sm">
                {c.level === 'warning' ? (
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-red-600" aria-hidden="true" />
                ) : (
                  <Info className="w-4 h-4 mt-0.5 shrink-0 text-blue-600" aria-hidden="true" />
                )}
                <span className={c.level === 'warning' ? 'text-red-700' : 'text-gray-700'}>
                  <span className="sr-only">{c.level === 'warning' ? '條件衝突：' : '請確認：'}</span>
                  {c.message}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-600">申請表和動物資料沒有發現需要特別確認的地方。</p>
        )}
      </div>

      <p className="mt-2 text-xs text-gray-500">
        以上由規則比對申請表與動物資料產生，沒有使用 AI，只供參考，是否核准由你決定。
        配對分數是動物和申請人配對檔案的契合度，不是對申請人的評價。
      </p>
    </section>
  );
};

export default ReviewInsights;
