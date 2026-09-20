# AMINRA Module Enforcement Sandbox-Ready Implementation Plan

> **For Hermes:** Implement automatically with strict TDD. Do not commit/push/deploy unless explicitly authorized.

**Goal:** Close the module-registry risks enough to mark AMINRA `sandbox ready` for controlled multi-module demo, without claiming production/customer-pilot readiness.

**Architecture:** Keep the existing modular monolith. Add scoped module-guard rollout, route coverage contracts, dependency-safe tenant-module admin API primitives, and a sandbox readiness evidence report. Do not introduce microservices or billing infrastructure in this pass.

**Tech Stack:** FastAPI, asyncpg-style DB adapter, Alembic-backed module registry, pytest source/contract tests, Next.js sidebar contract tests.

---

## Success criteria

AMINRA can be called **sandbox ready for multi-module demo** only if all of these are true:

1. **Scoped guard rollout exists**: `MODULE_GUARDS_ENABLED=true` can be combined with a module allowlist so only reviewed module guards enforce.
2. **Supply-chain route coverage is explicit**: authenticated supplier/material/process/batch management routes have module guard ownership; public token/QR trace routes are intentionally documented exceptions.
3. **Dependency enforcement exists**: enabling/disabling tenant modules checks `required` dependencies and reverse dependents; no invalid module graph can be created via admin tooling.
4. **Admin management plane exists at backend level**: platform admin can list a tenant’s modules and safely set status/source/config through API. Frontend admin UI is nice-to-have, not required for sandbox readiness.
5. **Frontend current-user sidebar remains module-aware** and fail-open behavior is preserved for controlled rollout until backend guards are deliberately enabled.
6. **Verification gates pass**: focused backend module tests, route contract tests, frontend sidebar module contract, compile/diff checks.
7. **Verdict lanes are honest**: sandbox demo can be PASS while production/customer pilot remains PARTIAL/NO-GO for unrelated SMTP/edge/dependency gates.

## Risk closure map

- RISK: guard default-off / unsafe global enablement
  ACTION: add `MODULE_GUARD_ROLLOUT` module allowlist; tests prove non-allowlisted modules stay fail-open even when global flag is true.

- RISK: backend guard coverage too narrow
  ACTION: add route-level guards for protected supplier and batch routes; keep public trace and supplier portal routes public by explicit exception; add static route contract.

- RISK: no admin module management
  ACTION: add backend admin router endpoints:
  - `GET /auth/admin/tenants/{tenant_id}/modules`
  - `PATCH /auth/admin/tenants/{tenant_id}/modules/{module_code}`

- RISK: dependency violations during toggle
  ACTION: service-level validation:
  - enabling a module requires all `required` prerequisites to be enabled/trial;
  - disabling/locking a module is blocked if enabled/trial dependents require it;
  - `required` default module cannot be disabled unless future policy adds explicit break-glass.

- RISK: commercial plan layer missing
  ACTION: document as **out of sandbox scope** but not omitted; sandbox uses existing business-model bundles, production packaging remains separate milestone.

## Bite-sized execution tasks

### Task 1 — Add scoped rollout contract

**Files:**
- Modify: `backend/auth/module_guard.py`
- Test: `backend/tests/test_module_guard.py`

**Steps:**
1. Add failing tests for `MODULE_GUARD_ROLLOUT`.
2. Implement parser supporting empty/all/module-code CSV.
3. Verify `MODULE_GUARDS_ENABLED=true` + rollout missing module => no DB call/fail-open.

### Task 2 — Add dependency validation/service API

**Files:**
- Modify: `backend/auth/module_service.py`
- Test: `backend/tests/test_module_service.py`

**Steps:**
1. Add fail-first tests for dependency-required enable and reverse-dependent disable.
2. Implement `set_tenant_module_status(...)` with transaction-friendly SQL and admin override source.
3. Keep config JSON normalized.

### Task 3 — Add admin backend module endpoints

**Files:**
- Modify: `backend/auth/module_router.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_module_route_contract.py`

**Steps:**
1. Add source/route contract asserting admin router is mounted.
2. Implement list/update endpoints using `require_admin`.
3. Do not add FE admin UI yet unless backend tests are green.

### Task 4 — Guard protected supply-chain routes

**Files:**
- Modify: `backend/supply_chain/supplier_router.py`
- Modify: `backend/supply_chain/batch_router.py`
- Test: `backend/tests/test_module_route_contract.py`

**Steps:**
1. Add route contract matrix for supplier/material/process/batch ownership.
2. Add route-level `dependencies=[Depends(require_module(...))]` to protected routes.
3. Preserve explicit exceptions: `/supplier-portal/{token}`, `/supplier-portal/{token}/upload`, `/batches/trace/{trace_id}`.

### Task 5 — Verification and sandbox verdict report

**Commands:**
- `cd backend && pytest tests/test_module_guard.py tests/test_module_service.py tests/test_module_route_contract.py -q`
- `cd backend && python -m py_compile auth/module_guard.py auth/module_service.py auth/module_router.py supply_chain/supplier_router.py supply_chain/batch_router.py`
- `cd frontend/aminra-web && npm test -- __tests__/sidebar-module-navigation-contract.test.tsx --runInBand` or project-equivalent Vitest command
- `git diff --check`

**Expected verdict:**
- `sandbox multi-module readiness`: PASS if gates pass.
- `production/customer pilot`: remains PARTIAL unless unrelated SMTP/edge/dependency gates are resolved.

## Out of scope for this automatic pass

- No commit/push/deploy without explicit authorization.
- No billing/pricing UI or plan enforcement.
- No broad `MODULE_GUARDS_ENABLED=true` runtime flip.
- No frontend admin console unless requested after backend management plane is stable.
