import React from 'react';

// 配對小遊戲結果揭曉時的彩帶，只播一次；使用者設定減少動態效果時不顯示。
// 位置、延遲、飄移距離用編號算出固定值，不用亂數，畫面每次都一樣、測試也穩定。
const COLORS = ['bg-primary-500', 'bg-primary-300', 'bg-primary-700', 'bg-gray-800', 'bg-primary-200'];

const Confetti = ({ pieces = 28 }) => (
  <div aria-hidden="true" className="pointer-events-none absolute inset-0 hidden overflow-hidden motion-safe:block">
    {Array.from({ length: pieces }, (_, i) => (
      <span
        key={i}
        className={`absolute top-0 block h-2.5 w-1.5 rounded-sm opacity-0 animate-confetti ${COLORS[i % COLORS.length]}`}
        style={{
          left: `${(i * 37) % 100}%`,
          animationDelay: `${(i % 7) * 0.07}s`,
          '--drift': `${((i * 53) % 80) - 40}px`,
        }}
      />
    ))}
  </div>
);

export default Confetti;
