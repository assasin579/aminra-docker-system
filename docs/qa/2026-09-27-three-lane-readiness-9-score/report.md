# AMINRA three-lane 9-score readiness follow-up

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Scope: Supply-chain / CB eligibility / traceability; Multiple module architecture; Tenant isolation / IDOR / security boundaries.
Safety: no commit, no push, no deploy, no destructive cleanup, no broad dependency upgrade.

## Executive verdict

The three requested lanes were executed in parallel by separate agents and then parent-verified.

Updated score estimate after source/test/evidence closure:

| Lane | Before | After | Verdict |
|---|---:|---:|---|
| Supply-chain / CB eligibility / traceability | 7.5/10 | 8.7/10 | Near 9; pending public trace SLO/load gate |
| Multiple module architecture | 8.0/10 | 8.8/10 | Near 9; pending runtime DB-backed admin activation smoke + product semantics caveats |
| Tenant isolation / IDOR / security boundaries | 8.0/10 | 9.0/10 | 9-score source/evidence gate met, with medium scanner backlog caveat |

Strict production/customer-pilot remains PARTIAL because dependency/security backlog, SMTP/customer onboarding, public edge/SLO, and broader mobile/browser/a11y gates are outside this scope.

## Lane 1 — Supply-chain / CB eligibility / traceability

Changed files:
- backend/supply_chain/models.py
- backend/tests/test_supply_chain_supplier_eligibility_routes.py
- docs/qa/2026-09-27-supply-chain-traceability-9-score/report.md

Closed gap:
- Added API-model fail-closed validation for supplier eligibility inverted validity windows (`valid_until < valid_from`) before database write.
- DB CHECK remains second-line guard.

Evidence:
- Focused supply-chain/eligibility/traceability gate: 50 passed, 1 skipped.
- Parent combined source gate includes same lane and passed.

Residual to true 9/10:
- Run public trace SLO/load gate against approved local/public target with seeded valid/invalid trace IDs.

## Lane 2 — Multiple module architecture

Changed files:
- backend/auth/module_service.py
- backend/tests/test_module_service.py
- docs/qa/2026-09-27-module-architecture-9-score/report.md

Closed gap:
- Hardened admin module status transitions so `tenant_modules` lifecycle timestamps remain consistent with migration constraints:
  - `enabled`/`trial`: set `enabled_at`, clear `disabled_at`.
  - `disabled`/`locked`: set `disabled_at`, clear `enabled_at`.

Evidence:
- Focused module service source gate: 20 passed.
- Focused module architecture/guard/route/activation contracts: 20 passed.
- Parent combined source gate includes same lane and passed.

Residual to true 9/10:
- After approved deploy/runtime lane, run DB-backed admin activation smoke via real admin API and verify timestamp transitions in DB.
- Product-level billing/package semantics and external operator channel policy remain unresolved.

## Lane 3 — Tenant isolation / IDOR / security boundaries

Changed files:
- backend/tests/test_route_tenant_inventory_coverage.py
- backend/tests/test_unauth_route_boundaries.py
- scripts/qa/build_route_tenant_inventory.py
- docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv
- docs/qa/2026-09-27-tenant-idor-9-score/*

Closed gaps:
- Route inventory regenerated: 273 routes.
- P0/P1 deferred or unmapped routes: 0.
- Added stricter regression gate: P0/P1 must be `covered` with executable evidence.
- Expanded anonymous negative probes for auth/me, feature flags, official artifacts, CB trust decision routes, conflicts, complaints, module activation, and other high-risk surfaces.
- Static scanner remains 0 HIGH.

Evidence:
- Route inventory + unauth negative gate: 57 passed.
- Focused route-family regression: 23 passed, 6 skipped.
- Static scanner: 189 findings, 0 HIGH, 181 MEDIUM, 8 INFO.
- Parent rerun with live backend URL: 57 passed.

Residual:
- 181 MEDIUM scanner prompts still need route-family triage.
- Not every route has direct wrong-role + cross-tenant live-token tests; some rely on representative coverage.

## Parent verification

Commands run:

```bash
git diff --check
```

Result: PASS.

```bash
docker compose run --rm -T --no-deps \
  -e TEST_BACKEND_URL=http://aminra-backend:8000 \
  -v "$PWD:/repo" -w /repo/backend aminra-backend pytest \
  tests/test_route_tenant_inventory_coverage.py \
  tests/test_unauth_route_boundaries.py -q
```

Result: PASS — 57 passed.

```bash
docker compose run --rm -T --no-deps -v "$PWD:/repo" -w /repo/backend aminra-backend pytest \
  tests/test_supplier_eligibility_service.py \
  tests/test_supply_chain_supplier_eligibility_routes.py \
  tests/test_supply_chain_sealing.py \
  tests/test_module_service.py \
  tests/test_module_guard.py \
  tests/test_module_route_contract.py \
  tests/test_supply_chain_module_guards.py \
  tests/test_module_registry_migration.py \
  tests/test_module_activation_browser_uat_runner_contract.py \
  tests/test_certification_decision_router.py \
  tests/test_complaints_appeals_router.py \
  tests/test_conflict_interest_router.py \
  tests/test_official_artifact_separation_contract.py \
  tests/test_official_artifacts_service.py \
  tests/test_feature_flags_integration.py::TestMyFeatureFlags \
  tests/test_feature_flags_integration.py::TestTenantIsolation::test_my_endpoint_does_not_leak_other_tenant_overrides -q
```

Result: PASS — 113 passed, 7 skipped.

Notes:
- One attempted parent combined command failed because route-inventory tests resolved `/repo/backend/docs/...` under a full repo mount and unauth tests targeted `localhost:8000` from a transient container. This exposed a harness portability issue, not a product failure. The route inventory root detection was hardened, and the live-HTTP test was rerun with `TEST_BACKEND_URL=http://aminra-backend:8000`, then passed.

## Remaining release blockers outside this scope

- Dependency/security backlog: direct high/critical npm findings remain.
- SMTP/customer onboarding gate must be rerun for customer/pilot sign-off.
- Public edge/CDN SLO gate remains separate from backend/source confidence.
- Mobile/cross-browser/a11y coverage remains partial.
- No commit/push/deploy has been performed in this follow-up.
