# AMINRA Remediation QA Report — FE Baseline, Role Boundary Harness, Canonical URL, Admin Flow 19

Date: 2026-09-04
Repo: `/home/user/Documents/aminra-docker-system`
Mode: local controlled sandbox remediation + verification.
Safety: no commit, no push, no deploy, no production data mutation.

## Executive verdict

- **Controlled sandbox demo:** GO on `http://localhost:3100` and `https://dev-web.silvergem.org`.
- **Customer pilot / production onboarding:** NO-GO until Keycloak email verification/SMTP is configured and verified.
- **Security smoke status:** representative anonymous + live role-boundary matrix is now green.
- **Frontend baseline status:** previously-red FE Vitest baseline is now green after classifying and updating stale tests/harness expectations plus one narrow product bug fix for revision error visibility.

## Scope completed

1. P0 FE baseline triage by category; no broad product rewrites.
2. P1 backend role-boundary live smoke harness fix without weakening RBAC assertions.
3. P1 demo URL canonical decision: `dev-web.silvergem.org` is canonical public sandbox; `fe.silvergem.org` is non-canonical/legacy drift.
4. Added explicit Flow 19 admin assertion for pending provider approval queue.
5. Ran verification gates and saved raw evidence logs.

## Changes made

### FE baseline triage/fixes

Files touched:

- `frontend/aminra-web/__tests__/auth-oidc.test.ts`
- `frontend/aminra-web/__tests__/forgot-password.test.tsx`
- `frontend/aminra-web/__tests__/reset-password.test.tsx`
- `frontend/aminra-web/__tests__/data-export.test.tsx`
- `frontend/aminra-web/__tests__/components/SimpleHeader.test.tsx`
- `frontend/aminra-web/__tests__/revision-panel.test.tsx`
- `frontend/aminra-web/components/submissions/RevisionPanel.tsx`

Classification:

- Keycloak redirect expectation drift: stale tests after SSO migration; updated to assert current `prompt=login` behavior.
- Forgot/reset password: stale tests for removed local password reset API; rewritten to assert Keycloak-owned handoff behavior.
- Data export auth token: stale test harness; page now consumes `UserAuthContext`, so tests mock context instead of legacy localStorage token.
- SimpleHeader branding: stale visual/accessibility expectation; now asserts accessible `AMINRA` wordmark image and current upload link styling.
- Revision panel: one real product bug fixed — fetch errors were hidden by the empty-panel early return. Guard now keeps error visible.

### Backend live role-boundary harness

File touched:

- `backend/tests/test_role_boundaries_live_smoke.py`

Root cause:

- Test ran inside `aminra-backend` container and obtained tokens from container-local Keycloak. Without forwarded proto/host headers, Keycloak minted tokens with issuer `http://auth.silvergem.org:8080/realms/aminra`, while the backend validates against public issuer `https://auth.silvergem.org/realms/aminra`.
- Result: backend rejected otherwise-valid demo tokens as `401 Invalid issuer`.

Fix:

- Keep token exchange container-local (`http://keycloak:8080`) to avoid public auth routing.
- Add forwarded proto/host/port headers so Keycloak mints tokens with the public issuer expected by backend.
- Default backend URL in container test to `http://127.0.0.1:8000`.
- Keep RBAC assertions strict: lower roles must be denied; platform admin must access admin read surfaces.

### Canonical demo URL

Files touched:

- `scripts/qa/runtime-smoke.sh`
- `docs/qa/current-test-baseline.md`
- `docs/qa/2026-09-04-aminra-remediation/demo-url-canonical.md`

Decision:

- Canonical local demo URL: `http://localhost:3100`
- Canonical public sandbox demo URL: `https://dev-web.silvergem.org`
- `https://fe.silvergem.org` remains non-canonical/legacy hostname drift until explicitly fixed and re-promoted.

### Admin Flow 19

File touched:

- `scripts/pre_demo_check.sh`

Added explicit assertion:

- Flow 19 now checks `/auth/admin/pending-providers`.
- Validates response shape: `providers` is a list, `count` is an integer, and `count == len(providers)`.

## Verification evidence

Raw logs are under:

`docs/qa/2026-09-04-aminra-remediation/raw/`

Commands/results:

- FE targeted remediation gate:
  - `npm test -- __tests__/auth-oidc.test.ts __tests__/forgot-password.test.tsx __tests__/reset-password.test.tsx __tests__/data-export.test.tsx __tests__/components/SimpleHeader.test.tsx __tests__/revision-panel.test.tsx`
  - Result: **6 files passed / 55 tests passed**
  - Log: `raw/fe-targeted-green-rerun.log`

- FE full baseline:
  - `npm test`
  - Result: **18 files passed / 194 tests passed**
  - Log: `raw/fe-vitest-full-after-remediation.log`

- Backend live role-boundary RED evidence:
  - Result before fix: **12 errors** due token endpoint/public routing mismatch; after first harness copy, **12 failures** due `401` issuer mismatch.
  - Logs: `raw/be-role-boundaries-red.log`, `raw/be-role-boundaries-green-rerun.log`

- Backend live role-boundary after fix:
  - `docker compose exec -T aminra-backend python -m pytest tests/test_role_boundaries_live_smoke.py -q`
  - Result: **9 passed / 3 skipped without explicit ADMIN_DEMO_PW** after pre-commit hardening. Earlier explicit-admin run passed **12 passed**.
  - Log: `raw/be-role-boundaries-no-admin-env-after-review-fix.log`
  - Note: platform-admin positive smoke now requires explicit admin demo credentials; the seed/test harness must never default `platform_admin` to the shared business/provider/auditor demo password.

- Backend focused security/regression suite:
  - `docker compose exec -T aminra-backend python -m pytest tests/test_role_boundaries_live_smoke.py tests/test_unauth_route_boundaries.py tests/test_certificate_pdf_integrity_smoke.py tests/test_generate_document_export_security.py tests/test_supply_chain_suppliers.py tests/test_supply_chain_batches.py -q`
  - Result: **144 passed / 3 skipped without explicit ADMIN_DEMO_PW** after pre-commit hardening. Earlier explicit-admin run passed **147 passed**.
  - Log: `raw/be-focused-security-after-review-fix.log`

- Admin smoke with Flow 19:
  - `bash -n scripts/pre_demo_check.sh && ADMIN_DEMO_PW=[REDACTED] bash scripts/pre_demo_check.sh`
  - Result: **PASS 35 / WARN 0 / FAIL 0**
  - Flow 19: **Admin pending provider queue returns providers[] + count**
  - Log: `raw/pre-demo-flow19-green.log`

- Runtime canonical smoke:
  - `bash scripts/qa/runtime-smoke.sh`
  - Result: **PASS 12 / WARN 0 / FAIL 0**
  - Public URLs checked: `https://dev-web.silvergem.org` only.
  - Log: `raw/runtime-smoke-canonical-after-remediation.log`

- Browser/API demo spine:
  - `npm run test:e2e -- e2e/38-demo-spine-keycloak.spec.ts`
  - Result: **3 passed**
  - Log: `raw/fe-playwright-demo-spine-after-remediation.log`

- Keycloak email config:
  - `bash scripts/keycloak-email-config-check.sh`
  - Result: **FAIL / 4 blockers** — `verifyEmail` off, SMTP host missing, SMTP from missing, SMTP transport security missing.
  - Log: `raw/keycloak-email-config-check-after-remediation.log`

- Whitespace/syntax:
  - `git diff --check`
  - Result: **PASS**
  - `bash -n scripts/pre_demo_check.sh`
  - Result: **PASS**

## Remaining blockers

### P0 — Production onboarding still blocked by Keycloak email verification

The remediation intentionally did not configure SMTP credentials. Current state remains:

- `verifyEmail` not enabled.
- SMTP host missing.
- SMTP from missing.
- SMTP transport security missing.

This blocks customer pilot / production onboarding, but does not block a controlled sandbox demo if demo users are pre-seeded and no real customer onboarding is attempted.

### P1 — Dirty working tree needs isolation before commit

Repo already contains many modified/untracked files beyond this remediation. Do not commit/push blindly. Isolate the intended QA/security/demo changes first.

## Final recommendation

- Use this state for a controlled sandbox demo.
- Do not present as customer pilot ready.
- Next P0: configure real SMTP/verification and rerun email verification checks.
- Before merge: isolate diff, run build/type gates, and review the broader dirty tree.
