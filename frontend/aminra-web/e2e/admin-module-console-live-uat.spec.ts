import { expect, test } from "@playwright/test";
import { keycloakClientId, keycloakTokenUrl } from "./helpers/auth-token";

const EVIDENCE_DIR = process.env.UAT_EVIDENCE_DIR || "../../docs/qa/tmp-module-admin/evidence";
const ADMIN_EMAIL = process.env.TEST_ADMIN_EMAIL;
const ADMIN_PASSWORD = process.env.TEST_ADMIN_PASSWORD;
const TENANT_ID = process.env.UAT_TENANT_ID;

async function requireAdminToken(request: any): Promise<string> {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "admin credentials not configured");
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

test("admin module console loads tenant module package through live admin API", async ({ page, request }) => {
  test.skip(!TENANT_ID, "UAT_TENANT_ID not configured");
  const token = await requireAdminToken(request);

  const apiResponse = await request.get(`/api/auth/admin/tenants/${encodeURIComponent(TENANT_ID as string)}/modules`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(apiResponse.ok(), await apiResponse.text()).toBeTruthy();
  const payload = await apiResponse.json();
  expect(payload.business_model?.code).toBeTruthy();
  expect(payload.modules?.length).toBeGreaterThan(0);

  await page.addInitScript((tokenValue) => {
    window.localStorage.setItem("aminra_user_token", tokenValue);
    document.cookie = "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
  }, token);

  await page.goto("/admin");
  await page.getByRole("button", { name: "Tenant modules" }).click();
  await expect(page.getByRole("heading", { name: "Tenant module console" })).toBeVisible({ timeout: 15000 });
  await page.getByLabel("Tenant ID").fill(TENANT_ID as string);
  await page.getByRole("button", { name: "Tải module" }).click();
  await expect(page.getByText(/Business model:/i)).toBeVisible({ timeout: 15000 });
  await expect(page.locator("code", { hasText: "supplier_management" })).toBeVisible();
  await expect(page.locator("code", { hasText: "process_digitization" })).toBeVisible();
  await expect(page.getByTestId("module-status-process_digitization")).toBeVisible();
  await page.screenshot({ path: `${EVIDENCE_DIR}/03-admin-tenant-module-console.png`, fullPage: true });
});
