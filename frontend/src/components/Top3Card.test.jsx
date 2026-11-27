import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Top3Card from './Top3Card';

const item = (reason = {}) => ({
  pet: { _id: 'p1', name: '小黑', species: 'dog', breed: '米克斯', age: { value: 2, unit: 'years' }, size: 'medium', activityLevel: 'high', photo: '' },
  score: 92,
  matchLevel: 'perfect',
  reason: { summary: '小黑活動量高，和你的作息相符。', highlights: ['活動量相符'], cautions: [], source: 'ai', ...reason },
});

const renderCard = (props = {}) => {
  const onLike = vi.fn();
  const onDislike = vi.fn();
  render(<Top3Card item={item()} onLike={onLike} onDislike={onDislike} {...props} />);
  return { onLike, onDislike };
};

test('顯示動物、分數、理由與 AI 標示', () => {
  renderCard();
  expect(screen.getByRole('heading', { name: '小黑' })).toBeInTheDocument();
  expect(screen.getByText('92')).toBeInTheDocument();
  expect(screen.getByText('小黑活動量高，和你的作息相符。')).toBeInTheDocument();
  expect(screen.getByText('活動量相符')).toBeInTheDocument();
  expect(screen.getByText(/AI 依你的配對檔案/)).toBeInTheDocument();
  expect(screen.queryByText(/目前使用規則推薦/)).not.toBeInTheDocument();
});

test('reason.source 是 rule 時顯示「目前使用規則推薦」，不標示 AI', () => {
  render(<Top3Card item={item({ source: 'rule' })} onLike={vi.fn()} onDislike={vi.fn()} />);
  expect(screen.getByText(/目前使用規則推薦/)).toBeInTheDocument();
  expect(screen.queryByText(/AI 依你的配對檔案/)).not.toBeInTheDocument();
});

test('有 cautions 時顯示「注意事項」區塊，沒有時不顯示', () => {
  const { unmount } = render(<Top3Card item={item({ cautions: ['住公寓需留意吠叫'] })} onLike={vi.fn()} onDislike={vi.fn()} />);
  expect(screen.getByText('注意事項')).toBeInTheDocument();
  expect(screen.getByText('住公寓需留意吠叫')).toBeInTheDocument();
  unmount();
  renderCard();
  expect(screen.queryByText('注意事項')).not.toBeInTheDocument();
});

test('按鈕把動物交給 onLike／onDislike；disabled 時兩個按鈕都不能點', () => {
  const { onLike, onDislike } = renderCard();
  fireEvent.click(screen.getByRole('button', { name: '小黑 不適合' }));
  fireEvent.click(screen.getByRole('button', { name: '小黑 適合' }));
  expect(onDislike).toHaveBeenCalledWith(expect.objectContaining({ _id: 'p1' }));
  expect(onLike).toHaveBeenCalledWith(expect.objectContaining({ _id: 'p1' }));
});

test('disabled 為 true 時，「不適合」與「適合」按鈕都停用', () => {
  renderCard({ disabled: true });
  expect(screen.getByRole('button', { name: '小黑 不適合' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '小黑 適合' })).toBeDisabled();
});
