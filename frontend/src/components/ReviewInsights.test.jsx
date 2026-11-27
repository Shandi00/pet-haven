import React from 'react';
import { render, screen } from '@testing-library/react';
import ReviewInsights from './ReviewInsights';

const pet = { name: '小白', adoptionStatus: 'pending', personality: { activityLevel: 'high', goodWith: { children: false } } };
const insights = (extra = {}) => ({
  pet: { otherActiveApplications: 1 },
  applicant: { otherActiveApplications: 2, completedAdoptions: 0, matchingProfileFilled: false },
  match: null,
  checks: [],
  source: 'rule',
  ...extra,
});

// 欄位名稱（dt）對應的值（dd），用角色查詢，不直接走 DOM
const rows = () => {
  const values = screen.getAllByRole('definition').map((d) => d.textContent);
  return Object.fromEntries(screen.getAllByRole('term').map((t, i) => [t.textContent, values[i]]));
};

test('沒有 reviewInsights（申請人自己看）時不顯示', () => {
  const { container } = render(<ReviewInsights insights={undefined} pet={pet} />);
  expect(container).toBeEmptyDOMElement();
});

test('顯示寵物狀態、申請人概況，並標示是規則產生', () => {
  render(<ReviewInsights insights={insights()} pet={pet} />);
  expect(screen.getByRole('heading', { name: '審核輔助' })).toBeInTheDocument();
  expect(rows()).toMatchObject({
    目前狀態: '審核中', 其他進行中的申請: '1 份', 和小孩相處: '不適合', 和其他寵物相處: '未填', 活動量: '高',
    另有進行中的申請: '2 份', 曾在平台完成認養: '0 次', 配對檔案: '未填', 配對分數: '沒有配對檔案，無法計算',
  });
  expect(screen.getByText('申請表和動物資料沒有發現需要特別確認的地方。')).toBeInTheDocument();
  expect(screen.getByText(/沒有使用 AI/)).toHaveTextContent('是否核准由你決定');
});

test('列出確認事項並區分衝突與待確認，顯示配對分數', () => {
  render(<ReviewInsights pet={pet} insights={insights({
    match: { score: 72, label: '絕佳配對' },
    checks: [
      { level: 'warning', message: '申請表填有 2 位兒童，小白標示不適合有小孩的家庭' },
      { level: 'info', message: '小白活動量高，申請人住公寓且沒有院子，請確認每天的運動安排' },
    ],
  })} />);
  const items = screen.getAllByRole('listitem');
  expect(items[0]).toHaveTextContent('條件衝突：申請表填有 2 位兒童');
  expect(items[1]).toHaveTextContent('請確認：小白活動量高');
  expect(rows().配對分數).toBe('72 分（絕佳配對）');
});
