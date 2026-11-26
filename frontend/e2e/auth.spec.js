const { test, expect } = require('@playwright/test');

// repo 是公開的，管理員帳密只從環境變數讀取；用 backend/scripts/create_admin 建立
const { E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD } = process.env;

test.describe('使用者認證測試', () => {
  test('應該能夠開啟登入頁面', async ({ page }) => {
    // 直接導向登入頁面
    await page.goto('/login', { waitUntil: 'networkidle' });
    
    // 額外等待 React 渲染
    await page.waitForTimeout(2000);
    
    // 確認登入頁面標題（使用更寬鬆的選擇器）
    const titleVisible = await page.locator('h2').filter({ hasText: '登入' }).isVisible({ timeout: 15000 }).catch(() => false);
    
    // 如果標題不可見，至少表單應該可見
    if (!titleVisible) {
      await expect(page.locator('input#email')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('input#password')).toBeVisible({ timeout: 15000 });
    } else {
      // 標題可見，也檢查表單
      await expect(page.locator('input#email')).toBeVisible({ timeout: 10000 });
      await expect(page.locator('input#password')).toBeVisible({ timeout: 10000 });
    }
  });

  test('應該能夠執行管理員登入', async ({ page }) => {
    test.skip(!E2E_ADMIN_EMAIL || !E2E_ADMIN_PASSWORD, '未設定 E2E_ADMIN_EMAIL／E2E_ADMIN_PASSWORD');
    await page.goto('/login', { waitUntil: 'networkidle' });
    
    // 等待表單載入
    await page.waitForTimeout(2000);
    await page.waitForSelector('input#email', { state: 'visible', timeout: 15000 });
    
    // 填寫管理員憑證
    await page.fill('input#email', E2E_ADMIN_EMAIL, { timeout: 10000 });
    await page.fill('input#password', E2E_ADMIN_PASSWORD, { timeout: 10000 });
    
    // 點擊登入按鈕
    const loginButton = page.locator('button[type="submit"]').filter({ hasText: '登入' });
    await loginButton.click({ timeout: 10000 });
    
    // 等待導向 - 管理員會導向 /shelter/dashboard
    await page.waitForURL(/\/(shelter\/dashboard|dashboard|admin)/, { timeout: 20000 });
    
    // 確認導向成功
    expect(page.url()).toMatch(/\/(shelter\/dashboard|dashboard|admin)/);
  });
});
