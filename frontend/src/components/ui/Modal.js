import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import PropTypes from 'prop-types';

const Modal = ({ isOpen, onClose, title, children, footer, size = 'md' }) => {
  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };
  const titleId = useId();
  const panelRef = useRef(null);
  // 呼叫端每次 render 都會給新的 onClose；用 ref 避免開著的時候焦點被重設
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return undefined;
    const previous = document.activeElement;
    document.body.style.overflow = 'hidden';
    // 開啟時焦點移進視窗（有輸入框就到輸入框），按 Esc 關閉，關閉後焦點回到原本的按鈕
    // shortcut: 沒有鎖住 Tab 焦點，按 Tab 可能跑到背後的頁面；要更完整時改用 focus-trap
    const panel = panelRef.current;
    (panel.querySelector('textarea, input, select') || panel).focus();
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = 'unset';
      previous?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // 掛在 body 下：頁面內容自成一層，放在頁面裡會被上方選單和小幫手按鈕蓋住
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        className={`relative bg-white rounded-lg shadow-xl ${sizeClasses[size]} w-full mx-4 max-h-[90vh] flex flex-col focus:outline-none`}
      >
        {title && (
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <h3 id={titleId} className="text-xl font-semibold text-gray-800">{title}</h3>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="關閉"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}
        <div className="p-6 overflow-y-auto">{children}</div>
        {footer && <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200">{footer}</div>}
      </div>
    </div>,
    document.body
  );
};

Modal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string,
  children: PropTypes.node.isRequired,
  footer: PropTypes.node,
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl']),
};

export default Modal;
