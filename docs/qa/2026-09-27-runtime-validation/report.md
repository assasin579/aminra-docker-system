# Backend-only deploy/runtime validation

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Code commit deployed: ff40e38

## Verdict

PASS with one correction discovered during runtime validation.

The first DB-backed module activation smoke exposed a real deployed-query issue: asyncpg could not infer `$3` type in `set_tenant_module_status()` because `$3` was used both as status assignment and CASE comparison. The fix casts `$3::varchar` consistently, the commit was amended, backend image rebuilt, and backend-only deploy rerun.

## Backend-only deploy

Method:
- Built `aminra-backend` image.
- Recreated only `aminra-backend` via `docker compose up -d --no-deps aminra-backend`.
- Verified protected service StartedAt values unchanged:
  - postgres-db unchanged
  - qdrant-db unchanged
  - redis unchanged
  - keycloak unchanged
  - aminra-frontend unchanged

Evidence:
- `protected-started-at-before-final.tsv`
- `post-deploy-health-and-runtime-tests.txt`
- `module-runtime-smoke.txt`

## Health checks

PASS:
- backend `/health`: 200
- local frontend `/health`: 200
- local frontend `/api/health`: 200
- public `https://aminra.org/health`: 200 with browser UA

## Runtime tests

PASS:
- `tests/test_supplier_eligibility_service.py`
- `tests/test_supply_chain_supplier_eligibility_routes.py`
- `tests/test_module_service.py`
- `tests/test_route_tenant_inventory_coverage.py`
- `tests/test_unauth_route_boundaries.py`

Result: 102 passed.

## DB-backed module smoke

PASS:
- Selected safe non-required module row.
- `disabled` transition: `enabled_at IS NULL`, `disabled_at IS NOT NULL`, `source='admin_override'`.
- `trial` transition: `enabled_at IS NOT NULL`, `disabled_at IS NULL`, `source='admin_override'`.
- Transaction rolled back; no persistent tenant/module change.
