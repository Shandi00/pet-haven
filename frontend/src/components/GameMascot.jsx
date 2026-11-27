import React from 'react';
import PropTypes from 'prop-types';
import { Dog } from 'lucide-react';

/**
 * 配對小遊戲的小狗角色與對話框：遊戲頁（T10）與推薦頁沒玩過遊戲時的提示共用。
 * bounceKey 改變時小狗會跳一下（重新掛載以重播動畫），用來回應使用者的選擇。
 */
const GameMascot = ({ children, size = 'md', bounceKey }) => {
  const large = size === 'lg';
  return (
    <div className="flex items-start gap-3 sm:gap-4">
      <div
        key={bounceKey}
        aria-hidden="true"
        className={`shrink-0 rounded-full bg-primary-500 text-white flex items-center justify-center shadow-sm motion-safe:animate-hop ${
          large ? 'w-16 h-16' : 'w-12 h-12'
        }`}
      >
        <Dog className={large ? 'w-9 h-9' : 'w-7 h-7'} />
      </div>
      <div className="relative min-w-0 flex-1 rounded-2xl bg-primary-50 px-4 py-3 text-gray-900">
        <span aria-hidden="true" className={`absolute -left-1.5 h-3 w-3 rotate-45 bg-primary-50 ${large ? 'top-6' : 'top-4'}`} />
        {children}
      </div>
    </div>
  );
};

GameMascot.propTypes = {
  children: PropTypes.node.isRequired,
  size: PropTypes.oneOf(['md', 'lg']),
  bounceKey: PropTypes.string,
};

export default GameMascot;
