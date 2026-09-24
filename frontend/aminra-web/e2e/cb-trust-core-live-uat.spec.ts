import { expect, test } from "@playwright/test";
import { requireKeycloakUserToken } from "./helpers/auth-token";

const EVIDENCE_DIR = process.env.UAT_EVIDENCE_DIR || "../../docs/qa/tmp-cb-trust-browser-uat/evidence";
const PROVIDER_EMAIL = process.env.PW_PROVIDER_EMAIL || "cb-demo@demo.aminra.vn";
const PROVIDER_PASSWORD = process.env.PW_PROVIDER_PASSWORD || process.env.PROVIDER_DEMO_PW || process.env.DEMO_PW;
const BUSINESS_EMAIL = process.env.PW_BIZ_EMAIL || process.env.DEMO_BUSINESS_EMAIL || "biz-demo-1@demo.aminra.vn";
const BUSINESS_PASSWORD = process.env.PW_BIZ_PASSWORD || process.env.DEMO_PW;

async function tokenFor(request: any, email: string, password?: string): Promise<string> {
  test.skip(!password, `Keycloak password not configured for ${email}`);
  return requireKeycloakUserToken(request, { email, password: password as string });
}

async function authGet(request: any, path: string, token: string) {
  return request.get(path, { headers: { Authorization: `Bearer ${token}` } });
}

async function authPost(request: any, path: string, token: string, data: unknown) {
  return request.post(path, { headers: { Authorization: `Bearer ${token}` }, data });
}

test("qa-cb-trust credentialed workflow proves conflicts, complaints, decisions, and UI markers", async ({ page, request }) => {
  const providerToken = await tokenFor(request, PROVIDER_EMAIL, PROVIDER_PASSWORD);
  const businessToken = await tokenFor(request, BUSINESS_EMAIL, BUSINESS_PASSWORD);

  const providerMeResponse = await authGet(request, "/api/auth/me", providerToken);
  expect(providerMeResponse.ok(), await providerMeResponse.text()).toBeTruthy();
  const providerMe = await providerMeResponse.json();
  expect(providerMe.role, JSON.stringify(providerMe)).toBe("provider");
  expect(providerMe.tenant_id, JSON.stringify(providerMe)).toBeTruthy();
  expect(providerMe.id || providerMe.user_id || providerMe.sub, JSON.stringify(providerMe)).toBeTruthy();
  const providerUserId = String(providerMe.id || providerMe.user_id || providerMe.sub);
  const providerTenantId = String(providerMe.tenant_id);

  const businessMeResponse = await authGet(request, "/api/auth/me", businessToken);
  expect(businessMeResponse.ok(), await businessMeResponse.text()).toBeTruthy();
  const businessMe = await businessMeResponse.json();
  expect(businessMe.role, JSON.stringify(businessMe)).toBe("business");
  expect(businessMe.tenant_id, JSON.stringify(businessMe)).toBeTruthy();
  const businessTenantId = String(businessMe.tenant_id);

  const unauthConflicts = await request.get("/api/api/conflicts");
  expect(unauthConflicts.status(), await unauthConflicts.text()).toBe(401);

  const businessCannotListConflicts = await authGet(request, "/api/api/conflicts", businessToken);
  expect(businessCannotListConflicts.status(), await businessCannotListConflicts.text()).toBe(403);

  const conflictDescription = `qa-cb-trust ${Date.now()} prior consultancy`;
  const declareConflict = await authPost(request, "/api/api/conflicts", providerToken, {
    business_tenant: businessTenantId,
    person_user_id: providerUserId,
    person_role: "decision_maker",
    conflict_type: "consultancy",
    description: conflictDescription,
  });
  expect(declareConflict.ok(), await declareConflict.text()).toBeTruthy();
  const conflict = await declareConflict.json();
  expect(conflict.status).toBe("declared");
  expect(conflict.description).toBe(conflictDescription);

  const conflictList = await authGet(
    request,
    `/api/api/conflicts?business_tenant=${encodeURIComponent(businessTenantId)}&status=declared`,
    providerToken,
  );
  expect(conflictList.ok(), await conflictList.text()).toBeTruthy();
  const conflictListBody = await conflictList.json();
  expect((conflictListBody.conflicts || []).some((item: any) => item.id === conflict.id)).toBeTruthy();

  const blockConflict = await authPost(request, `/api/api/conflicts/${conflict.id}/review`, providerToken, {
    status: "blocked",
    review_reason: "qa-cb-trust confirms unresolved conflict blocks until owner override",
  });
  expect(blockConflict.ok(), await blockConflict.text()).toBeTruthy();
  expect((await blockConflict.json()).status).toBe("blocked");

  const overrideConflict = await authPost(request, `/api/api/conflicts/${conflict.id}/override`, providerToken, {
    override_reason: "qa-cb-trust mitigation approved by provider owner for sandbox UAT",
  });
  expect(overrideConflict.ok(), await overrideConflict.text()).toBeTruthy();
  expect((await overrideConflict.json()).status).toBe("overridden");

  const complaintTitle = `qa-cb-trust complaint ${Date.now()}`;
  const createComplaint = await authPost(request, "/api/api/complaints", businessToken, {
    provider_id: providerTenantId,
    case_type: "complaint_service",
    source: "business",
    title: complaintTitle,
    description: "Credentialed browser UAT complaint lifecycle proof.",
  });
  expect(createComplaint.ok(), await createComplaint.text()).toBeTruthy();
  const complaint = await createComplaint.json();
  expect(complaint.status).toBe("received");
  expect(complaint.title).toBe(complaintTitle);

  const businessComplaintList = await authGet(request, "/api/api/complaints", businessToken);
  expect(businessComplaintList.ok(), await businessComplaintList.text()).toBeTruthy();
  const businessComplaintBody = await businessComplaintList.json();
  expect((businessComplaintBody.cases || []).some((item: any) => item.id === complaint.id)).toBeTruthy();

  const providerComplaintList = await authGet(request, "/api/api/complaints", providerToken);
  expect(providerComplaintList.ok(), await providerComplaintList.text()).toBeTruthy();
  const providerComplaintBody = await providerComplaintList.json();
  expect((providerComplaintBody.cases || []).some((item: any) => item.id === complaint.id)).toBeTruthy();

  const assignComplaint = await authPost(request, `/api/api/complaints/${complaint.id}/assign`, providerToken, {
    owner_id: providerUserId,
    notes: "qa-cb-trust assigns provider owner for sandbox UAT",
  });
  expect(assignComplaint.ok(), await assignComplaint.text()).toBeTruthy();
  expect((await assignComplaint.json()).assigned_owner_id).toBe(providerUserId);

  const acknowledgeComplaint = await authPost(request, `/api/api/complaints/${complaint.id}/transition`, providerToken, {
    to_status: "acknowledged",
    notes: "qa-cb-trust acknowledged",
  });
  expect(acknowledgeComplaint.ok(), await acknowledgeComplaint.text()).toBeTruthy();
  expect((await acknowledgeComplaint.json()).status).toBe("acknowledged");

  const businessCannotCreateDecision = await authPost(request, "/api/api/certification-decisions", businessToken, {
    submission_id: "00000000-0000-4000-8000-000000000001",
    notes: "business must not create CB decision cases",
  });
  expect(businessCannotCreateDecision.status(), await businessCannotCreateDecision.text()).toBe(403);

  const missingDecision = await authGet(
    request,
    "/api/api/certification-decisions/submission/00000000-0000-4000-8000-000000000001",
    providerToken,
  );
  expect([404, 403]).toContain(missingDecision.status());

  await page.goto("/conflicts");
  await expect(page.getByRole("heading", { name: "Conflict-of-Interest Register" })).toBeVisible({ timeout: 15000 });
  await expect(page.locator("[data-marker='unresolved-conflicts-block']")).toBeVisible();
  await expect(page.locator("form[data-api-path='/api/conflicts'][data-method='POST']")).toBeVisible();
  await page.screenshot({ path: `${EVIDENCE_DIR}/01-conflict-register-page.png`, fullPage: true });

  await page.goto("/complaints");
  await expect(page.getByRole("heading", { name: "Complaints & Appeals" })).toBeVisible({ timeout: 15000 });
  await expect(page.locator("[data-marker='independent-appeal-handler']")).toBeVisible();
  await expect(page.locator("[data-testid='closure-reason-required']")).toBeVisible();
  await page.screenshot({ path: `${EVIDENCE_DIR}/02-complaints-appeals-page.png`, fullPage: true });
});
