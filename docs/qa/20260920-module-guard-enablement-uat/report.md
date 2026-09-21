# AMINRA Module Guard Enablement — Deploy/Rebuild/UAT Report

Date: 2026-09-20 / 2026-09-21 runtime
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `dev`
Verdict: **CONDITIONAL GO for local sandbox module-guard enablement**

## Executive summary

Module guards are now enabled in the rebuilt local AMINRA runtime for the scoped rollout:

- `MODULE_GUARDS_ENABLED=true`
- `MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace`

Core source gates, rebuild/deploy gates, and live UAT passed after fixing one real backend provisioning defect discovered by UAT.

## Scope

In scope:

1. Rebuild/redeploy local AMINRA backend + frontend after module end-user UX and guard work.
2. Enable scoped backend module guards.
3. Verify business end-user module package UX.
4. Verify backend fail-closed guard behavior for disabled modules.
5. Verify admin module console can load tenant module state through live admin API.
6. Verify health after deploy.

Out of scope:

- Full multi-browser/mobile matrix.
- Public production traffic rollout beyond health smoke.
- Billing/package/payment semantics.
- Admin save/mutation UAT for module status changes beyond existing automated contract tests.

## Deployment evidence

Deploy command lane:

- `scripts/automation/modularization-phase-gate.sh immutable-deploy`
- Env: `MODULE_GUARDS_ENABLED=true`, `MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace`
- Evidence dirs:
  - `docs/qa/20260920-223703-module-end-user-guard-deploy/`
  - `docs/qa/20260920-224958-module-guard-redeploy-after-provision-fix/`

Final deployed health:

- Backend container: healthy
- Frontend container: healthy
- Local frontend `/health`: HTTP 200
- Local backend `/health`: HTTP 200
- Public `https://aminra.org/health`: HTTP 200

## Gates run

### Source/backend/frontend gates

PASS:

- Backend focused module gates: `26 passed`
  - `tests/test_module_registry_migration.py`
  - `tests/test_module_service.py`
  - `tests/test_module_route_contract.py`
  - `tests/test_module_guard.py`
  - `tests/test_supply_chain_module_guards.py`
- Frontend focused gates: `11 passed`
  - `sidebar-module-navigation-contract.test.tsx`
  - `sidebar-admin-navigation-contract.test.tsx`
  - `admin-module-manager-contract.test.tsx`
  - `my-modules-customer-experience.test.tsx`
- Frontend lint: PASS
- Alembic head: `043_account_deletion_cases (head)`
- Docker BuildKit write probe: PASS
- Next production build: PASS with existing Sentry config warnings

### Live business UAT

PASS:

- Spec: `frontend/aminra-web/e2e/module-guard-live-uat.spec.ts`
- Final evidence: `docs/qa/20260920-225627-module-guard-live-uat-final2/`
- Result: `1 passed`
- Evidence screenshots:
  - `evidence/01-business-my-modules.png`
  - `evidence/02-disabled-process-direct-url.png`

Assertions covered:

- Business user obtains real Keycloak token.
- `/api/api/me/modules` returns business model and tenant module package.
- `/modules` page renders “Gói module của tôi”, business model, active/disabled module cards, and locked/disabled copy.
- Enabled `supplier_management` API returns HTTP 200 for materials.
- Disabled `process_digitization` API returns HTTP 403 with `MODULE_DISABLED:process_digitization`.
- Disabled `traceability` API returns HTTP 403 with `MODULE_DISABLED:traceability`.

### Live admin console UAT

PASS:

- Spec: `frontend/aminra-web/e2e/admin-module-console-live-uat.spec.ts`
- Final evidence: `docs/qa/20260920-225904-admin-module-console-live-uat-final3/`
- Result: `1 passed`
- Evidence screenshot:
  - `evidence/03-admin-tenant-module-console.png`

Assertions covered:

- Platform admin obtains real Keycloak token.
- Admin API `/api/auth/admin/tenants/{tenant_id}/modules` returns live tenant module package.
- Browser `/admin` accepts platform-admin token.
- Admin “Tenant modules” tab loads.
- Tenant ID lookup renders business model and module status controls.

## Defect found and fixed during UAT

Severity: **P1 / runtime onboarding blocker**

Finding:

- First live business UAT failed when `business-select` attempted to provision modules for a tenant with no existing `tenant_modules` rows.
- Backend inserted `tenant_modules.status='enabled'` or `'disabled'` without setting `enabled_at` / `disabled_at`.
- DB check constraint requires `enabled_at IS NOT NULL` for `enabled|trial`, and `disabled_at IS NOT NULL` for `disabled|locked`.

Fix:

- Updated `backend/auth/module_service.py` provisioning SQL to set `enabled_at` or `disabled_at` on insert.
- Updated conflict path to maintain timestamp invariants when non-admin-overridden rows change status.
- Added contract assertions in `backend/tests/test_module_service.py` for timestamp invariant SQL.

Retest:

- `docker compose exec -T aminra-backend pytest tests/test_module_service.py -q` → `9 passed`
- Full module phase gate rerun → backend `26 passed`, frontend `11 passed`, lint PASS, deploy PASS
- Final live business UAT → PASS
- Final live admin console UAT → PASS
- Promoted permanent E2E smoke rerun → `2 passed`; evidence `docs/qa/20260920-232554-module-guard-promoted-e2e-smoke/`

## Risks and caveats

- **Conditional GO, not full commercial multi-module launch**: package/billing/trial expiry/upgrade request workflow is still not complete.
- Admin console live UAT verified read/load path; safe mutation is covered by automated contract tests, but no live admin status mutation was performed to avoid unnecessary tenant-state drift.
- Sentry warnings persist during Next build; not blocking this scope but should be cleaned before production-hardening claim.
- Playwright UAT specs have been promoted from temporary scripts into maintained E2E coverage; they are credential-gated and skipped when the required demo/admin env is absent.

## Recommendation

Proceed with sandbox review of module guard enablement as **CONDITIONAL GO**.

Next P1 hardening:

1. Add a proper locked-state direct-route UX wrapper for disabled frontend pages, not only API 403 behavior.
2. Add an upgrade/request-activation workflow so disabled modules produce a sales/support path instead of a dead end.
3. Add admin live mutation UAT against a disposable tenant fixture.
