# Gate 1 Unsupervised Customer Onboarding Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task. Follow strict TDD: no production code or harness code without a failing test first.

**Goal:** Make AMINRA Gate 1 ready for scoped unsupervised customer onboarding: a customer can self-register or accept an invite, verify email, log in, recover password, enter the correct portal, complete the first-value workflow, and receive clear validation/authorization errors without manual database/Keycloak intervention.

**Architecture:** Treat onboarding as a product contract, not a smoke check. Add a customer-perspective acceptance matrix, fail-first unit/integration/E2E tests, then patch backend/frontend/config only where tests expose gaps. Separate source tests, live runtime tests, browser tests, SMTP/Keycloak tests, and final evidence report.

**Tech Stack:** FastAPI backend, Keycloak/OIDC, PostgreSQL, Next.js frontend (`frontend/aminra-web`), Playwright E2E, Pytest, Docker Compose local/public runtime, Resend/SMTP production email path.

---

## 0. Customer Role Assumptions and Non-Negotiable Experience Bar

### Primary customer personas

1. **Business owner / halal applicant**
   - Wants to sign up, verify email, enter the business portal, understand what to do next, create/update first business-critical records, and see clear validation errors.
2. **Certification Body / provider admin**
   - Wants to log in, see only provider-owned work, perform permitted certificate/authority operations, and never see false success.
3. **Auditor / sub-user**
   - Wants to access assigned work only, with clear forbidden messages when outside scope.
4. **Platform admin support**
   - Wants to recover accounts, reset password, inspect status, and unblock a customer without DB surgery.

### Customer satisfaction requirements

A customer should say:

- “I know where I am and what to do next.”
- “When I make a mistake, the system tells me exactly how to fix it.”
- “Email verification and password reset work the first time.”
- “I never see a fake success message.”
- “I cannot accidentally access the wrong company/provider data.”
- “The output I see — certificate/demo/trace/status — matches the promised state.”

### Gate 1 DONE definition

Gate 1 is DONE only when:

- New-user verify email live path passes.
- Password reset live path passes.
- Business, provider/CB, and auditor login/landing role routes pass.
- First-value workflow passes for approved Gate 1 scope.
- Invalid input and forbidden access produce clear user-facing errors.
- No false success on backend non-2xx or network failure.
- Full desktop Chromium matrix returns 0 failed after changes.
- Evidence report exists under `docs/qa/YYYYMMDD-gate1-onboarding/`.
- Any skipped/deferred tests are classified and do not hide P0/P1 onboarding risk.

---

## 1. Implementation Rules

### TDD protocol for every task

For each behavior change:

1. Write a focused failing test first.
2. Run the exact focused test and confirm RED for the expected reason.
3. Implement the smallest safe fix.
4. Run the focused test and confirm GREEN.
5. Run the relevant regression pack.
6. Update evidence.
7. Commit only after user authorization.

### Evidence directory

Create:

```text
docs/qa/20260917-gate1-onboarding/
  report.md
  status.tsv
  acceptance-matrix.md
  evidence/
    terminal/
    screenshots/
    raw/
    network/
    console/
```

### Status vocabulary

- `PASS`: verified with evidence.
- `FAIL`: product behavior failed.
- `WARN`: non-blocking but must be tracked.
- `BLOCKED`: cannot run due missing credential/env/external dependency.
- `DEFERRED`: intentionally out of Gate 1 scope; must not affect Gate 1 claim.

---

## 2. Customer Acceptance Matrix

### Task 1: Create Gate 1 acceptance matrix

**Objective:** Lock scope before writing code so tests reflect customer value, not implementation convenience.

**Files:**
- Create: `docs/qa/20260917-gate1-onboarding/acceptance-matrix.md`
- Create: `docs/qa/20260917-gate1-onboarding/status.tsv`

**Customer requirements to encode:**

- Business owner can self-register or be invited.
- Verification email arrives and link completes activation.
- Password reset email arrives and resets the password.
- Login routes user to the correct portal.
- Portal shows an obvious next step.
- Wrong email/password shows clear error and no stale profile.
- Unverified user sees clear verification-required message.
- Suspended/disabled user cannot continue and sees support guidance.
- Business cannot access provider/admin routes.
- Provider cannot access other provider-owned authority data.
- Auditor cannot access unassigned tenant/provider data.
- Forms catch invalid input before or at backend with user-readable errors.
- Successful output matches expected data state.

**Step 1: Write the matrix**

Include columns:

```text
ID | Persona | Flow | Requirement | Positive expected | Negative expected | Evidence | Priority | Status
```

**Step 2: Add initial status ledger rows**

Use rows like:

```tsv
domain	status	step	evidence	note
scope	PASS	G1-SCOPE acceptance matrix created	docs/qa/20260917-gate1-onboarding/acceptance-matrix.md	Gate 1 scope locked before code
```

**Verification:**

```bash
test -f docs/qa/20260917-gate1-onboarding/acceptance-matrix.md
test -f docs/qa/20260917-gate1-onboarding/status.tsv
```

Expected: both commands exit `0`.

---

## 3. Email Verification and Password Reset

### Task 2: Add live-email verification contract test

**Objective:** Prove a newly onboarded user can receive and complete verification without manual intervention.

**Files:**
- Test: `frontend/aminra-web/e2e/41-gate1-onboarding-email.spec.ts`
- Possible helper: `frontend/aminra-web/e2e/helpers/email-capture.ts`
- Possible backend/helper script: `scripts/qa/gate1_onboarding_smoke.py`

**RED test cases:**

1. `business user receives verify email and becomes login-eligible`
2. `expired or already-used verification link shows clear message`
3. `unverified user sees verification-required guidance`
4. `email send failure surfaces actionable retry/support message`

**Step 1: Write failing Playwright test**

Pseudo-contract:

```ts
test('business user receives verify email and becomes login-eligible', async ({ page }) => {
  const email = `gate1-business-${Date.now()}@demo.aminra.vn`;
  await page.goto(`${baseURL}/business/register`);
  await fillBusinessRegistration(page, { email, password: qaPassword, companyName: 'Gate1 Demo Co' });
  await expect(page.getByText(/kiểm tra email|verify your email/i)).toBeVisible();

  const verifyUrl = await waitForVerifyEmailUrl(email);
  await page.goto(verifyUrl);
  await expect(page.getByText(/xác minh thành công|email verified/i)).toBeVisible();

  await page.goto(`${baseURL}/business/login`);
  await loginViaKeycloak(page, email, qaPassword);
  await expect(page).toHaveURL(/business/);
  await expect(page.getByText(/Gate1 Demo Co|dashboard|hồ sơ/i)).toBeVisible();
});
```

**Step 2: Run RED**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/41-gate1-onboarding-email.spec.ts --project=chromium --grep "receives verify email" --reporter=line
```

Expected RED: missing test helper, missing route support, email capture missing, or product behavior gap. The failure must be classified.

**Step 3: Implement minimal helper/product fix**

Allowed fixes only if test proves need:

- Add helper to read test email via approved test mailbox/capture mechanism.
- Normalize success/error copy.
- Ensure Keycloak execute-actions-email uses canonical `auth.aminra.org` and frontend callback.
- Ensure frontend displays verification-required states.

**Step 4: Run GREEN**

Same command. Expected: `1 passed`.

**Regression:**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/02-auth.spec.ts e2e/keycloak/02-login-ui-flow.spec.ts e2e/41-gate1-onboarding-email.spec.ts --project=chromium --reporter=line
```

---

### Task 3: Add password reset live contract

**Objective:** Prove customers can recover without platform-admin/manual DB intervention.

**Files:**
- Test: `frontend/aminra-web/e2e/41-gate1-onboarding-email.spec.ts`
- Existing related test: `frontend/aminra-web/e2e/12-cuj-password-reset.spec.ts`

**RED test cases:**

1. `existing business user completes password reset and old password fails`
2. `nonexistent email shows non-enumerating confirmation copy`
3. `weak replacement password is rejected with clear policy`
4. `used reset link cannot be reused`

**Step 1: Write failing tests**

Assert:

- Request reset does not leak whether account exists.
- Email arrives for valid account.
- Reset link accepts strong password.
- Old password returns login failure.
- New password logs in.
- Weak password shows Keycloak policy in readable form.

**Step 2: Run RED**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/41-gate1-onboarding-email.spec.ts --project=chromium --grep "password reset" --reporter=line
```

Expected: fail until helpers/product states are wired.

**Step 3: Minimal fix**

- Patch reset UX copy if unclear.
- Patch error mapper if Keycloak policy errors are cryptic.
- Ensure stale AMINRA/OIDC local/session storage is cleared after reset when applicable.

**Step 4: GREEN + regression**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/12-cuj-password-reset.spec.ts e2e/41-gate1-onboarding-email.spec.ts --project=chromium --reporter=line
```

---

## 4. Role Landing and Session Correctness

### Task 4: Canonical role login and landing tests

**Objective:** Ensure each persona lands in the right place and does not see stale/incorrect identity.

**Files:**
- Test: `frontend/aminra-web/e2e/42-gate1-role-landing.spec.ts`
- Existing helpers: `frontend/aminra-web/e2e/helpers/auth-token.ts`
- Related backend test: `backend/tests/test_role_boundaries_live_smoke.py`

**RED test cases:**

1. `business login lands on business dashboard with business next step`
2. `provider login lands on provider dashboard with provider-owned work only`
3. `auditor login lands on assigned auditor workspace only`
4. `logout then login as different role never shows stale profile/sidebar`
5. `disabled user cannot enter app and sees support guidance`

**Step 1: Write failing Playwright tests**

Use existing credential env names; do not print secrets.

**Step 2: Run RED**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/42-gate1-role-landing.spec.ts --project=chromium --reporter=line
```

Expected: fails for missing spec/helper or behavior gap.

**Step 3: Minimal fix**

Potential areas:

- Frontend auth state purge before login.
- Role-specific route after `/auth/me` verification.
- Clear support copy for disabled/unverified states.
- Sidebar/menu role markers.

**Step 4: GREEN + backend role-boundary regression**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/42-gate1-role-landing.spec.ts e2e/22-token-isolation.spec.ts e2e/23-cross-context-logout.spec.ts --project=chromium --reporter=line

cd ../../backend
pytest tests/test_role_boundaries_live_smoke.py -q
```

---

## 5. First-Value Workflow: Business Customer

### Task 5: Business first-value workflow E2E

**Objective:** A business customer can complete the first meaningful workflow and see correct output.

**Recommended Gate 1 scope:** Use deterministic QA business data, not real customer legal documents yet.

**Files:**
- Test: `frontend/aminra-web/e2e/43-gate1-business-first-value.spec.ts`
- Existing related tests:
  - `frontend/aminra-web/e2e/03-business-flow.spec.ts`
  - `frontend/aminra-web/e2e/10-supply-chain.spec.ts`
  - `frontend/aminra-web/e2e/40-supply-chain-create-contracts.spec.ts`
- Backend related routes:
  - `backend/supply_chain/material_router.py`
  - `backend/supply_chain/process_router.py`

**Customer acceptance flow:**

1. Login as business.
2. See clear dashboard/next step.
3. Create or update company/profile baseline if required.
4. Create/select eligible supplier/material.
5. Create process/batch where Gate 1 allows.
6. See saved record in list/detail.
7. Invalid fields show inline/actionable error.
8. Backend rejection never shows success toast.

**RED test cases:**

1. `business can create first material/process/batch and see persisted detail`
2. `missing required field shows inline error and save is blocked`
3. `invalid supplier eligibility is rejected with clear message`
4. `backend 4xx detail array is rendered as readable Vietnamese/English copy`
5. `network failure or 500 does not close modal and does not show success`

**Step 1: Write source/component contract where possible**

If existing component tests exist, add fail-first tests for error mapping and no false success.

Search target before implementation:

```bash
cd frontend/aminra-web
npm test -- --run --reporter=verbose
```

Then add focused tests in existing `__tests__` files or a new one if needed.

**Step 2: Write Playwright RED**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/43-gate1-business-first-value.spec.ts --project=chromium --reporter=line
```

**Step 3: Minimal fix**

Likely allowed fixes:

- Use shared API client consistently for write actions.
- Normalize FastAPI error shapes.
- Keep modal/form open on failure.
- Add durable `data-testid` markers for customer-critical states.
- Patch validation copy.

**Step 4: Regression**

```bash
cd frontend/aminra-web
npm run lint
npm run build
PW_BASE_URL=https://aminra.org npx playwright test e2e/03-business-flow.spec.ts e2e/10-supply-chain.spec.ts e2e/40-supply-chain-create-contracts.spec.ts e2e/43-gate1-business-first-value.spec.ts --project=chromium --reporter=line

cd ../../backend
pytest tests/test_supply_chain_*.py tests/test_unauth_route_boundaries.py -q
```

Expected: 0 failed; skipped tests classified.

---

## 6. First-Value Workflow: Provider/CB Customer

### Task 6: Provider/CB first-value workflow E2E

**Objective:** Provider can complete approved Gate 1 authority/cert operation and output matches expected state.

**Files:**
- Test: `frontend/aminra-web/e2e/44-gate1-provider-first-value.spec.ts`
- Existing related:
  - `frontend/aminra-web/e2e/04-provider-flow.spec.ts`
  - `frontend/aminra-web/e2e/14-cuj-cert-lifecycle.spec.ts`
  - `frontend/aminra-web/e2e/18-mvp-demo-provider-admin.spec.ts`
- Backend related:
  - `backend/auth/certificate_router.py`
  - `backend/services/cert_lifecycle.py`

**Customer acceptance flow:**

1. Login as provider/CB.
2. See provider-owned queue/workspace.
3. Perform allowed certificate/authority action.
4. See updated status/output.
5. Forbidden cross-provider action fails closed.
6. Invalid state transition shows clear error.

**RED test cases:**

1. `provider sees only provider-owned submissions/certificates`
2. `provider allowed state transition persists and renders correct status`
3. `provider cannot mutate another provider authority record`
4. `invalid transition shows clear error and no false success`
5. `public certificate output matches approved state`

**Step 1: Backend RED for authority boundaries**

```bash
cd backend
pytest tests/test_cert_lifecycle_integration.py::test_provider_cannot_mutate_other_provider_certificate -q
```

If test does not exist, add it first and watch fail.

**Step 2: Playwright RED**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/44-gate1-provider-first-value.spec.ts --project=chromium --reporter=line
```

**Step 3: Minimal fix**

- Patch route filters or frontend reader only if tests prove leakage or incorrect output.
- Patch error handling/copy for invalid transitions.

**Step 4: Regression**

```bash
cd backend
pytest tests/test_cert_lifecycle_integration.py tests/test_certificate_live_issue_uat.py tests/test_certificate_pdf_integration.py -q

cd ../frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/04-provider-flow.spec.ts e2e/14-cuj-cert-lifecycle.spec.ts e2e/44-gate1-provider-first-value.spec.ts --project=chromium --reporter=line
```

---

## 7. Auditor/Sub-user Boundary Flow

### Task 7: Auditor assigned-only workflow

**Objective:** Auditor can access assigned work and gets a clear denial outside assignment.

**Files:**
- Test: `frontend/aminra-web/e2e/45-gate1-auditor-boundary.spec.ts`
- Backend related: `backend/tests/test_role_boundaries_live_smoke.py`

**RED test cases:**

1. `auditor login lands on assigned workspace`
2. `auditor can view assigned item`
3. `auditor cannot view unassigned tenant/provider item`
4. `forbidden page shows clear no-access/support copy, not blank screen`

**Commands:**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/45-gate1-auditor-boundary.spec.ts --project=chromium --reporter=line

cd ../../backend
pytest tests/test_role_boundaries_live_smoke.py tests/test_route_tenant_inventory_coverage.py -q
```

Expected GREEN before Gate 1 sign-off.

---

## 8. Error UX and Invalid Input System Sweep

### Task 8: Error-message quality contract

**Objective:** Invalid input is caught and explained clearly; no customer sees raw stack traces, JSON blobs, or silent failures.

**Files:**
- Test: `frontend/aminra-web/e2e/46-gate1-error-ux.spec.ts`
- Possible frontend source test: `frontend/aminra-web/__tests__/api-error-normalization-contract.test.ts`
- Existing related: `frontend/aminra-web/e2e/36-batch6-parse-api-error.spec.ts`

**Invalid input cases:**

- Empty required field.
- Too-short password.
- Invalid email format.
- Duplicate email/company where applicable.
- Invalid file type/too large file.
- Invalid UUID/id in route.
- Ineligible supplier/material.
- Unauthorized/forbidden action.
- Expired verification/reset link.
- Backend 422 with FastAPI `detail` array.
- Backend 409 conflict.
- Backend 500/network failure.

**RED tests:**

1. `fastapi detail array renders readable bullet messages`
2. `422 does not show success toast`
3. `409 conflict explains duplicate/conflict state`
4. `500/network error keeps form state and offers retry/support`
5. `forbidden action shows no-access message without leaking private IDs`

**Commands:**

```bash
cd frontend/aminra-web
npm test -- --run __tests__/api-error-normalization-contract.test.ts
PW_BASE_URL=https://aminra.org npx playwright test e2e/36-batch6-parse-api-error.spec.ts e2e/46-gate1-error-ux.spec.ts --project=chromium --reporter=line
```

**Expected:** all pass; no raw `{"detail":...}` visible in UI for customer-facing flows.

---

## 9. Output Correctness Gates

### Task 9: Customer-visible output correctness

**Objective:** Output screens match expected system state, especially certificate/status/public output.

**Files:**
- Test: `frontend/aminra-web/e2e/47-gate1-output-correctness.spec.ts`
- Existing related:
  - `frontend/aminra-web/e2e/17-mvp-demo-public.spec.ts`
  - `frontend/aminra-web/e2e/38-demo-spine-keycloak.spec.ts`
  - `backend/tests/test_certificate_pdf_integration.py`
  - public trace tests under backend supply-chain tests

**Customer expected output cases:**

- Certificate/public verify page shows the correct certificate ID/status/company.
- Draft/private/unapproved certificate does not appear public.
- Public trace uses sealed/published snapshot only.
- Invalid public ID returns safe not-found.
- No tenant IDs, provider internal IDs, audit actor IDs, or private fields leak.
- Business dashboard statuses match backend state.

**Commands:**

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test e2e/17-mvp-demo-public.spec.ts e2e/38-demo-spine-keycloak.spec.ts e2e/47-gate1-output-correctness.spec.ts --project=chromium --reporter=line

cd ../../backend
pytest tests/test_certificate_pdf_integration.py tests/test_cert_lifecycle_integration.py tests/test_unauth_route_boundaries.py -q
```

---

## 10. Full Gate 1 Runner

### Task 10: Build a Gate 1 runner script

**Objective:** Make Gate 1 repeatable, evidence-producing, and hard to overclaim.

**Files:**
- Create: `scripts/qa/run-gate1-onboarding.sh`
- Create/update: `docs/qa/20260917-gate1-onboarding/report.md`
- Update: `docs/qa/20260917-gate1-onboarding/status.tsv`

**Runner requirements:**

- Continue after individual step failures.
- Save each command output under `evidence/terminal/`.
- Append status rows.
- Never print secrets.
- Exit non-zero if any P0/P1 Gate 1 required step fails.
- Always produce `report.md` and `status.tsv`.

**RED test for runner behavior:**

Create a shell/unit test if project has shell test pattern, or a Python contract test:

- Test missing output report causes failure.
- Test failed command becomes `FAIL` in status.
- Test deferred non-scope command does not make Gate 1 fail.

Possible file:

- `backend/tests/test_gate1_runner_contract.py`

**Commands:**

```bash
cd backend
pytest tests/test_gate1_runner_contract.py -q

cd ..
bash scripts/qa/run-gate1-onboarding.sh
```

Expected final runner status:

- required P0/P1 rows all `PASS`
- no unresolved `FAIL`
- skipped rows classified as `DEFERRED` or `BLOCKED` with reason

---

## 11. Final Regression Pack

### Task 11: Final full-loop verification

**Objective:** Prove Gate 1 changes did not regress current green state.

**Commands:**

```bash
# Runtime health
cd /home/user/Documents/aminra-docker-system
docker compose ps aminra-backend aminra-frontend postgres-db qdrant-db redis keycloak
curl -fsS http://127.0.0.1:8100/health
curl -fsS -o /dev/null -w '%{http_code}\n' https://aminra.org/business/login

# Backend focused security/onboarding
cd backend
pytest tests/test_role_boundaries_live_smoke.py tests/test_unauth_route_boundaries.py tests/test_route_tenant_inventory_coverage.py -q
pytest tests/test_cert_lifecycle_integration.py tests/test_certificate_pdf_integration.py -q

# Frontend lint/build/source tests
cd ../frontend/aminra-web
npm run lint
npm run build
npm test -- --run

# Gate 1 browser suite
PW_BASE_URL=https://aminra.org npx playwright test \
  e2e/41-gate1-onboarding-email.spec.ts \
  e2e/42-gate1-role-landing.spec.ts \
  e2e/43-gate1-business-first-value.spec.ts \
  e2e/44-gate1-provider-first-value.spec.ts \
  e2e/45-gate1-auditor-boundary.spec.ts \
  e2e/46-gate1-error-ux.spec.ts \
  e2e/47-gate1-output-correctness.spec.ts \
  --project=chromium --reporter=line

# Full desktop Chromium regression
PW_BASE_URL=https://aminra.org npx playwright test --project=chromium --reporter=line
```

**DONE criteria:**

- All required commands PASS.
- Full desktop Chromium has `0 failed`.
- Any skipped tests have classification.
- Evidence paths attached in report.

---

## 12. Final Report Template

Create/update `docs/qa/20260917-gate1-onboarding/report.md`:

```markdown
# AMINRA Gate 1 — Unsupervised Customer Onboarding Readiness

## Verdict
PASS / PARTIAL / BLOCKED / NO-GO

## Scope
- Roles included:
- Roles excluded:
- Data mode:
- Public URLs:

## Customer experience summary
- Registration/verify email:
- Password reset:
- Business first-value workflow:
- Provider first-value workflow:
- Auditor boundary:
- Error UX:
- Output correctness:

## Evidence table
- Gate:
- Status:
- Command:
- Evidence path:

## Defects
- Severity:
- Steps:
- Expected:
- Actual:
- Evidence:
- Fix/retest status:

## Skips/deferred
- Item:
- Reason:
- Customer risk:
- Owner/date:

## Final recommendation
GO / CONDITIONAL GO / NO-GO for scoped unsupervised customer onboarding.
```

---

## 13. Expanded Customer Scenario Catalogue — add before execution

**Objective:** Prevent the Gate 1 suite from becoming a narrow happy-path checklist. These scenarios must be converted into atomic tests or explicitly marked `DEFERRED` with customer-risk rationale in `acceptance-matrix.md`.

### 13.1 Entry, navigation, and first-impression scenarios

**Anonymous/customer discovery**

- Landing page loads on fresh browser, incognito, and logged-out state.
- Business login page has `Về trang chủ`, Keycloak CTA, and does not trap unauthenticated users.
- Provider login page has the same escape/CTA behavior.
- Direct deep link to protected business page redirects to login, then returns to the intended page after login if safe.
- Direct deep link to provider-only page as business user shows clear no-access message, not redirect loop.
- Browser back button after login does not resurrect login page with stale authenticated state.
- Browser refresh on dashboard preserves session and role context.
- Two tabs open: logout in one tab causes the other tab to require re-auth or refresh identity safely.
- Session expiry while editing a form preserves draft locally if possible, or clearly asks user to re-login without data loss.
- User opens app after many hours: stale local profile is not shown before `/auth/me` verifies token.

**Customer satisfaction expectation:** The user always knows whether they are logged in, which organization they represent, and where to go next.

### 13.2 Registration and identity edge cases

**Business registration / invite**

- Valid new business self-registration succeeds and sends verification email.
- Duplicate email registration does not create duplicate Keycloak/Postgres rows.
- Duplicate company name with different owner follows the intended policy and explains conflict clearly.
- Email with uppercase letters normalizes consistently.
- Email with leading/trailing spaces is trimmed or rejected consistently.
- Invalid email domains/formats show inline error.
- Password below policy is rejected with readable policy details.
- Password with user email/name is rejected if Keycloak policy enforces it; UI message is readable.
- Terms/privacy required checkbox cannot be bypassed if required.
- Required business fields missing show field-level errors.
- Registration interrupted after Keycloak user creation but before app DB row creation compensates or recovers idempotently.
- Re-submitting after network timeout does not create duplicate users/tenants.
- Verification email resend works and rate-limits abuse.
- Verification link opened on a different browser/device completes the account and does not require original browser state.
- Expired verification link offers resend path.
- Already verified link shows safe success/already-verified message, not scary failure.
- Disabled/suspended account cannot verify/login and sees support guidance.

**Provider/auditor invites**

- Provider/CB invite accepts only intended email/role.
- Auditor invite accepts only intended email/assignment.
- Invite link expired shows clear contact/resend path.
- Invite already used cannot provision a second account.
- Invite opened by wrong existing logged-in user warns and requires logout/account switch.
- Provider/auditor invite failure does not leave orphan Keycloak user without app row.

### 13.3 Email delivery and deliverability scenarios

- Verify email subject/sender/from-domain are recognizable to customer.
- Verify email link points to canonical `auth.aminra.org` / `aminra.org`, never legacy `silvergem.org`.
- Password reset email link points to canonical domain.
- Email HTML and plaintext contain enough context and no secrets.
- User clicks the newest verification email after requesting resend multiple times; newest works, old links fail safely or remain valid per policy.
- SMTP provider accepts but event is delayed; UI sets expectation and offers resend after cooldown.
- SMTP provider failure surfaces as retry/support, not silent success.
- Rate limiting prevents email spam without locking legitimate customer permanently.

### 13.4 Login, logout, account-switch, and session isolation

- Correct business credentials login successfully.
- Wrong password shows non-enumerating error.
- Nonexistent email shows non-enumerating error.
- Unverified account gets verification-required guidance.
- Disabled account gets support guidance.
- Locked/brute-force account gets safe support guidance.
- Business logout clears local/session storage and app profile.
- Provider logout clears provider state and Keycloak realm session as designed.
- Platform admin logout does not leave admin token/profile.
- Business -> provider account switch in same browser shows correct organization/sidebar.
- Provider -> admin account switch does not show provider menu inside admin panel.
- Login in private/incognito works without service-worker cache residue.
- Service worker update does not cache auth/admin routes.
- Refresh token expiry leads to controlled re-login, not blank screen.
- Malformed/expired token API calls return 401 and frontend prompts re-auth.

### 13.5 Business first-value workflow scenarios

**Profile/company setup**

- Empty profile displays setup checklist.
- Valid company profile save persists after refresh.
- Invalid tax/company identifier format is rejected if policy exists.
- Logo upload valid image succeeds.
- Unsupported file type, huge file, and corrupted file show clear error.
- Missing company logo returns graceful empty state, not 500/noisy error.

**Supply-chain/material/process/batch**

- Business can create first material with eligible supplier.
- Supplier dropdown lists only eligible suppliers for selected material category.
- No eligible supplier state explains next step instead of showing empty unexplained dropdown.
- Ineligible/expired supplier is rejected backend-side even if user tampers request.
- Material create/update non-2xx keeps form open and shows readable error.
- Process create persists, appears in list, detail, and after refresh.
- Process update with invalid fields shows field-level error.
- Batch create with valid materials/process succeeds.
- Batch create without required materials/process is blocked.
- Batch with duplicate code/identifier follows conflict policy and explains it.
- Sealed batch cannot be mutated; UI explains immutable/sealed state.
- Public trace is unavailable before publish/seal readiness.
- Published/sealed trace shows snapshot state, not later live mutation.
- Bulk/rapid double-click submit does not create duplicates.
- Network offline during save shows retry and does not claim success.

### 13.6 Provider/CB workflow scenarios

- Provider sees only own submissions/certificates/authority records.
- Provider cannot search or open another provider's record by URL/id.
- Provider can perform allowed status transition.
- Invalid status transition is blocked with clear explanation.
- Provider certificate action output matches backend state after refresh.
- Provider cannot create/mark supplier eligibility without source authority evidence.
- Provider cannot take over another provider's supplier eligibility.
- Expired certificate/authority cannot be used for active eligibility.
- Revoked/suspended certificate disappears or is marked unavailable in business selection.
- Provider upload/view certificate PDF works with valid file.
- Invalid PDF/file type too large is rejected.
- Provider public certificate verification page shows correct public fields only.
- Provider action race/double-submit remains idempotent or conflict-safe.

### 13.7 Auditor/sub-user workflow scenarios

- Auditor login lands on assigned workspace.
- Auditor sees only assigned tenant/submission/batch.
- Auditor direct URL to unassigned item returns forbidden/not-found without private hints.
- Auditor allowed comment/review action persists if in scope.
- Auditor cannot approve/finalize provider/admin-only actions.
- Auditor account removed/disabled loses access immediately after refresh.
- Auditor with no assignments sees helpful empty state.

### 13.8 Admin support and recovery scenarios

- Platform admin can locate customer user by email without exposing secrets.
- Platform admin can safely resend verification email.
- Platform admin can reset password via Keycloak-backed endpoint.
- Admin reset revokes sessions; target old session loses access.
- Admin self-reset purges own session and requires re-login.
- Admin cannot edit user password through profile update endpoint silently.
- Admin disabled account state is reflected in login behavior.
- Admin-created placeholder/test user cleanup removes Keycloak and app rows safely where intended.

### 13.9 Output correctness and document/public artifact scenarios

- Public certificate verify page shows exact certificate number, status, company, issue/expiry dates.
- Expired/revoked certificate shows the correct non-active status.
- Draft/pending certificate is not public.
- Certificate PDF renders with correct status and no stale cached previous state.
- Public trace valid opaque ID returns 200 and integrity markers.
- Public trace invalid/random/injection ID returns safe 404/not-found.
- Public trace does not leak tenant IDs, provider internal IDs, audit actor IDs, source certificate IDs, private notes.
- Dashboard status badges match backend canonical state.
- After provider revokes certificate, business dashboard/public output reflect new state according to policy.

### 13.10 Error UX and validation scenarios

For each core form/action, test these classes:

- Missing required field.
- Invalid format.
- Too long input.
- Leading/trailing whitespace.
- Unicode/Vietnamese names.
- HTML/script injection text renders escaped.
- Duplicate/conflict state.
- Unauthorized anonymous request.
- Forbidden authenticated role.
- Expired session.
- Backend 422 `detail` array.
- Backend 409 conflict.
- Backend 429 rate limit.
- Backend 500.
- Network timeout/offline.
- Slow response with loading state.
- Double submit while loading.

**User-facing rule:** Every failure must say what happened, what the user can do next, and must not display raw stack traces, raw JSON, internal IDs, or secrets.

### 13.11 Cross-browser, responsive, accessibility, and localization scenarios

- Chromium desktop full matrix passes.
- WebKit/Safari smoke for login/register/verify/reset/core dashboard if customer uses Safari.
- Mobile narrow viewport: login/register/reset usable, no horizontal overflow, CTA visible.
- Tablet viewport: dashboard/sidebar usable.
- Keyboard-only navigation through login/register/reset forms works.
- Focus moves to first invalid field or error summary after failed submit.
- Screen-reader labels exist for critical inputs/buttons.
- Color contrast serious warnings triaged for onboarding-critical pages.
- Vietnamese and English copy both understandable if app supports both.
- Date/time/number formatting is consistent for certificate validity and statuses.

### 13.12 Data integrity, idempotency, and concurrency scenarios

- User presses submit twice quickly: one record or safe duplicate prevention.
- User opens same edit form in two tabs; stale save conflict policy is clear.
- Backend rejects tampered tenant/provider IDs even if UI hides them.
- Partial provisioning failure compensates or recovers idempotently.
- Audit log records critical onboarding/account/security actions.
- Append-only audit immutability is respected; tests must not bypass trigger.
- Created QA records can be identified and cleaned up safely.

### 13.13 Security and abuse scenarios within Gate 1

- Anonymous cannot access protected APIs/pages.
- Business cannot access provider/admin/auditor routes.
- Provider cannot access platform-admin routes.
- Auditor cannot access business owner/provider-admin mutation routes.
- Path traversal/file upload abuse rejected.
- Uploaded file download requires correct tenant/authority.
- XSS payload in company/material/process names renders escaped in UI and public outputs.
- CSRF/state mismatch in OIDC callback fails closed.
- Open redirect attempt in `next`/return URL is rejected.
- Rate limit on login/reset/verification resend is effective and user-friendly.

### 13.14 Observability scenarios for customer-impacting failures

- Failed verification send is logged with non-secret correlation ID.
- Password reset failure is logged without token/password leakage.
- Backend 5xx during onboarding increments/appears in logs/metrics.
- Customer support can ask user for a safe request/correlation ID.
- Fatal frontend console/page errors are captured during E2E; Gate 1 fails on uncaught errors in onboarding-critical pages.

### 13.15 Test-priority mapping

Convert the above into tiers:

- **P0 required for Gate 1 GO:** registration/verify/reset, login/session, role landing, first-value business/provider workflow, forbidden boundaries, no false success, output correctness, no private leak.
- **P1 required before more than 1-2 friendly customers:** cross-browser/mobile/accessibility, admin support recovery, rate limits, audit/correlation IDs.
- **P2 can be backlog with explicit customer-risk note:** advanced concurrency, non-critical localization polish, optional mobile-auditor app if outside Gate 1 scope.

---

## 14. Execution Order

Do not parallelize before scope and email contracts are stable.

1. Task 1 — acceptance matrix.
2. Task 2 — verify email.
3. Task 3 — password reset.
4. Task 4 — role landing/session correctness.
5. Task 8 — error UX normalization, because it affects all later flows.
6. Task 5 — business first-value workflow.
7. Task 6 — provider first-value workflow.
8. Task 7 — auditor boundary.
9. Task 9 — output correctness.
10. Task 10 — runner.
11. Task 11 — final regression.
12. Task 12 — report and verdict.

---

## 14. Stop Conditions

Stop and report `NO-GO` or `BLOCKED` if any of these occur:

- Verification email cannot be completed through live/canonical path.
- Password reset cannot be completed through live/canonical path.
- Any role can access another tenant/provider/customer's data.
- Any create/update flow shows success after backend failure.
- Public certificate/trace output leaks private fields.
- Full desktop Chromium has unresolved failures after Gate 1 changes.
- Required credentials/env are missing and cannot be safely sourced without exposing secrets.

---

## 15. Commit/Deploy Policy

- Do not commit unless founder approves after reviewing diff and evidence.
- Do not deploy/recreate containers unless explicitly authorized.
- If deploy is authorized, run the existing approval-gated immutable local deploy pipeline and attach evidence under the same Gate 1 report.

Recommended commit sequence after approval:

```bash
git add docs/qa/20260917-gate1-onboarding scripts/qa/run-gate1-onboarding.sh backend/tests frontend/aminra-web/e2e frontend/aminra-web/__tests__
git commit -m "test(qa): add gate1 onboarding readiness suite"
# then product fixes in separate commits by behavior, not one giant mixed commit
```
