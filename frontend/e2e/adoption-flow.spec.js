// T17 展示主線後半：認養者送出申請 → 收容所審核通過 → 完成認養 → 認養者看到狀態更新。
// 需要前後端都在執行，且已跑過 `npm run seed`（收容所帳號 shelter@example.com 與 8 隻動物）。
// 每次執行建立一個新的認養者帳號；結束時把用到的動物改回「待認養」，讓下次與展示仍可使用。
const { test, expect, request: pwRequest } = require('@playwright/test');

const API = 'http://localhost:5000/api/';
// seed 測試帳號，只用在本機與 CI（見 AGENTS.md / backend/seed.py）
// 展示機會設定 SEED_SHELTER_PASSWORD；沒設定時用 seed 的預設密碼（只在本機與 CI）
const SHELTER = { email: 'shelter@example.com', password: process.env.SEED_SHELTER_PASSWORD || 'shelter123' };

const stamp = Date.now();
const ADOPTER = {
  username: `e2e${stamp}`,
  email: `e2e-adopter-${stamp}@example.test`,
  password: 'E2eAdopt1',
  firstName: 'E2E',
  lastName: 'Adopter',
};

let api;
let shelterToken;
let adopterToken;
let pet; // { _id, name, tags }
let adoptionId;

async function uiLogin(page, { email, password }) {
  await page.goto('/login');
  await page.fill('input#email', email);
  await page.fill('input#password', password);
  await page.locator('button[type="submit"]').filter({ hasText: '登入' }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
}

// 申請表的 <label> 沒有 htmlFor，getByLabel 找不到；改用「label 後面的欄位」
const fieldAfter = (page, label) =>
  page.locator('label', { hasText: label }).locator('xpath=following-sibling::*[1]');
const checkboxBefore = (page, label) =>
  page.locator('label', { hasText: label }).locator('xpath=preceding-sibling::input[@type="checkbox"]');
// /my-applications 的單筆卡片（新認養者只有這一筆）；last() 取最內層符合的 div
const adopterCard = (page, petName) => page.locator('div')
  .filter({ has: page.getByRole('link', { name: petName, exact: true }) })
  .filter({ has: page.getByRole('link', { name: '查看寵物詳情' }) })
  .last();

test.describe.serial('認養流程：申請 → 審核通過 → 完成 → 認養者看到狀態', () => {
  test.beforeAll(async () => {
    api = await pwRequest.newContext({ baseURL: API });

    const reg = await api.post('auth/register', { data: ADOPTER });
    expect(reg.status(), await reg.text()).toBe(201);
    adopterToken = (await reg.json()).token;

    const login = await api.post('auth/login', { data: SHELTER });
    expect(login.ok(), '收容所登入失敗，請先執行 npm run seed').toBeTruthy();
    const { token, user } = await login.json();
    shelterToken = token;

    // 只挑收容所自己、目前「待認養」的動物（其他狀態後端會拒絕新申請）
    const list = await api.get('pets', { params: { createdBy: user._id, limit: 50 } });
    const { pets } = await list.json();
    expect(pets.length, '收容所沒有待認養的動物，請執行 npm run seed').toBeGreaterThan(0);
    pet = { _id: pets[0]._id, name: pets[0].name, tags: pets[0].tags || [] };
  });

  test.afterAll(async () => {
    // 完成認養會把動物改成 adopted；改回 available 與原本的標籤，讓下次執行與展示仍可用
    if (pet && shelterToken) {
      await api.put(`pets/${pet._id}`, {
        headers: { Authorization: `Bearer ${shelterToken}` },
        data: { adoptionStatus: 'available', tags: pet.tags },
      });
    }
    await api?.dispose();
  });

  test('認養者送出申請，收容所通過，認養者看到已通過，完成認養', async ({ browser }) => {
    test.setTimeout(120000);

    // 1. 認養者在 /adopt/:petId 填完四步驟表單並送出（UI）
    const adopterCtx = await browser.newContext();
    const adopter = await adopterCtx.newPage();
    await uiLogin(adopter, ADOPTER);
    await adopter.goto(`/adopt/${pet._id}`);
    await expect(adopter.getByRole('heading', { name: '認養申請' })).toBeVisible();
    await expect(adopter.getByText(`您正在申請認養：${pet.name}`)).toBeVisible();

    // 個資欄位一律用明顯的假資料
    await fieldAfter(adopter, '姓名').fill('E2E 測試');
    // emergencyContact.email 沿用舊版規則，只接受 2–3 碼的網域結尾，.test 會被拒絕，所以表單 Email 用 .com
    await fieldAfter(adopter, '電子郵件').fill(`e2e${stamp}@example.com`);
    await fieldAfter(adopter, '聯絡電話').fill('0900000000');
    await fieldAfter(adopter, '年齡').fill('30');
    await fieldAfter(adopter, '職業').fill('測試員');
    await adopter.getByRole('button', { name: '下一步' }).click();

    await expect(adopter.getByRole('heading', { name: '居住環境' })).toBeVisible();
    await fieldAfter(adopter, '住宅類型').selectOption('apartment');
    await fieldAfter(adopter, '住宅所有權').selectOption('rented');
    await fieldAfter(adopter, '居住地址').fill('測試路1號');
    await fieldAfter(adopter, '家庭成員人數').fill('1');
    await adopter.getByRole('button', { name: '下一步' }).click();

    await expect(adopter.getByRole('heading', { name: '養寵經驗' })).toBeVisible();
    await checkboxBefore(adopter, '無養寵物經驗').check();
    await adopter.getByRole('button', { name: '下一步' }).click();

    await expect(adopter.getByRole('heading', { name: '照顧計畫' })).toBeVisible();
    await fieldAfter(adopter, '每日可陪伴時間').selectOption('3-5');
    await fieldAfter(adopter, '獸醫照護計畫').fill('定期健康檢查與預防針（E2E 測試）');
    await fieldAfter(adopter, '認養原因').fill('E2E 測試申請');
    await fieldAfter(adopter, '緊急聯絡人').fill('測試聯絡人');
    await fieldAfter(adopter, '緊急聯絡電話').fill('0900000001');

    const applyResp = adopter.waitForResponse(
      (r) => r.url().includes(`/api/adoptions/apply/${pet._id}`) && r.request().method() === 'POST');
    await adopter.getByRole('button', { name: '提交申請' }).click();
    const resp = await applyResp;
    expect(resp.status(), await resp.text()).toBe(201);
    adoptionId = (await resp.json()).data.adoption._id;
    await expect(adopter.getByText('認養申請已提交').first()).toBeVisible();

    // 2. 收容所在 /my-pets-applications 找到這筆申請並按「通過」（UI）
    const shelterCtx = await browser.newContext();
    const shelter = await shelterCtx.newPage();
    await uiLogin(shelter, SHELTER);
    await shelter.goto('/my-pets-applications');
    await expect(shelter.getByRole('heading', { name: '收到的認養申請' })).toBeVisible();
    // 申請者帳號每次都是新的，可以唯一定位到這張卡片；last() 取最內層符合的 div
    const card = shelter.locator('div')
      .filter({ hasText: `申請者: ${ADOPTER.username}` })
      .filter({ has: shelter.getByRole('button', { name: '查看申請詳情' }) })
      .last();
    await expect(card).toContainText('待審核');
    await card.getByRole('button', { name: '通過' }).click();
    await expect(shelter.getByText('審核完成').first()).toBeVisible();
    await expect(card).toContainText('已通過');
    await expect(card.getByRole('button', { name: '通過' })).toHaveCount(0);

    // 認養者在 /my-applications 看到狀態變成「已通過」（UI）
    await adopter.goto('/my-applications');
    await expect(adopter.getByRole('heading', { name: '我的認養申請' })).toBeVisible();
    await expect(adopterCard(adopter, pet.name)).toContainText('已通過');

    // 3. 收容所在同一張卡片按「完成認養」並確認（UI）
    shelter.once('dialog', (d) => d.accept());
    const completeResp = shelter.waitForResponse(
      (r) => r.url().includes(`/api/adoptions/${adoptionId}/complete`) && r.request().method() === 'POST');
    await card.getByRole('button', { name: '完成認養' }).click();
    const done = await completeResp;
    expect(done.status(), await done.text()).toBe(200);
    await expect(shelter.getByText('已完成認養').first()).toBeVisible();
    await expect(card).toContainText('已完成');
    await expect(card.getByRole('button', { name: '完成認養' })).toHaveCount(0);
    const mine = await api.get('adoptions/my-applications', {
      headers: { Authorization: `Bearer ${adopterToken}` } });
    expect((await mine.json()).applications.find((a) => a._id === adoptionId)?.status).toBe('completed');

    await adopterCtx.close();
    await shelterCtx.close();
  });

  // 4. 完成後認養者在 /my-applications 看到「已完成」（UI）。
  test('認養者在我的認養申請看到「已完成」', async ({ page }) => {
    await uiLogin(page, ADOPTER);
    await page.goto('/my-applications');
    const card = adopterCard(page, pet.name);
    await expect(card).toBeVisible();
    await expect(card).toContainText('已完成', { timeout: 5000 });
  });
});
