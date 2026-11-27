import React from 'react';
import { render, waitFor } from '@testing-library/react';
import Captcha, { isCaptchaEnabled } from './Captcha';

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.turnstile;
});

test('沒設定 site key 時不顯示，也不需要驗證', () => {
  const { container } = render(<Captcha onToken={vi.fn()} />);
  expect(container).toBeEmptyDOMElement();
  expect(isCaptchaEnabled()).toBe(false);
});

test('有 site key 時載入驗證元件，通過後交出 token，卸載時移除', async () => {
  vi.stubEnv('REACT_APP_TURNSTILE_SITE_KEY', 'site-key');
  window.turnstile = {
    render: vi.fn((el, options) => {
      options.callback('token-1');
      return 'widget-1';
    }),
    remove: vi.fn(),
  };
  const onToken = vi.fn();
  const { unmount } = render(<Captcha onToken={onToken} />);
  expect(isCaptchaEnabled()).toBe(true);
  await waitFor(() => expect(onToken).toHaveBeenCalledWith('token-1'));
  expect(window.turnstile.render.mock.calls[0][1].sitekey).toBe('site-key');
  unmount();
  expect(window.turnstile.remove).toHaveBeenCalledWith('widget-1');
});

test('驗證過期時把 token 清空', async () => {
  vi.stubEnv('REACT_APP_TURNSTILE_SITE_KEY', 'site-key');
  window.turnstile = { render: vi.fn((el, options) => options['expired-callback']()), remove: vi.fn() };
  const onToken = vi.fn();
  render(<Captcha onToken={onToken} />);
  await waitFor(() => expect(onToken).toHaveBeenCalledWith(''));
});
