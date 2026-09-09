# AMINRA QA — CRUD users / org-provider / editor-auditor / company profile

Date: 2026-09-09
Scope path: `/home/user/Documents/aminra-docker-system/docs/qa/2026-09-08-crud-users-org-editor-business/`
Verdict: **GO for controlled sandbox/UAT smoke on these scoped paths** after P0 remediation. **Not yet a broad production release sign-off** because this pass covers focused CRUD/auth/browser smoke only, not full regression, CI, migration rollback, or load/security scans.

## 1. Analysis

### Acceptance criteria

- Admin user CRUD works with a real temporary `platform_admin` Keycloak token.
- Editor/admin placeholder CRUD works and leaves no QA placeholder behind.
- Business owner can read/update/restore company profile without permanent fixture drift.
- Business owner can create/read/update/delete IHC members with QA-only data, and deletion does not leave login-capable Keycloak orphans.
- Provider owner can create/read/update/delete auditors with QA-only data, and deletion does not leave login-capable Keycloak orphans.
- Role boundaries fail closed: business/auditor cannot hit privileged admin/provider/business-owner endpoints.
- Browser smoke can render the relevant role pages with real seeded Keycloak accounts.
- Company-logo empty state does not create browser console/API error noise for tenants without uploaded logo.
- QA-created data is cleaned up from Postgres and Keycloak.

### Endpoint / UI map checked

- Admin user CRUD: `POST/GET/PUT/DELETE /admin/users`, `POST /admin/users/{id}/reset-password`; UI: `/admin` → `Quản lý Users`.
- Editor placeholder CRUD: `POST/GET/PUT/DELETE /admin/placeholders`; UI: `/admin` → `Placeholders`.
- Business company profile: `GET/PUT /auth/company-profile`; UI: `/settings/company`.
- Business IHC member CRUD: `POST /auth/business/invite`, `GET /auth/business/members`, `PUT/DELETE /auth/business/members/{id}`, permission read/write; UI: `/members`.
- Provider auditor CRUD: `POST/GET/PUT/DELETE /auth/provider/auditors`; UI: `/auditors`.
- Provider managed businesses: UI `/portfolio`.
- Auditor dashboard: UI `/dashboard/provider` with non-owner auditor fixture.

### Root cause confirmed and remediated

- The prior P0 blocker was real: `POST /auth/business/invite` and `POST /auth/provider/auditors` wrote `owner["sub"]` into `users.invited_by`.
- Under Keycloak auth, `owner["sub"]` is the IdP subject UUID, while `users.invited_by` is an FK to AMINRA `users.id`.
- Fix applied in `backend/auth/router.py`:
  - `invite_member` now resolves the actor via `resolve_canonical_user_id(owner, db)` and writes the canonical AMINRA DB user id to `invited_by`.
  - `invite_auditor` uses the same canonical id and also uses it for missing provider `tenant_id` self-heal.
  - `remove_member` and `remove_auditor` now fetch the child row's `keycloak_sub` and call `keycloak_admin.delete_user(...)` before deleting the Postgres row, so live delete no longer leaves login-capable KC orphans.
  - `GET /auth/company-logo/{tenant_id}` now returns `204 No Content` when no logo exists, instead of noisy `404`.

## 2. Solution / evidence produced

### Code/tests added or changed

- Changed: `backend/auth/router.py`.
- Added: `backend/tests/test_auth_invite_canonical_invited_by.py`.
  - Covers business invite canonical `invited_by`.
  - Covers provider auditor invite canonical `invited_by`.
  - Covers business member delete removing Keycloak account.
  - Covers provider auditor delete removing Keycloak account.
- Added: `backend/tests/test_company_logo_empty_state.py`.
  - Covers missing logo returns `204` empty state, not `404` error.
- Changed: `docs/qa/2026-09-08-crud-users-org-editor-business/live-crud-smoke.py`.
  - Token acquisition supports Keycloak public issuer headers so password-grant tokens validate against the API issuer config while still running from inside Docker.

### Automated gates

- Focused backend suite after fix: `71 passed, 7 skipped, 18 warnings`.
  - Command run in container:
    - `PYTHONPATH=/app pytest -q tests/test_company_logo_empty_state.py tests/test_auth_invite_canonical_invited_by.py tests/test_kc_sub_fk_smoke.py tests/test_admin_user_password_reset.py tests/test_feature_flags_unit.py`
  - Warnings are pre-existing test hygiene issues: unknown `uat` mark and sync tests marked `asyncio` in `test_feature_flags_unit.py`.
- Previous baseline evidence retained:
  - Backend focused auth/admin/security suite: `130 passed, 17 warnings` → `evidence/raw/backend-focused-pytest.txt`.
  - Frontend focused Vitest auth/admin/cache suite: `50 passed` → `evidence/raw/frontend-focused-vitest.txt`.
  - Demo Keycloak login smoke: business/provider/auditor pass; `admin@aminra.com` password credential drift remains P1 → `evidence/raw/keycloak-login-smoke.txt`.

### Live API CRUD smoke after fix

- Result: `30/30 passed`, `0 failed`.
- Evidence: `evidence/raw/live-crud-smoke-after-fix.json`.
- Covered positive paths:
  - Temporary platform admin token.
  - Admin user create/search/update/reset-password/delete.
  - Editor placeholder create/read/update/delete.
  - Company profile read/update/read-after-update/restore.
  - Business member create/read/update/permissions read/permissions update/delete.
  - Provider auditor create/read/update/delete.
- Covered failure/negative paths:
  - Deleted business member cannot authenticate after delete: expected `401`, passed.
  - Deleted provider auditor cannot authenticate after delete: expected `401`, passed.
  - Business denied `/admin/users`: expected `403`, passed.
  - Business denied provider auditor create: expected `403`, passed.
  - Auditor denied business members: expected `403`, passed.
- Cleanup verification after live smoke:
  - Postgres: `{"pg_users" : 0, "pg_member_invites" : 0}` for `qa-crud-%@qa.aminra.vn` and `forbidden-%@qa.aminra.vn`.
  - Keycloak: `{"forbidden-": 0, "qa-crud-": 0}`.

### Browser smoke after fix

- Result: `5/5 routes rendered`, `failed: []`.
- Evidence: `evidence/raw/browser-role-pages-smoke-after-fix.json`.
- Covered pages:
  - Business owner: `/settings/company`, `/members`.
  - Provider owner: `/auditors`, `/portfolio`.
  - Auditor fixture: `/dashboard/provider`.
- The previous company-logo 404 console noise is resolved by backend `204` empty-state response.

## 3. Risks

- **P1 release-process risk:** These fixes were applied locally and copied into the running backend container for verification. They are not committed/deployed until explicitly authorized.
- **P1 auth ops risk:** `admin@aminra.com` credential drift remains in the separate login smoke. Current CRUD smoke works around this by creating a temporary platform-admin identity; canonical admin credential source still needs cleanup.
- **P2 test hygiene risk:** `test_feature_flags_unit.py` contains sync tests marked `asyncio`; `test_kc_sub_fk_smoke.py` uses unregistered `uat` mark. Not product-blocking, but warning noise can hide future signal.
- **P2 static guard brittleness:** Existing Playwright static guard `36-batch6-parse-api-error` is quote-style brittle and still should be made regex-based (`from ["']@/lib/apiError["']`).
- **P2 delete atomicity risk:** Delete path removes Keycloak before Postgres. This prevents login-capable orphans, but if the DB delete fails after KC deletion, a disabled/loginless DB row can remain. Safer future improvement: transactional state machine / soft-delete first, then async/idempotent KC cleanup with retry.

## 4. Tests

### Commands / checks represented by evidence

- Focused backend suite: command listed above; latest observed result `71 passed, 7 skipped, 18 warnings`.
- Live API CRUD smoke: `live-crud-smoke.py` → `evidence/raw/live-crud-smoke-after-fix.json`.
- Browser role-page smoke: `browser-role-pages-smoke.cjs` → `evidence/raw/browser-role-pages-smoke-after-fix.json`.
- Cleanup verification: Postgres + Keycloak QA-prefix checks executed after live smoke; no QA leftovers found.

### Failure-path coverage included

- Invite FK regression:
  - Business member `invited_by` must be AMINRA `users.id`, not Keycloak `sub`.
  - Provider auditor `invited_by` must be AMINRA `users.id`, not Keycloak `sub`.
- Delete orphan regression:
  - Business member deletion removes the corresponding Keycloak account before the PG row.
  - Provider auditor deletion removes the corresponding Keycloak account before the PG row.
  - Live password-grant attempts for deleted member/auditor return `401`.
- Role boundary:
  - Business token denied admin users.
  - Business token denied provider auditor creation.
  - Auditor token denied business member listing.
- Empty-state browser noise:
  - Missing company logo returns `204`, browser role-page smoke reports no failed responses/console errors.

## 5. Improvements / next actions

P0 — completed in this pass:

1. Replace `owner["sub"]` used as `invited_by` in business member and provider auditor insert paths with canonical AMINRA DB `users.id`.
2. Add regression tests for canonical `invited_by`.
3. Extend delete behavior to remove Keycloak child accounts and prove post-delete login denial in live smoke.
4. Re-run live CRUD smoke to full pass.
5. Remove company-logo empty-state console noise and re-run browser smoke to full pass.

P1 — recommended before production-style release:

1. Commit these local changes after review approval.
2. Resolve `admin@aminra.com` credential drift or update the canonical QA credential source; re-run account login smoke.
3. Make `e2e/36-batch6-parse-api-error.spec.ts` quote-style agnostic.
4. Run broader backend/frontend regression in CI-equivalent mode, not only focused smoke.

P2 — hardening:

1. Replace hard delete choreography with idempotent account-deprovision workflow: mark child disabled/deleting in PG, revoke/disable/delete KC, then final PG delete or audit tombstone.
2. Register custom pytest marks and remove invalid `asyncio` marks from sync tests.
3. Add an API-level test for `GET /auth/company-logo/{tenant_id}` over HTTP, not only direct function call.
