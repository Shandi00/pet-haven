import React, { useId } from 'react';
import PropTypes from 'prop-types';

const Textarea = ({ label, error, helperText, fullWidth = false, rows = 4, className = '', id, ...props }) => {
  const baseStyles = 'px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors resize-vertical';
  const errorStyles = error ? 'border-red-500' : 'border-gray-300';
  const widthClass = fullWidth ? 'w-full' : '';
  // label 要對到輸入框，螢幕報讀和 Playwright 才能用文字找到它
  const autoId = useId();
  const fieldId = id || autoId;

  return (
    <div className={`${widthClass} ${className}`}>
      {label && <label htmlFor={fieldId} className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}
      <textarea id={fieldId} rows={rows} className={`${baseStyles} ${errorStyles} ${widthClass}`} {...props} />
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      {helperText && !error && <p className="mt-1 text-sm text-gray-500">{helperText}</p>}
    </div>
  );
};

Textarea.propTypes = {
  label: PropTypes.string,
  error: PropTypes.string,
  helperText: PropTypes.string,
  fullWidth: PropTypes.bool,
  rows: PropTypes.number,
  className: PropTypes.string,
  id: PropTypes.string,
};

export default Textarea;
