const { chromium } = require('playwright');
const fs = require('fs/promises');
const path = require('path');

const FE_BASE = process.env.QA_FE_BASE || 'http://127.0.0.1:3100';
const API_BASE = process.env.QA_API_BASE || 'http://127.0.0.1:8100';
const KC_URL = process.env.KEYCLOAK_URL || 'https://auth.silvergem.org';
const KC_REALM = process.env.KEYCLOAK_REALM || 'aminra';
const KC_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID || 'aminra-frontend';
const DEMO_PW = process.env.DEMO_PW || 'DemoP@ss2026';
const OUT = process.env.QA_OUT || '/home/user/Documents/aminra-docker-system/docs/qa/2026-09-08-crud-users-org-editor-business/evidence';

async function tokenFor(email, password = DEMO_PW) {
  const params = new URLSearchParams({ grant_type: 'password', client_id: KC_CLIENT_ID, username: email, password });
  const res = await fetch(`${KC_URL}/realms/${KC_REALM}/protocol/openid-connect/token`, { method: 'POST', body: params });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.access_token) throw new Error(`token failed for ${email}: ${res.status} ${body.error || ''}`);
  return body.access_token;
}

async function profileFor(token) {
  const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`/auth/me failed: ${res.status}`);
  return body;
}

async function newAuthedPage(browser, label, email, expectedMarkers, routes) {
  const token = await tokenFor(email);
  const user = await profileFor(token);
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  await context.addInitScript(({ t, u }) => {
    window.localStorage.setItem('aminra_user_token', t);
    window.localStorage.setItem('aminra_user_profile', JSON.stringify(u));
  }, { t: token, u: user });
  const page = await context.newPage();
  const consoleErrors = [];
  const failedResponses = [];
  page.on('console', (msg) => { if (['error'].includes(msg.type())) consoleErrors.push(msg.text().slice(0, 500)); });
  page.on('response', (res) => {
    const s = res.status();
    if (s >= 400 && /\/api\//.test(res.url())) failedResponses.push({ status: s, url: res.url().replace(/[?].*/, '') });
  });

  const routeResults = [];
  for (const route of routes) {
    const resp = await page.goto(`${FE_BASE}${route.path}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2000);
    const bodyText = (await page.locator('body').innerText({ timeout: 10000 }).catch(() => '')).slice(0, 3000);
    const markersOk = route.markers.every((m) => bodyText.includes(m));
    const shot = path.join(OUT, 'screenshots', `${label}-${route.name}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    routeResults.push({ route: route.path, httpStatus: resp ? resp.status() : null, markersOk, expectedMarkers: route.markers, screenshot: shot, bodyExcerpt: bodyText.slice(0, 400) });
  }

  await context.close();
  return { role: label, email, expectedMarkers, user: { role: user.role, is_owner: user.is_owner, status: user.status }, routeResults, consoleErrors, failedResponses };
}

(async () => {
  await fs.mkdir(path.join(OUT, 'screenshots'), { recursive: true });
  await fs.mkdir(path.join(OUT, 'raw'), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    results.push(await newAuthedPage(browser, 'business', 'biz-demo-1@demo.aminra.vn', [], [
      { name: 'settings-company', path: '/settings/company', markers: ['Thông tin doanh nghiệp'] },
      { name: 'members', path: '/members', markers: ['Internal Halal Committee', 'Mời thành viên'] },
    ]));
    results.push(await newAuthedPage(browser, 'provider', 'cb-demo@demo.aminra.vn', [], [
      { name: 'auditors', path: '/auditors', markers: ['Quản lý Auditor', 'Thêm Auditor'] },
      { name: 'portfolio', path: '/portfolio', markers: ['Doanh nghiệp'] },
    ]));
    results.push(await newAuthedPage(browser, 'auditor', 'auditor-demo@demo.aminra.vn', [], [
      { name: 'dashboard-auditor', path: '/dashboard/provider', markers: ['Auditor'] },
    ]));
  } finally {
    await browser.close();
  }
  const failed = [];
  for (const r of results) {
    for (const rr of r.routeResults) {
      if (!rr.markersOk || rr.httpStatus >= 400) failed.push({ role: r.role, route: rr.route, httpStatus: rr.httpStatus, markersOk: rr.markersOk, expectedMarkers: rr.expectedMarkers });
    }
    if (r.consoleErrors.length) failed.push({ role: r.role, consoleErrors: r.consoleErrors });
    if (r.failedResponses.length) failed.push({ role: r.role, failedResponses: r.failedResponses });
  }
  const summary = { totalRoutes: results.reduce((n, r) => n + r.routeResults.length, 0), passedRoutes: results.reduce((n, r) => n + r.routeResults.filter(x => x.markersOk && (!x.httpStatus || x.httpStatus < 400)).length, 0), failed, results };
  const outPath = path.join(OUT, 'raw', 'browser-role-pages-smoke.json');
  await fs.writeFile(outPath, JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ totalRoutes: summary.totalRoutes, passedRoutes: summary.passedRoutes, failed: summary.failed }, null, 2));
  if (summary.failed.length) process.exit(1);
})().catch(async (err) => {
  await fs.mkdir(path.join(OUT, 'raw'), { recursive: true });
  await fs.writeFile(path.join(OUT, 'raw', 'browser-role-pages-smoke-error.txt'), String(err && err.stack || err));
  console.error(String(err && err.stack || err));
  process.exit(1);
});
