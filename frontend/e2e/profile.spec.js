const { test, expect } = require('@playwright/test');

// 個人中心「配對檔案」分頁（T09）
// 登入帳號從環境變數帶入，不寫在程式裡；需要一般使用者（user）帳號，變數名稱見 frontend/.env.example。
// 測試會改寫這個帳號的生活方式檔案，請用測試帳號。
const email = process.env.E2E_USER_EMAIL;
const password = process.env.E2E_USER_PASSWORD;

async function loginTo(page, path) {
  await page.goto(`/login?redirect=${encodeURIComponent(path)}`, { waitUntil: 'networkidle' });
  await page.fill('input#email', email);
  await page.fill('input#password', password);
  await page.locator('button[type="submit"]').filter({ hasText: '登入' }).click();
  await page.waitForURL('**/profile?tab=matching', { timeout: 20000 });
}

// 表單的 label 沒有連到下拉選單，改用選項值找到對應的選單
const activitySelect = (page) => page.locator('select:has(option[value="high"])');
const timeSelect = (page) => page.locator('select:has(option[value="extensive"])');
const housingSelect = (page) => page.locator('select:has(option[value="house-with-yard"])');

test.describe('配對檔案分頁', () => {
  test.skip(!email || !password, '請先設定環境變數 E2E_USER_EMAIL、E2E_USER_PASSWORD（一般使用者帳號）');

  test('生活方式儲存後重新整理，活動量仍然是「高」', async ({ page }) => {
    await loginTo(page, '/profile?tab=matching');

    await page.getByRole('button', { name: '手動修改配對檔案' }).click(); // 表單預設收起
    await page.getByRole('button', { name: '生活方式', exact: true }).click();
    // 三個欄位都填了才能儲存
    await activitySelect(page).selectOption('high');
    await timeSelect(page).selectOption('moderate');
    await housingSelect(page).selectOption('apartment');
    await page.getByRole('button', { name: '儲存生活方式', exact: true }).click();
    await expect(page.getByText('生活方式檔案已儲存')).toBeVisible();

    await page.reload();
    await page.getByRole('button', { name: '手動修改配對檔案' }).click();
    await expect(activitySelect(page)).toHaveValue('high');
  });

  test('從配對檔案分頁前往配對小遊戲', async ({ page }) => {
    await loginTo(page, '/profile?tab=matching');

    // 沒玩過是「去玩配對遊戲」，玩過是「再玩一次」
    await page.getByRole('button', { name: /^(去玩配對遊戲|再玩一次)$/ }).click();
    await expect(page).toHaveURL(/\/match-game$/);
  });
});
