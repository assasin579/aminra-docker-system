import { expect, test } from "@playwright/test";
import { keycloakClientId, keycloakTokenUrl, requireKeycloakUserToken } from "./helpers/auth-token";

const EVIDENCE_DIR = process.env.UAT_EVIDENCE_DIR || "../../docs/qa/tmp-module-guard/evidence";
const BUSINESS_EMAIL = process.env.PW_BIZ_EMAIL || process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const BUSINESS_PASSWORD = process.env.PW_BIZ_PASSWORD || process.env.DEMO_PW;
const TARGET_INDUSTRY_CODE = process.env.UAT_INDUSTRY_CODE || "restaurant_hotel";
const ADMIN_EMAIL = process.env.TEST_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.TEST_ADMIN_PASSWORD;

async function requireAdminToken(request: any): Promise<string> {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "admin credentials not configured (TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD)");
  const tokenUrl = keycloakTokenUrl();
  const forwarded = /(^http:\/\/127\.0\.0\.1|^http:\/\/localhost|^http:\/\/keycloak[:/])/.test(tokenUrl)
    ? {
        "X-Forwarded-Proto": process.env.KEYCLOAK_PUBLIC_PROTO || "https",
        "X-Forwarded-Host": process.env.KEYCLOAK_PUBLIC_HOST || "auth.aminra.org",
        "X-Forwarded-Port": process.env.KEYCLOAK_PUBLIC_PORT || "443",
      }
    : undefined;
  const login = await request.post(tokenUrl, {
    headers: forwarded,
    form: {
      grant_type: "password",
      client_id: keycloakClientId(),
      username: ADMIN_EMAIL as string,
      password: ADMIN_PASSWORD as string,
    },
  });
  expect(login.ok(), `admin token grant failed: ${login.status()}`).toBeTruthy();
  const body = await login.json();
  expect(body.access_token).toBeTruthy();
  return body.access_token;
}

async function rejectPendingActivationRequests(request: any, adminToken: string, tenantId: string, moduleCode: string) {
  const response = await request.get(
    `/api/auth/admin/module-activation-requests?tenant_id=${encodeURIComponent(tenantId)}&status=pending`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = await response.json();
  for (const item of body.requests || []) {
    if (item.module_code !== moduleCode) continue;
    const review = await request.patch(`/api/auth/admin/module-activation-requests/${item.id}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { action: "reject", admin_note: "Browser UAT cleanup before rerun" },
    });
    expect(review.ok(), await review.text()).toBeTruthy();
  }
}

async function jsonOrText(response: { json: () => Promise<unknown>; text: () => Promise<string> }) {
  try {
    return await response.json();
  } catch {
    return await response.text();
  }
}

test("business end-user modules page and scoped guards work after enablement", async ({ page, request }) => {
  test.skip(!BUSINESS_PASSWORD, "business demo password not configured");

  const token = await requireKeycloakUserToken(request, {
    email: BUSINESS_EMAIL,
    password: BUSINESS_PASSWORD as string,
  });

  const meResponse = await request.get("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(meResponse.ok(), await meResponse.text()).toBeTruthy();
  const me = await meResponse.json();
  expect(me.role).toBe("business");
  expect(me.tenant_id).toBeTruthy();

  const adminToken = await requireAdminToken(request);
  await rejectPendingActivationRequests(request, adminToken, me.tenant_id, "process_digitization");

  let modulesResponse = await request.get("/api/api/me/modules", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(modulesResponse.ok(), await modulesResponse.text()).toBeTruthy();
  let modulesPayload = await modulesResponse.json();

  if (!modulesPayload.business_model || (modulesPayload.modules || []).length === 0) {
    const schemaResponse = await request.get(`/api/industry-schemas/${TARGET_INDUSTRY_CODE}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(schemaResponse.ok(), await schemaResponse.text()).toBeTruthy();
    const schema = await schemaResponse.json();
    const selectResponse = await request.post("/api/industry-schemas/business-select", {
      headers: { Authorization: `Bearer ${token}` },
      data: { schema_id: schema.id },
    });
    expect(selectResponse.ok(), JSON.stringify(await jsonOrText(selectResponse))).toBeTruthy();

    modulesResponse = await request.get("/api/api/me/modules", {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(modulesResponse.ok(), await modulesResponse.text()).toBeTruthy();
    modulesPayload = await modulesResponse.json();
  }

  expect(modulesPayload.business_model?.code).toBeTruthy();
  expect(modulesPayload.modules.length).toBeGreaterThan(0);
  const byCode = Object.fromEntries(modulesPayload.modules.map((module: any) => [module.code, module]));
  expect(["enabled", "trial"]).toContain(byCode.supplier_management?.status);
  expect(["disabled", "locked"]).toContain(byCode.traceability?.status);
  expect(["disabled", "locked"]).toContain(byCode.process_digitization?.status);

  const materialResponse = await request.get("/api/api/supply-chain/materials", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(materialResponse.status(), await materialResponse.text()).toBe(200);

  const processResponse = await request.get("/api/api/supply-chain/processes", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(processResponse.status(), await processResponse.text()).toBe(403);
  expect(await processResponse.text()).toContain("MODULE_DISABLED:process_digitization");

  const batchResponse = await request.get("/api/api/supply-chain/batches", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(batchResponse.status(), await batchResponse.text()).toBe(403);
  expect(await batchResponse.text()).toContain("MODULE_DISABLED:traceability");

  await page.addInitScript(({ tokenValue, profile }) => {
    window.localStorage.setItem("aminra_user_token", tokenValue);
    window.localStorage.setItem("aminra_user_profile", JSON.stringify(profile));
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, { tokenValue: token, profile: me });

  await page.goto("/modules");
  await expect(page.getByRole("heading", { name: /Gói module của tôi/i })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Business model:/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Quản lý nhà cung cấp" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Số hóa quy trình" })).toBeVisible();
  await expect(page.getByText(/Chưa kích hoạt|Đang khóa/i).first()).toBeVisible();
  await page.screenshot({ path: `${EVIDENCE_DIR}/01-business-my-modules.png`, fullPage: true });

  await page.goto("/supply-chain/process");
  await expect(page.getByRole("heading", { name: /Module chưa kích hoạt/i })).toBeVisible({ timeout: 15000 });
  await expect(page.locator("p", { hasText: /^Số hóa quy trình$/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Xem gói module của tôi/i })).toBeVisible();
  const activationButton = page.getByRole("button", { name: /Yêu cầu kích hoạt Số hóa quy trình/i });
  await expect(activationButton).toBeEnabled();
  await activationButton.click();
  await expect(page.getByRole("status")).toContainText("Đã gửi yêu cầu kích hoạt");
  await page.screenshot({ path: `${EVIDENCE_DIR}/02-disabled-process-direct-url-requested.png`, fullPage: true });

  const pendingResponse = await request.get(
    `/api/auth/admin/module-activation-requests?tenant_id=${encodeURIComponent(me.tenant_id)}&status=pending`,
    { headers: { Authorization: `Bearer ${adminToken}` } },
  );
  expect(pendingResponse.ok(), await pendingResponse.text()).toBeTruthy();
  const pendingBody = await pendingResponse.json();
  const requested = (pendingBody.requests || []).find((item: any) => item.module_code === "process_digitization");
  expect(requested, JSON.stringify(pendingBody)).toBeTruthy();
  expect(requested.sla_due_at).toBeTruthy();
  expect(["open", "overdue"]).toContain(requested.sla_state);
  expect(requested.notification_count).toBeGreaterThan(0);

  await page.addInitScript((tokenValue) => {
    window.localStorage.setItem("aminra_user_token", tokenValue);
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, adminToken);
  await page.goto("/admin");
  await page.getByRole("button", { name: "Tenant modules" }).click();
  await expect(page.getByRole("heading", { name: "Tenant module console" })).toBeVisible({ timeout: 15000 });
  await page.getByLabel("Tenant ID").fill(me.tenant_id);
  await page.getByRole("button", { name: "Tải yêu cầu kích hoạt" }).click();
  await expect(page.getByRole("heading", { name: "Yêu cầu kích hoạt đang chờ" })).toBeVisible({ timeout: 15000 });
  await expect(page.locator("section[data-module-activation-requests='true']")).toContainText("process_digitization");
  await expect(page.locator("section[data-module-activation-requests='true']")).toContainText("Đã báo operator:");
  await expect(page.locator("section[data-module-activation-requests='true']")).toContainText(/SLA/);
  await page.screenshot({ path: `${EVIDENCE_DIR}/03-admin-activation-request-queue.png`, fullPage: true });
  await page.getByRole("button", { name: "Từ chối process_digitization" }).click();
  await expect(page.getByRole("status")).toContainText("Đã từ chối yêu cầu process_digitization");
  await page.screenshot({ path: `${EVIDENCE_DIR}/04-admin-activation-request-rejected.png`, fullPage: true });
});
