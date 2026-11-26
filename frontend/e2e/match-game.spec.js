const { test, expect } = require('@playwright/test');

// 配對小遊戲（T10）
// 登入帳號從環境變數帶入，不寫在程式裡；需要一般使用者（user）帳號，變數名稱見 frontend/.env.example。
const email = process.env.E2E_USER_EMAIL;
const password = process.env.E2E_USER_PASSWORD;

test.describe('配對小遊戲', () => {
  test.skip(!email || !password, '請先設定環境變數 E2E_USER_EMAIL、E2E_USER_PASSWORD（一般使用者帳號）');

  test('答完 8 題後看到毛孩類型與「看推薦」按鈕', async ({ page }) => {
    await page.goto('/login?redirect=/match-game', { waitUntil: 'networkidle' });
    // 後端還沒有 PUT /api/matching/profile/game（後端計畫 Task 4），先用假資料開關保存遊戲結果；
    // 三支既有的配對檔案 API 仍然打真的後端
    await page.evaluate(() => window.localStorage.setItem('useMockData', 'true'));

    await page.fill('input#email', email);
    await page.fill('input#password', password);
    await page.locator('button[type="submit"]').filter({ hasText: '登入' }).click();
    await page.waitForURL('**/match-game', { timeout: 20000 });

    for (let i = 1; i <= 8; i += 1) {
      await expect(page.getByText(`第 ${i} 題／共 8 題`)).toBeVisible();
      await page.getByRole('group').getByRole('button').first().click();
    }

    // 每題都選第一個選項，結果是戶外冒險型（見 docs/features/配對遊戲題目對照表.md 的計分範例）
    await expect(page.getByRole('heading', { name: '戶外冒險型' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: '看推薦' })).toBeVisible();
    // 推薦頁 /recommendations 由 Task 4 新增；完成後在這裡補上「點看推薦 → 網址變成 /recommendations」
  });
});
