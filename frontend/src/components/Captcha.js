import React, { useEffect, useRef } from 'react';

// 登入與註冊的人機驗證（Cloudflare Turnstile）。沒設定 REACT_APP_TURNSTILE_SITE_KEY 時不顯示、也不需要 token，
// 後端同樣在沒設定 TURNSTILE_SECRET_KEY 時不驗證（開發與 CI）。
const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
const siteKey = () => process.env.REACT_APP_TURNSTILE_SITE_KEY;
export const isCaptchaEnabled = () => Boolean(siteKey());

let scriptPromise;
const loadScript = () => {
  if (window.turnstile) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = SCRIPT_URL;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => {
        scriptPromise = null; // 下次再試
        reject(new Error('captcha script failed'));
      };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
};

// onToken 會收到驗證通過的 token；過期或出錯時收到空字串。token 只能用一次，送出失敗後父層換 key 重新載入
const Captcha = ({ onToken }) => {
  const box = useRef(null);
  const key = siteKey();

  useEffect(() => {
    if (!key) return undefined;
    let widgetId;
    let cancelled = false;
    loadScript()
      .then(() => {
        if (cancelled || !box.current || !window.turnstile) return;
        widgetId = window.turnstile.render(box.current, {
          sitekey: key,
          language: 'zh-tw',
          callback: (token) => onToken(token),
          'expired-callback': () => onToken(''),
          'error-callback': () => onToken(''),
        });
      })
      .catch(() => onToken(''));
    return () => {
      cancelled = true;
      if (widgetId !== undefined) window.turnstile?.remove(widgetId);
    };
  }, [key, onToken]);

  if (!key) return null;
  return <div ref={box} className="flex justify-center" aria-label="人機驗證" />;
};

export default Captcha;
