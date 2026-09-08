# AMINRA Login/Auth/RBAC QA — all account types

Generated: 2026-09-07T23:47:32.768848+00:00
Environment: local Docker stack (`frontend localhost:3100`, `backend localhost:8100`, `keycloak localhost:8180`, issuer `https://auth.silvergem.org/realms/aminra`).

## Verdict

**PARTIAL / NOT DONE.** Core Keycloak login works for business, CB/provider, and auditor, but platform-admin login is blocked by invalid demo credentials and several RBAC/security boundaries fail or are stale. Do not promote this as fully regression-tested until the P0/P1 items below are fixed and re-run.

## Account matrix

- Business (`biz-demo-1@demo.aminra.vn`): API token login PASS; `/auth/me` PASS; browser SSO login PASS but lands on onboarding industry-select instead of dashboard because account requires onboarding.
- CB/provider owner (`cb-demo@demo.aminra.vn`): API token login PASS; `/auth/me` role provider/is_owner true PASS; browser SSO login PASS.
- Auditor (`auditor-demo@demo.aminra.vn`): Keycloak login PASS; browser SSO login PASS; **RBAC FAIL** — backend projects `/auth/me.role` as `provider`, and allows `/api/submissions/received` + `/dossiers` although matrix expects auditor-only audit scope.
- Platform admin (`admin`, `admin@aminra.com`): **FAIL/BLOCKED** — password grant rejected with `invalid_grant`; browser remains on gated `/admin` login screen. Separate existing Playwright fixture using platform admin token passes token validation, so credential/config path is inconsistent.
- Disabled/surplus business (`biz-demo-2@demo.aminra.vn`): negative login PASS — rejected with `Account disabled`.
- Wrong password: negative PASS for enabled user accounts tested by runtime matrix.

## Evidence files

- Runtime/API matrix: `docs/qa/2026-09-07-login-all-account-types/runtime-login-matrix-results.json`
- Browser login smoke JSON: `docs/qa/2026-09-07-login-all-account-types/browser-login-smoke-results.json`
- Browser screenshots: `docs/qa/2026-09-07-login-all-account-types/evidence/screenshots/`
- Raw logs:
  - `/tmp/aminra-auth-frontend-vitest.log`
  - `/tmp/aminra-auth-rbac-pytest.log`
  - `/tmp/aminra-runtime-login-matrix.log`
  - `/tmp/aminra-browser-login-smoke.log`
  - `/tmp/aminra-auth-e2e-targeted.log`

## Test commands executed

```bash
# Frontend unit/auth contracts
cd frontend/aminra-web
npx vitest run __tests__/auth-oidc.test.ts __tests__/auth-callback-page.test.tsx __tests__/UserAuthContext-keycloak.test.tsx __tests__/AdminAuthContext.test.tsx __tests__/landing-keycloak-cta.test.tsx __tests__/components/KeycloakSsoButton.test.tsx __tests__/forgot-password.test.tsx __tests__/reset-password.test.tsx __tests__/service-worker-auth-cache.test.ts __tests__/sidebar-admin-navigation-contract.test.tsx

# Backend pytest copied into running backend container because tests are not mounted in image
cd /home/user/Documents/aminra-docker-system
docker cp backend/tests <backend-container>:/tmp/aminra-tests/tests
docker cp backend/pytest.ini <backend-container>:/tmp/aminra-tests/pytest.ini
docker compose exec -T aminra-backend sh -lc 'cd /tmp/aminra-tests && PYTHONPATH=/app BACKEND_URL=http://127.0.0.1:8000 pytest -q tests/test_dual_auth_unit.py tests/test_keycloak_token_security.py tests/test_keycloak_jwks_edge.py tests/test_keycloak_admin_edge.py tests/test_unauth_route_boundaries.py tests/test_role_boundaries_live_smoke.py'

# Runtime matrix with real Keycloak tokens + backend route boundaries
BACKEND_URL=http://localhost:8100 KEYCLOAK_URL=http://localhost:8180 KEYCLOAK_PUBLIC_PROTO=https KEYCLOAK_PUBLIC_HOST=auth.silvergem.org KEYCLOAK_PUBLIC_PORT=443 python3 docs/qa/2026-09-07-login-all-account-types/runtime-login-matrix.py

# Browser SSO smoke for business/provider/auditor/admin
node frontend/aminra-web/tmp-browser-login-smoke.mjs

# Targeted Playwright auth/keycloak/RBAC E2E
cd frontend/aminra-web
PLAYWRIGHT_BASE_URL=http://localhost:3100 npx playwright test e2e/02-auth.spec.ts e2e/08-login-ui.spec.ts e2e/20-admin-unified-auth.spec.ts e2e/21-admin-pages-token-pattern.spec.ts e2e/22-token-isolation.spec.ts e2e/23-cross-context-logout.spec.ts e2e/keycloak/01-token-validation.spec.ts e2e/keycloak/02-login-ui-flow.spec.ts e2e/keycloak/03-attacker-scenarios.spec.ts e2e/keycloak/04-multi-user.spec.ts --project=desktop-chromium
```

## Results summary

### Frontend auth Vitest
```text
 Test Files  10 passed (10)
      Tests  120 passed (120)
```

### Backend auth/RBAC pytest
```text
=================== 1 failed, 227 passed, 3 skipped in 7.05s ===================
```
Failure: `test_keycloak_token_security.py::test_issuer_mismatch[https://auth.silvergem.org/realms/aminra]` expected issuer mismatch but used the currently configured issuer value; likely a stale/incorrect test parameter, not a runtime exploit by itself. Needs test cleanup or assertion clarification.

### Runtime login matrix
```text
PASS=False failures=5
FAIL: platform_admin_username login expected success got HTTP 401 {'error': 'invalid_grant', 'error_description': 'Invalid user credentials'}
FAIL: platform_admin_email login expected success got HTTP 401 {'error': 'invalid_grant', 'error_description': 'Invalid user credentials'}
FAIL: auditor /auth/me role expected auditor got provider
FAIL: auditor expected deny/non-surface /api/submissions/received, got 200
FAIL: auditor expected deny/non-surface /dossiers, got 200
```

### Browser login smoke
- Business: latest raw smoke PASS for session creation, final URL `/business/onboarding/industry-select`; older saved script expected dashboard URL, corrected evidence script now treats session token/profile as the login success criterion.
- CB/provider: PASS.
- Auditor: PASS for login/session creation; RBAC issue remains in API matrix.
- Platform admin: FAIL; no admin session/profile/token stored, page still says “Bạn cần đăng nhập”.

### Targeted Playwright E2E
```text
Error: expect(locator).toBeVisible() failed
test-results/08-login-ui-08-UI-login-fo-10a97-mail-password-submit-button-desktop-chromium/test-failed-1.png
test-results/08-login-ui-08-UI-login-fo-4358a-ccepts-email-password-input-desktop-chromium/test-failed-1.png
test-results/20-admin-unified-auth-admi-3966f-nalytics-audit-logs-overdue-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--c83b7-form-fields-when-page-loads-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--9a5a2-SO-button-when-flag-enabled-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--8c113-age-UI-renders-HOẶC-divider-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--d8c85--TOTP-hint-under-SSO-button-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--e8cc5-ns-functional-alongside-SSO-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--0eaa0-ot-password-link-is-present-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--6ebb7-renders-Keycloak-SSO-button-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--72c8a--auditor-specific-TOTP-hint-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--d547b-enders-trusted-bodies-badge-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--bfda0-oak-SSO-notice-when-flag-on-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--b375c-to-Keycloak-account-console-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--d9d6e-ndered-for-unmigrated-users-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--521f1-when-accessed-without-token-desktop-chromium/test-failed-1.png
Error: expect(locator).toBeVisible() failed
test-results/keycloak-02-login-ui-flow--bfb00--mentions-migrated-accounts-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--ae9d0-utton-redirects-to-Keycloak-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--e9538-contains-response-type-code-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--9b5ae-s-client-id-aminra-frontend-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--14c1c-ntains-code-challenge-PKCE--desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--f8ade--code-challenge-method-S256-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--ca3b8-ect-URL-has-state-parameter-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--ba90a-i-pointing-to-auth-callback-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--3850e-page-renders-username-field-desktop-chromium/test-failed-1.png
test-results/keycloak-02-login-ui-flow--85c0f-page-renders-password-field-desktop-chromium/test-failed-1.png
32 failed
3 skipped
80 passed (6.4m)
```
Failed test groups:
- e2e/02-auth.spec.ts:4:7 › 02. Authentication flows › Business register + login returns JWT
- e2e/02-auth.spec.ts:9:7 › 02. Authentication flows › /auth/me returns correct email for business token
- e2e/02-auth.spec.ts:22:7 › 02. Authentication flows › Wrong password rejected 401
- e2e/02-auth.spec.ts:43:7 › 02. Authentication flows › Admin login returns token
- e2e/08-login-ui.spec.ts:4:7 › 08. UI login form — business › Login form renders with email + password + submit button
- e2e/08-login-ui.spec.ts:24:7 › 08. UI login form — business › Form accepts email + password input
- e2e/20-admin-unified-auth.spec.ts:23:7 › admin unified auth › legacy /admin token unlocks analytics + audit-logs + overdue
- e2e/23-cross-context-logout.spec.ts:39:5 › AdminAuthContext.logout removes aminra_user_token
- e2e/keycloak/02-login-ui-flow.spec.ts:18:7 › Business login page UI › renders form fields when page loads
- e2e/keycloak/02-login-ui-flow.spec.ts:24:7 › Business login page UI › renders Keycloak SSO button when flag enabled
- e2e/keycloak/02-login-ui-flow.spec.ts:29:7 › Business login page UI › renders 'HOẶC' divider
- e2e/keycloak/02-login-ui-flow.spec.ts:34:7 › Business login page UI › renders TOTP hint under SSO button
- e2e/keycloak/02-login-ui-flow.spec.ts:39:7 › Business login page UI › legacy email+password form remains functional alongside SSO
- e2e/keycloak/02-login-ui-flow.spec.ts:44:7 › Business login page UI › forgot password link is present
- e2e/keycloak/02-login-ui-flow.spec.ts:54:7 › Provider login page UI › renders Keycloak SSO button
- e2e/keycloak/02-login-ui-flow.spec.ts:59:7 › Provider login page UI › renders auditor-specific TOTP hint
- e2e/keycloak/02-login-ui-flow.spec.ts:64:7 › Provider login page UI › renders trusted bodies badge
- e2e/keycloak/02-login-ui-flow.spec.ts:74:7 › Forgot password page › renders Keycloak SSO notice when flag on
- e2e/keycloak/02-login-ui-flow.spec.ts:79:7 › Forgot password page › CTA links to Keycloak account console
- e2e/keycloak/02-login-ui-flow.spec.ts:85:7 › Forgot password page › legacy form still rendered for unmigrated users
- e2e/keycloak/02-login-ui-flow.spec.ts:92:7 › Reset password page › renders SSO notice when accessed without token
- e2e/keycloak/02-login-ui-flow.spec.ts:97:7 › Reset password page › notice mentions migrated accounts
- e2e/keycloak/02-login-ui-flow.spec.ts:107:7 › SSO redirect flow › clicking SSO button redirects to Keycloak
- e2e/keycloak/02-login-ui-flow.spec.ts:116:7 › SSO redirect flow › redirect URL contains response_type=code
- e2e/keycloak/02-login-ui-flow.spec.ts:125:7 › SSO redirect flow › redirect URL contains client_id=aminra-frontend
- e2e/keycloak/02-login-ui-flow.spec.ts:134:7 › SSO redirect flow › redirect URL contains code_challenge (PKCE)
- e2e/keycloak/02-login-ui-flow.spec.ts:143:7 › SSO redirect flow › redirect URL has code_challenge_method=S256
- e2e/keycloak/02-login-ui-flow.spec.ts:152:7 › SSO redirect flow › redirect URL has state parameter
- e2e/keycloak/02-login-ui-flow.spec.ts:161:7 › SSO redirect flow › redirect URL has redirect_uri pointing to /auth/callback
- e2e/keycloak/02-login-ui-flow.spec.ts:170:7 › SSO redirect flow › Keycloak login page renders username field
- e2e/keycloak/02-login-ui-flow.spec.ts:179:7 › SSO redirect flow › Keycloak login page renders password field
- e2e/keycloak/03-attacker-scenarios.spec.ts:251:7 › Token structure attacks › token with whitespace rejected

## Defects / gaps

### P0 — Platform admin credential/config path broken
- Evidence: runtime matrix rejects `admin` and `admin@aminra.com` with `invalid_grant`; browser smoke remains on gated `/admin` page.
- Impact: cannot complete admin login/logout/session persistence coverage with the advertised credentials.
- Next fix: identify canonical demo platform-admin username/password (Playwright fixture appears to use a different account), seed/reset Keycloak user, then re-run admin browser + API matrix.

### P0 — Auditor effective role/RBAC boundary ambiguous and too broad
- Evidence: auditor token has Keycloak realm role `auditor`, but backend `/auth/me` returns app role `provider`; backend allows `/api/submissions/received` and `/dossiers`.
- Impact: lower-role auditor can see provider/business surfaces beyond audit scope, depending on intended policy.
- Next fix: either introduce first-class backend role `auditor` or explicitly document provider-role-with-auditor-claims and tighten route dependencies to realm role / `is_owner`.

### P1 — Bearer token whitespace accepted in E2E attacker scenario
- Evidence: `e2e/keycloak/03-attacker-scenarios.spec.ts` expected malformed token with whitespace to reject, received 200.
- Impact: likely token normalization weakness or test construction issue. Even if benign, auth parser should be deterministic and strict.

### P1 — Auth E2E suite contains stale legacy expectations
- Evidence: legacy `/auth/login` tests expect JWT/form login but stack migrated to Keycloak SSO; many UI tests expect email/password form and SSO test ids that current login pages no longer expose.
- Impact: CI signal is noisy; real regressions hide inside stale failures.
- Next fix: split legacy tests into quarantined migration tests; rewrite E2E around current SSO behavior.

### P1 — AdminAuthContext logout isolation regression
- Evidence: `e2e/23-cross-context-logout.spec.ts` user logout cleanup passed, admin logout did not remove `aminra_user_token`.
- Impact: cross-context token residue risk when switching between admin/user personas in same browser.

## Coverage not completed

- Admin full browser login/logout/session persistence: **blocked** by invalid admin credentials/config.
- True auditor-vs-provider backend policy: **blocked by unclear product policy**; current implementation treats auditor as provider at `/auth/me` but UI hides owner/provider-only nav.
- Full Playwright suite: not run; targeted auth/keycloak/RBAC suite already has blocking failures.
- Public sandbox: not tested; local Docker only.

## Recommended next order

1. Fix platform admin seed/credential path and rerun runtime + browser smoke.
2. Decide auditor authorization model, then enforce route boundaries with backend tests.
3. Fix token whitespace parser behavior or correct attacker test if it is invalid.
4. Clean stale legacy E2E expectations so auth CI becomes actionable.
5. Add canonical login/logout/session-persistence Playwright test per account type after P0s are closed.
