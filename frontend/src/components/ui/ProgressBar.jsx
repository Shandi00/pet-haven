import React from 'react';
import PropTypes from 'prop-types';

/**
 * ProgressBar 進度條元件
 * 顏色與 Button 的 primary 相同；帶 role="progressbar"，螢幕閱讀器和 Playwright 都能讀到目前進度
 */
const ProgressBar = ({ value, max = 100, label, className = '' }) => {
  const safeValue = Math.min(Math.max(value, 0), max);
  const percent = max > 0 ? (safeValue / max) * 100 : 0;

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={safeValue}
      aria-label={label}
      className={`w-full h-2 bg-gray-200 rounded-full overflow-hidden ${className}`}
    >
      <div
        className="h-full bg-primary-500 rounded-full transition-all duration-300"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
};

ProgressBar.propTypes = {
  value: PropTypes.number.isRequired,
  max: PropTypes.number,
  label: PropTypes.string,
  className: PropTypes.string,
};

export default ProgressBar;
