import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Pagination from './Pagination';

const showPager = (currentPage, totalPages) => {
  const onPageChange = jest.fn();
  render(<Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={onPageChange} />);
  return onPageChange;
};

test('標示目前頁，第一頁不能按上一頁', () => {
  const onPageChange = showPager(1, 3);
  expect(screen.getByRole('navigation', { name: '分頁' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '第 1 頁' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('button', { name: '上一頁' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: '下一頁' }));
  expect(onPageChange).toHaveBeenCalledWith(2);
});

test('頁數多時中間用省略號，最後一頁不能按下一頁', () => {
  const onPageChange = showPager(10, 10);
  expect(screen.getAllByRole('button', { name: /^第 \d+ 頁$/ }).map((b) => b.textContent)).toEqual(['1', '7', '8', '9', '10']);
  expect(screen.getByRole('button', { name: '下一頁' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: '第 7 頁' }));
  expect(onPageChange).toHaveBeenCalledWith(7);
});
