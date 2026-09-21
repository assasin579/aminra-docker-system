# AMINRA Module Locked Direct-Route UX — QA Report

Date: 2026-09-21
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `dev`
Verdict: **GO for local sandbox scoped direct-route locked UX**; **PARTIAL for production/customer-pilot**.

## Scope

P1 follow-up after scoped module guard enablement:

- Replace raw/blank/direct-route disabled module experience with a customer-facing locked-state screen.
- Keep backend/API module guard fail-closed behavior unchanged.
- Cover protected supply-chain routes:
  - `/supply-chain/materials` → `supplier_management`
  - `/supply-chain/process` → `process_digitization`
  - `/supply-chain/batches` → `traceability`
- Promote live UAT assertion so `/supply-chain/process` must show locked module UX for disabled process digitization.

## User-facing expectation

If a business user opens a disabled module by direct URL, they should see:

- clear heading: `Module chưa kích hoạt`
- module name, e.g. `Số hóa quy trình`
- link back to `/modules`: `Xem gói module của tôi`
- disabled activation CTA placeholder: `Yêu cầu kích hoạt <module>`
- no raw `403`, no blank page, no confusing broken app state

## Implementation summary

Changed files:

- `frontend/aminra-web/components/ModuleAccessGate.tsx`
  - New reusable client-side access wrapper.
  - Loads `/api/me/modules` via existing BFF path.
  - Renders children only for `enabled`/`trial`/`active` module state.
  - Renders locked-state screen for missing/disabled/locked module.
- `frontend/aminra-web/app/supply-chain/materials/page.tsx`
  - Wraps workspace in `ModuleAccessGate moduleCode="supplier_management"`.
- `frontend/aminra-web/app/supply-chain/process/page.tsx`
  - Wraps workspace in `ModuleAccessGate moduleCode="process_digitization"`.
- `frontend/aminra-web/app/supply-chain/batches/page.tsx`
  - Wraps workspace in `ModuleAccessGate moduleCode="traceability"`.
- `frontend/aminra-web/__tests__/module-access-gate-contract.test.tsx`
  - New contract tests for active, locked, and fail-closed/error states.
- `frontend/aminra-web/__tests__/supply-chain-process-create.test.tsx`
  - Updated existing process FE→BE contracts to mock active module access before testing write flows.
- `frontend/aminra-web/e2e/module-guard-live-uat.spec.ts`
  - Adds browser assertion for direct-route locked UX.

## Verification

### Source/unit-contract gates

```bash
cd frontend/aminra-web && npm run test -- \
  __tests__/module-access-gate-contract.test.tsx \
  __tests__/my-modules-customer-experience.test.tsx \
  __tests__/sidebar-module-navigation-contract.test.tsx \
  __tests__/supply-chain-process-create.test.tsx
```

Result: `4 passed`, `11 tests passed`.

```bash
cd frontend/aminra-web && npm run test -- \
  __tests__/module-access-gate-contract.test.tsx \
  __tests__/supply-chain-process-create.test.tsx
```

Final focused rerun after E2E locator fix: `2 passed`, `6 tests passed`.

### Lint/build

```bash
cd frontend/aminra-web && npm run lint
```

Result: PASS.

```bash
cd frontend/aminra-web && npm run build
```

Result: PASS. Existing Sentry/Next deprecation warnings only.

### Backend regression guard

```bash
docker compose exec -T aminra-backend pytest \
  tests/test_module_service.py \
  tests/test_module_guard.py \
  tests/test_module_route_contract.py \
  tests/test_supply_chain_module_guards.py -q
```

Result: `21 passed`.

Phase-gate deploy also ran backend module suite and reported `26 passed`.

### Deploy/runtime

Command class:

```bash
MODULE_GUARDS_ENABLED=true \
MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace \
LOG_DIR=docs/qa/20260921-004134-module-locked-direct-route-deploy \
SKIP_COMMIT=true \
STABILITY_SAMPLES=6 \
STABILITY_INTERVAL_SECONDS=3 \
scripts/automation/modularization-phase-gate.sh immutable-deploy
```

Result: PASS.

Evidence dir:

- `docs/qa/20260921-004134-module-locked-direct-route-deploy/`

Runtime env final:

```text
MODULE_GUARDS_ENABLED=true
MODULE_GUARD_ROLLOUT=supplier_management,process_digitization,traceability,public_trace
```

Health:

```text
frontend=200
public=200
```

### Live browser UAT

Final passing run:

```bash
PW_BASE_URL=http://127.0.0.1:3100 \
UAT_TENANT_ID=<redacted> \
UAT_EVIDENCE_DIR=docs/qa/20260921-005000-module-locked-direct-route-live-uat-pass/evidence \
npx playwright test \
  e2e/module-guard-live-uat.spec.ts \
  e2e/admin-module-console-live-uat.spec.ts \
  --project=desktop-chromium --reporter=list
```

Result:

```text
2 passed
```

Evidence:

- `docs/qa/20260921-005000-module-locked-direct-route-live-uat-pass/playwright.log`
- `docs/qa/20260921-005000-module-locked-direct-route-live-uat-pass/evidence/01-business-my-modules.png`
- `docs/qa/20260921-005000-module-locked-direct-route-live-uat-pass/evidence/02-disabled-process-direct-url.png`
- `docs/qa/20260921-005000-module-locked-direct-route-live-uat-pass/evidence/03-admin-tenant-module-console.png`

Note: an earlier live UAT attempt failed only because the Playwright locator was ambiguous (`Số hóa quy trình` appeared both as module label and CTA text). The UI behavior itself was present; the maintained spec was tightened to target the exact `<p>` label and rerun successfully.

## Risk assessment

### Controlled

- Backend module guard remains authoritative and fail-closed for scoped modules.
- Frontend direct-route UX now explains the locked module instead of exposing raw failure.
- Existing process FE→BE write contract still passes when module is active.

### Remaining risks / not production GO

- `Yêu cầu kích hoạt` CTA is still a disabled placeholder; no activation request workflow or admin inbox exists yet.
- Client-side route wrapper improves UX but does not replace backend enforcement; continue treating backend guards as authority.
- Rollout remains scoped to selected module codes only.
- Production/customer-pilot still blocked by broader AMINRA readiness backlog: SMTP/customer onboarding, edge/CDN SLO, dependency/security backlog, package/billing semantics.

## Verdict

- **Sandbox/local demo:** GO.
- **Production/customer pilot:** PARTIAL.

Next recommended P1: implement real activation-request workflow from locked module screen to admin/operator review, or add disposable-tenant admin mutation UAT before broadening rollout.
