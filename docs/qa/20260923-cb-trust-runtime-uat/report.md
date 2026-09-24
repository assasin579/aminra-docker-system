# AMINRA CB Trust Core — Runtime Migration + Sandbox UAT Report

Date: 2026-09-23
Branch: `feat/cb-trust-core-rbac-decisions`
Commit: `1950dda feat(cb-trust): add core decision controls`
Mode: local/sandbox runtime validation after founder approval

## Verdict

**SANDBOX RUNTIME PASS for CB Trust Core basic runtime availability and guarded route behavior.**

This is **not** production/customer-pilot GO. It proves that the committed CB Trust Core source can be migrated, rebuilt, loaded by the local runtime, and smoke-tested with real provider/business tokens for representative endpoints. Broader end-to-end workflow UAT, admin/CB-admin browser lanes, mobile/cross-browser, SMTP/customer onboarding, edge/CDN SLO, dependency/security backlog remain outside this gate.

## Safety controls

- Pre-migration PostgreSQL backup created before Alembic upgrade:
  - `/home/user/Documents/backups/aminra/pre-cb-trust-runtime-20260923-204558/aminra.dump`
  - SHA256: `b6504168801baad720be7565c91c9be3c515ab1b7a8f391cdf40a1d6f7d7139c`
- Schema-only backup:
  - `/home/user/Documents/backups/aminra/pre-cb-trust-runtime-20260923-204558/aminra-schema-before.sql`
  - SHA256: `b6af0fa9d6b461cbb828844c3f25dccb8a22fa74770c96d0a2312a682dc12f3b`
- Protected service `StartedAt` values before/after rebuild matched for:
  - `postgres-db`
  - `qdrant-db`
  - `redis`
  - `keycloak`
- Backend/frontend were recreated with `--no-deps`; protected stateful/runtime dependencies were not restarted.

## Migration evidence

Before migration:

```text
046_module_activation_escal
```

Upgrade path executed:

```text
046_module_activation_escal -> 047_cert_decisions
047_cert_decisions -> 048_conflicts_interest
048_conflicts_interest -> 050_complaints_appeals
```

After migration:

```text
050_complaints_appeals (head)
```

Verified tables:

```text
certification_decision_events
certification_decisions
complaint_case_events
complaint_cases
conflict_declarations
conflict_overrides
```

## Build/recreate evidence

- `docker compose build aminra-backend aminra-frontend` PASS.
- Next.js build included new static routes:
  - `/conflicts`
  - `/complaints`
- Known existing non-blocking warnings: Sentry/Next instrumentation deprecation warnings.
- `docker compose up -d --no-deps aminra-backend aminra-frontend` PASS.

Post-recreate services:

```text
aminra-backend    healthy
aminra-frontend   healthy
postgres-db       healthy
qdrant-db         healthy
redis             healthy
keycloak          healthy
```

Health/smoke:

```text
backend_health ok connected connected
frontend_health 200
local_conflicts 200
local_complaints 200
public_health 200
```

Recent backend/frontend fatal/error log scan: clean.

## Runtime UAT evidence

Credential handling: sourced gitignored QA credential env; tokens/passwords were not printed.

```text
provider token PASS
business token PASS
noauth_conflicts PASS http=401
noauth_complaints PASS http=401
noauth_decisions PASS http=401
provider_auth_me PASS http=200 keys=address,company_code,company_name,email,id,industry_schema_code
business_auth_me PASS http=200 keys=address,company_code,company_name,email,id,industry_schema_code
provider_conflicts_list PASS http=200 keys=conflicts
provider_complaints_list PASS http=200 keys=cases
business_complaints_list PASS http=200 keys=cases
business_conflicts_forbidden PASS http=403 keys=detail
provider_decision_missing_submission PASS http=404 keys=detail
frontend_conflicts 200
frontend_complaints 200
```

Browser smoke:

- `http://127.0.0.1:3100/conflicts` rendered heading `Conflict-of-Interest Register` with declaration/review/override controls.
- `http://127.0.0.1:3100/complaints` rendered heading `Complaints & Appeals` with create/assign/transition controls.

## Focused regression evidence after runtime rebuild

Backend focused runtime-image tests:

```text
34 passed in 3.05s
```

Covered:

- policy engine
- migration contracts
- certificate decision gate
- conflict interest service
- complaints/appeals service

Frontend focused host contracts:

```text
Test Files 2 passed
Tests 2 passed
```

## Scope not covered / remaining gates

- Full credentialed browser E2E for end-to-end decision/create/review/appeal workflows was not run.
- Admin/CB-admin credential lane was not used in this pass; provider/business token lanes were sufficient for representative route smoke but not full role-matrix signoff.
- No push to remote was performed.
- No production deployment was performed.
- Customer/production GO remains blocked by existing SMTP/customer onboarding, public edge/CDN SLO, dependency/security backlog, and broader UAT coverage.

## Final recommendation

Treat CB Trust Core as **local sandbox runtime PASS / production PARTIAL**.

Safe next options:

1. Push branch for remote backup/PR review.
2. Extend credentialed Playwright UAT for full workflows and screenshots.
3. Add a reusable CB Trust browser UAT runner before any customer-facing demo claim.
