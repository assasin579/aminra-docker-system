import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3100';
const DEMO_PW = process.env.DEMO_PW || 'DemoP@ss2026';
const ADMIN_PW = process.env.ADMIN_DEMO_PW || DEMO_PW;
const outDir = path.resolve('docs/qa/2026-09-07-login-all-account-types/evidence/screenshots');
await fs.mkdir(outDir, { recursive: true });

const accounts = [
  { label: 'business', start: '/business/login', username: 'biz-demo-1@demo.aminra.vn', password: DEMO_PW, expectUrl: /dashboard\/business|business|auth\/callback/ },
  { label: 'cb_provider', start: '/provider/login', username: 'cb-demo@demo.aminra.vn', password: DEMO_PW, expectUrl: /dashboard\/provider|provider|auth\/callback/ },
  { label: 'auditor', start: '/provider/login', username: 'auditor-demo@demo.aminra.vn', password: DEMO_PW, expectUrl: /dashboard\/provider|audits|auth\/callback/ },
  { label: 'platform_admin', start: '/admin', username: 'admin', password: ADMIN_PW, expectUrl: /admin|auth\/callback/ },
];

async function runOne(acct) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 300)); });
  const result = { label: acct.label, username: acct.username, start: acct.start, status: 'UNKNOWN', finalUrl: null, consoleErrors };
  try {
    await page.goto(BASE + acct.start, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    if (/auth\.silvergem\.org|localhost:8180/.test(page.url())) {
      await page.locator('input#username, input[name="username"]').fill(acct.username, { timeout: 15000 });
      await page.locator('input#password, input[name="password"]').fill(acct.password, { timeout: 15000 });
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => null),
        page.locator('input#kc-login, button[type="submit"], input[type="submit"]').click(),
      ]);
      await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    }
    result.finalUrl = page.url().replace(/code=[^&]+/g, 'code=[REDACTED]').replace(/state=[^&]+/g, 'state=[REDACTED]');
    await page.screenshot({ path: path.join(outDir, `${acct.label}.png`), fullPage: true });
    const storage = await page.evaluate(() => ({
      userToken: Boolean(localStorage.getItem('aminra_user_token')),
      adminToken: Boolean(localStorage.getItem('aminra_admin_token')),
      userProfile: Boolean(localStorage.getItem('aminra_user_profile')),
      adminProfile: Boolean(localStorage.getItem('aminra_admin_profile')),
      bodyText: document.body.innerText.slice(0, 500),
    })).catch(e => ({ error: String(e) }));
    result.storage = storage;
    const loginErrorVisible = await page.locator('.kc-feedback-text, #input-error, .pf-v5-c-alert, .alert-error').first().textContent({ timeout: 1000 }).catch(() => null);
    if (loginErrorVisible) result.loginErrorText = loginErrorVisible.trim().slice(0, 300);
    const hasUserSession = Boolean(storage.userToken && storage.userProfile);
    const hasAdminSession = Boolean(storage.adminToken || storage.adminProfile || /Admin Panel|Quản trị hệ thống|Dashboard Admin/i.test(storage.bodyText || ''));
    result.status = acct.label === 'platform_admin'
      ? (hasAdminSession && !/Bạn cần đăng nhập|Đăng nhập Admin \(Keycloak SSO\)/i.test(storage.bodyText || '') ? 'PASS' : 'FAIL')
      : (hasUserSession && !loginErrorVisible ? 'PASS' : 'FAIL');
  } catch (e) {
    result.status = 'ERROR';
    result.error = String(e).slice(0, 1000);
    await page.screenshot({ path: path.join(outDir, `${acct.label}-error.png`), fullPage: true }).catch(() => {});
  } finally {
    await context.close();
    await browser.close();
  }
  return result;
}

const results = [];
for (const acct of accounts) results.push(await runOne(acct));
const out = { startedAt: new Date().toISOString(), base: BASE, results };
await fs.writeFile('docs/qa/2026-09-07-login-all-account-types/browser-login-smoke-results.json', JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 2));
if (results.some(r => r.status !== 'PASS')) process.exit(1);
