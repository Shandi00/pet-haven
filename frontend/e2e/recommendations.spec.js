const { test, expect } = require('@playwright/test');

// Top 3 推薦與 AI 小幫手（T15）
// 用假資料模式（aiMock.js）跑，結果固定；登入帳號從環境變數帶入，變數名稱見 frontend/.env.example。
const email = process.env.E2E_USER_EMAIL;
const password = process.env.E2E_USER_PASSWORD;

async function loginTo(page, path) {
  await page.goto(`/login?redirect=${encodeURIComponent(path)}`, { waitUntil: 'networkidle' });
  await page.evaluate(() => window.localStorage.setItem('useMockData', 'true'));
  await page.fill('input#email', email);
  await page.fill('input#password', password);
  await page.locator('button[type="submit"]').filter({ hasText: '登入' }).click();
  await page.waitForURL(`**${path}`, { timeout: 20000 });
}

const cardHeadings = (page) => page.locator('main h3');

test.describe('Top 3 推薦與 AI 小幫手（假資料模式）', () => {
  test.skip(!email || !password, '請先設定環境變數 E2E_USER_EMAIL、E2E_USER_PASSWORD（一般使用者帳號）');

  test.afterEach(async ({ page }) => {
    await page.evaluate(() => window.localStorage.removeItem('useMockData'));
  });

  test('按「不適合」換一批並顯示已避開，全部避開後可以重新開始', async ({ page }) => {
    await loginTo(page, '/recommendations');
    await expect(cardHeadings(page)).toHaveCount(3);

    const first = await cardHeadings(page).first().innerText();
    await page.getByRole('button', { name: `${first} 不適合` }).click();
    await expect(page.getByText(`已避開：${first}`)).toBeVisible();
    await expect(page.getByRole('heading', { name: first, exact: true })).toHaveCount(0);

    // 一直按「不適合」直到沒有卡片
    while (await cardHeadings(page).count()) {
      const name = await cardHeadings(page).first().innerText();
      await page.getByRole('button', { name: `${name} 不適合` }).click();
      await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
    }
    await expect(page.getByText('目前沒有符合條件的毛孩')).toBeVisible();
    await page.getByRole('button', { name: '重新開始' }).click();
    await expect(cardHeadings(page)).toHaveCount(3);
  });

  test('小幫手回答附來源，醫療問題提醒就醫', async ({ page }) => {
    await loginTo(page, '/recommendations');
    await page.getByRole('button', { name: '問小幫手' }).click();
    const chat = page.getByRole('dialog', { name: 'AI 小幫手' });

    await chat.getByLabel('輸入問題').fill('第一次養貓要準備什麼');
    await chat.getByRole('button', { name: '送出' }).click();
    await expect(chat.getByText('新手養貓準備清單')).toBeVisible({ timeout: 10000 });

    await chat.getByLabel('輸入問題').fill('我的貓一直嘔吐怎麼辦');
    await chat.getByRole('button', { name: '送出' }).click();
    await expect(chat.getByText(/獸醫/)).toBeVisible({ timeout: 10000 });
    await expect(chat.getByText('規則回覆（未使用 AI）')).toBeVisible();
  });
});
