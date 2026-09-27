# AMINRA three-lane 9-score readiness follow-up

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Scope: Supply-chain / CB eligibility / traceability; Multiple module architecture; Tenant isolation / IDOR / security boundaries.
Safety: backend-only deploy performed after source commit; protected stateful/frontend services were verified unchanged.

## Executive verdict

The three requested lanes were executed in parallel by separate agents, parent-verified, committed, backend-only deployed, runtime-validated, and rechecked with public trace SLO/load plus Tenant/IDOR MEDIUM triage.

Updated score estimate after source/test/evidence/runtime closure:

| Lane | Before | After | Verdict |
|---|---:|---:|---|
| Supply-chain / CB eligibility / traceability | 7.5/10 | 9.0/10 | 9 for source/runtime/local/public correctness; WARN on public concurrency-30 p95 until Cloudflare edge cache HIT |
| Multiple module architecture | 8.0/10 | 9.0/10 | 9 for module lifecycle invariant + DB-backed runtime smoke; product billing/operator semantics still future scope |
| Tenant isolation / IDOR / security boundaries | 8.0/10 | 9.0/10 | 9-score source/evidence gate met; MEDIUM scanner triaged, no HIGH |

Strict production/customer-pilot remains PARTIAL because dependency/security backlog, SMTP/customer onboarding, and broader mobile/browser/a11y gates are outside this scope.

## Lane 1 — Supply-chain / CB eligibility / traceability

Changed files:
- backend/supply_chain/models.py
- backend/tests/test_supply_chain_supplier_eligibility_routes.py
- docs/qa/2026-09-27-supply-chain-traceability-9-score/report.md
- docs/qa/2026-09-27-public-trace-slo-load/*

Closed gaps:
- Added API-model fail-closed validation for supplier eligibility inverted validity windows (`valid_until < valid_from`) before database write.
- DB CHECK remains second-line guard.
- Seeded deterministic public trace fixture.
- Verified valid/invalid public trace behavior and absence of obvious private-field leaks.
- Ran split SLO/load local backend vs local frontend proxy vs public frontend proxy.

Evidence:
- Focused supply-chain/eligibility/traceability gate: 50 passed, 1 skipped.
- Runtime deployed backend gate: included in 102 passed.
- Public trace valid/invalid smoke: PASS.
- Load: local backend c30 p95 463.2 ms PASS; local frontend proxy c30 p95 389.5 ms PASS; public warmed c20 p95 767.6 ms PASS.
- WARN: public c30 p95 remains >800 ms and `cf-cache-status: dynamic`.

## Lane 2 — Multiple module architecture

Changed files:
- backend/auth/module_service.py
- backend/tests/test_module_service.py
- docs/qa/2026-09-27-module-architecture-9-score/report.md
- docs/qa/2026-09-27-runtime-validation/*

Closed gaps:
- Hardened admin module status transitions so `tenant_modules` lifecycle timestamps remain consistent with migration constraints:
  - `enabled`/`trial`: set `enabled_at`, clear `disabled_at`.
  - `disabled`/`locked`: set `disabled_at`, clear `enabled_at`.
- Runtime DB-backed smoke exposed and fixed an asyncpg ambiguity by casting `$3::varchar` consistently in the update statement.
- DB-backed runtime smoke then passed in a rollback transaction.

Evidence:
- Focused module service source gate: 20 passed.
- Runtime test batch: 102 passed.
- DB-backed module smoke: PASS.

Residual product caveat:
- Product-level billing/package semantics and external operator channel policy remain future scope.

## Lane 3 — Tenant isolation / IDOR / security boundaries

Changed files:
- backend/tests/test_route_tenant_inventory_coverage.py
- backend/tests/test_unauth_route_boundaries.py
- scripts/qa/build_route_tenant_inventory.py
- docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv
- docs/qa/2026-09-27-tenant-idor-9-score/*
- docs/qa/2026-09-27-tenant-idor-medium-triage/*

Closed gaps:
- Route inventory regenerated: 273 routes.
- P0/P1 deferred or unmapped routes: 0.
- Added stricter regression gate: P0/P1 must be `covered` with executable evidence.
- Expanded anonymous negative probes for auth/me, feature flags, official artifacts, CB trust decision routes, conflicts, complaints, module activation, and other high-risk surfaces.
- Static scanner remains 0 HIGH.
- MEDIUM findings triaged by family/severity disposition.

Evidence:
- Route inventory + unauth negative gate: 57 passed.
- Focused route-family regression: 23 passed, 6 skipped.
- Static scanner: 189 findings, 0 HIGH, 181 MEDIUM, 8 INFO.
- Parent/live rerun: 57 passed.
- Runtime deployed backend batch: 102 passed.

Residual:
- MEDIUM scanner findings are triaged prompts, not all direct wrong-role/cross-tenant live-token tests.
- Continue converting representative coverage into direct route-family live-token coverage over time.

## Backend-only deploy/runtime validation

PASS:
- Built `aminra-backend`.
- Recreated only `aminra-backend` via `docker compose up -d --no-deps aminra-backend`.
- Verified unchanged StartedAt for postgres-db, qdrant-db, redis, keycloak, and aminra-frontend.
- Backend reached healthy after 15 seconds.
- Health checks all 200: backend, local frontend, local frontend API, public health with browser UA.

## Remaining release blockers outside this scope

- Dependency/security backlog: direct high/critical npm findings remain.
- SMTP/customer onboarding gate must be rerun for customer/pilot sign-off.
- Cloudflare edge cache rule was prepared/fixed for `aminra.org` but not applied because Cloudflare credentials are not present in this session environment.
- Mobile/cross-browser/a11y coverage remains partial.
