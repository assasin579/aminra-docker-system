# AMINRA Supply-Chain Traceability — Production QA Execution Report

Date: 2026-09-11  
Executor: Hermes Agent  
Execution file: `docs/qa/2026-09-11-supply-chain-traceability-production-qa-execution.md`  
Evidence root: `docs/qa/2026-09-11-supply-chain-traceability-production/`

---

## Verdict

**PARTIAL — immediate P0 QA blockers are fixed and verified in sandbox, but production sign-off remains blocked by broader pilot-readiness evidence gaps.**

**UPDATED 2026-09-11 after executing next actions:** the three immediate blockers DEF-001/002/003 are now fixed and verified in the local/public sandbox evidence set. Remaining status is **PARTIAL, not production GO**, because live multi-role business/provider/admin browser E2E, full audit matrix, load, and chaos/resilience tests remain unexecuted.

**P0 runtime re-smoke addendum:** backend was recreated from the rebuilt image, deterministic trace fixture was re-seeded, local backend API `/api/supply-chain/batches/trace/{public_trace_id}` returns **HTTP 200**, invalid and injection-shaped IDs return **HTTP 404**, hydrated public browser page renders the successful QA trace, actual public browser proxy path `/api/api/supply-chain/batches/trace/{public_trace_id}` returns **HTTP 200**, and targeted backend/ARQ log scan is clean. Evidence: `46-backend-recreate-after-build.txt`, `47-reseed-public-trace-fixture-after-backend-recreate.txt`, `50-public-trace-correct-endpoint-resmoke-after-recreate.txt`, `51-log-scan-after-public-trace-resmoke.txt`, `52-public-next-actual-proxy-resmoke.txt`, screenshot `public-valid-trace-after-backend-recreate.png`.

This is **not** a production `GO` yet.

Why:

- Backend focused P0 gate is green unmodified after fixture repair: **163 passed, 1 skipped**.
- Backend supply-chain regression is green unmodified after fixture repair: **264 passed, 1 skipped**.
- Frontend full suite is green: **238 passed**.
- Frontend lint/build are green.
- Runtime local/public basic smoke is green, including deterministic valid public trace `200` through backend API and public browser proxy.
- Public invalid/malformed/injection-shaped trace fails closed with `404` and clean browser not-found UI.
- Migration head is correct: `040_public_trace_id (head)` via project wrapper.

But:

- Real multi-role business/provider/admin browser E2E with credentials was not executed in this run.
- Full 365-case matrix, load/performance soak, chaos/resilience dependency tests, and full accessibility/browser matrix remain unexecuted.
- Direct destructive migration downgrade/upgrade was not run against the live sandbox DB; only migration-wrapper current checks and transactional migration tests were used.

---

## Environment

- Repo: `/home/user/Documents/aminra-docker-system`
- Branch: `dev`
- Commit: `ed0893f`
- Dirty tree before/after: new QA execution/report artifacts only
- Backend: healthy
- Frontend: healthy
- Postgres: healthy
- Qdrant: healthy
- Keycloak: healthy
- Redis: healthy
- ARQ worker: running, but one job error observed
- Local URL: `http://localhost:3100` → `HTTP 200`
- Public sandbox URL: `https://dev-web.silvergem.org` → `HTTP 200`
- Backend health: database connected, qdrant connected
- Alembic head: `040_public_trace_id (head)`

Evidence:

- `evidence/terminal/00-environment-baseline.txt`
- `evidence/terminal/01-alembic-current-wrapper.txt`
- `evidence/terminal/40-git-hygiene.txt`

---

## Scope executed

Executed:

1. Environment/service baseline.
2. Alembic current verification using project wrapper.
3. Backend focused supply-chain/public-trace/sealing/eligibility tests.
4. Backend broader supply-chain regression.
5. Frontend supply-chain guardrails.
6. Frontend lint.
7. Frontend build.
8. Frontend full Vitest suite.
9. Runtime local/public smoke.
10. Public invalid/malformed trace fail-closed smoke.
11. Browser visual check for invalid public trace page.
12. High-signal container log scan.
13. Git hygiene check.

Not executed / blocked:

- Real multi-role browser E2E with credentials; no credentials were provided in this run.
- Destructive migration downgrade/upgrade on live sandbox DB; not run as a direct DB mutation. Transactional migration tests did run and passed.
- Load/performance soak.
- Chaos/resilience destructive dependency tests.
- Full accessibility/browser matrix.

Previously blocked live positive public trace `200` browser/API smoke is now executed and passed using deterministic sealed fixture `QA-TRACE-PUBLISHED-SEALED-001`.

---

## Test result summary

### Addendum — next actions executed 2026-09-11

- DEF-001 stale supplier eligibility fixture: **FIXED**. `backend/tests/test_supplier_eligibility_service.py` now applies migrations 038 + 039 in order. Unmodified backend P0 focused gate passes: **163 passed, 1 skipped**.
- DEF-002 missing positive public trace fixture: **FIXED**. Added `scripts/qa/seed-public-trace-fixture.py`, seeded `QA-TRACE-PUBLISHED-SEALED-001` with public trace ID `73695b8a-3c10-570b-8bba-92c12da9b56e`, verified local backend API `HTTP 200`, public/ local trace page `HTTP 200`, integrity verified, snapshot version 2, and no private-field leakage markers (`tenant_id`, `provider_id`, `source_certificate_id`, `changed_by`).
- Browser evidence: `evidence/screenshots/public-valid-trace-qa-fixture.png` shows successful public trace page for `QA Published Sealed Halal Trace Fixture`.
- P0 runtime re-smoke after backend image recreate: **PASS**. Backend container recreated from rebuilt image, fixture re-seeded, local backend API returns `HTTP 200`, invalid/injection-shaped IDs return `HTTP 404`, actual browser fetch path `/api/api/supply-chain/batches/trace/{public_trace_id}` returns `HTTP 200`, hydrated browser screenshot captured, and backend/ARQ targeted log scan is clean.
- DEF-003 ARQ worker DB unavailable: **FIXED**. Root cause: ARQ worker did not mount `/vault/secrets`, so `entrypoint.sh` could not source `DATABASE_URL`; additionally `mark_alert_sent()` reused one parameter as both text and int in asyncpg. Fixed worker lifecycle DB init/shutdown, mounted `vault-secrets`, split bind params, rebuilt/recreated worker, and verified `daily_cert_expiry_alerts` dry-run completes: `{'sent': 1, 'failed': 0, 'checked': 1}`.

New evidence:

- `evidence/terminal/33-seed-public-trace-fixture.txt`
- `evidence/terminal/34-positive-public-trace-smoke.txt`
- `evidence/screenshots/public-valid-trace-qa-fixture.png`
- `evidence/terminal/36-arq-worker-after-recreate.txt`
- `evidence/terminal/38-arq-worker-after-second-recreate.txt`
- `evidence/terminal/39-arq-daily-cert-dry-run-after-param-fix.txt`
- `evidence/terminal/41-focused-regression-after-next-actions.txt`
- `evidence/terminal/46-backend-recreate-after-build.txt`
- `evidence/terminal/47-reseed-public-trace-fixture-after-backend-recreate.txt`
- `evidence/terminal/50-public-trace-correct-endpoint-resmoke-after-recreate.txt`
- `evidence/terminal/51-log-scan-after-public-trace-resmoke.txt`
- `evidence/terminal/52-public-next-actual-proxy-resmoke.txt`
- `evidence/screenshots/public-valid-trace-after-backend-recreate.png`

### P0/P1 automated source gates

- Backend P0 focused, unmodified run:
  - Result: **FAIL due to 1 stale fixture test**
  - Count: **162 passed, 1 skipped, 1 failed**
  - Evidence: `evidence/terminal/11-backend-p0-focused-tests-retry.txt`

- Backend P0 focused, excluding known stale fixture test:
  - Result: **PASS**
  - Count: **162 passed, 1 skipped, 1 deselected**
  - Evidence: `evidence/terminal/12-backend-p0-focused-tests-excluding-stale-fixture.txt`

- Backend supply-chain regression, excluding known stale fixture test:
  - Result: **PASS**
  - Count: **263 passed, 1 skipped, 1 deselected**
  - Evidence: `evidence/terminal/13-backend-supply-chain-regression.txt`

- Frontend supply-chain guardrails:
  - Result: **PASS**
  - Count: **12 passed**
  - Evidence: `evidence/terminal/20-frontend-supply-chain-guardrails.txt`

- Frontend full Vitest:
  - Result: **PASS**
  - Count: **238 passed**
  - Evidence: `evidence/terminal/23-frontend-full-vitest.txt`

- Frontend lint:
  - Result: **PASS**
  - Evidence: `evidence/terminal/21-frontend-lint.txt`

- Frontend build:
  - Result: **PASS**
  - Evidence: `evidence/terminal/22-frontend-build.txt`

### Runtime smoke

- Compose services: backend/frontend/postgres/qdrant/keycloak/redis healthy; arq-worker running.
- Backend `/health`: database/qdrant connected.
- Local frontend `/`: `HTTP 200`.
- Public sandbox `/`: `HTTP 200`.
- Public invalid trace `/api/supply-chain/public/trace/ABC123`: `HTTP 404`.
- Public malformed/injection-shaped trace: `HTTP 404`.
- Local invalid trace: `HTTP 404`.
- Browser `/trace/ABC123`: clean Vietnamese not-found UI.

Evidence:

- `evidence/terminal/30-runtime-smoke.txt`
- `evidence/screenshots/public-invalid-trace-not-found.png`

### Migration/data integrity

- Alembic current via wrapper: **PASS**, `040_public_trace_id (head)`.
- Transactional migration tests: **PASS** inside backend supply-chain regression.
- Direct sandbox downgrade/upgrade: **NOT RUN** for safety; requires explicit approval or disposable DB clone.

Evidence:

- `evidence/terminal/01-alembic-current-wrapper.txt`
- `evidence/terminal/13-backend-supply-chain-regression.txt`

### Logs/observability

- High-signal log scan found expected DB errors from negative tests.
- Also found one ARQ worker job failure: `daily_cert_expiry_alerts failed, RuntimeError: Database not available`.

Evidence:

- `evidence/terminal/32-high-signal-log-scan.txt`

---

## Critical findings

### P1 — Missing valid public trace runtime fixture blocks full public trace sign-off

The sandbox currently has `production_batches.public_trace_id` candidates, but observed candidates were not `public_trace_enabled=true`.

Impact:

- Negative/fail-closed public trace behavior is proven.
- Positive live public trace page rendering is **not** proven in this run.

Required action:

- Seed a deterministic public-enabled sealed QA fixture and add it to runtime smoke.

Defect:

- `defects/DEFECTS.md#def-002`

### P2 — Stale test fixture causes false red in backend P0 unmodified gate

The test `test_list_eligible_suppliers_filters_fail_closed` applies migration 038 only. Current production service selects 039-added columns.

Impact:

- Product DB schema at head has `provider_id`; broader regression passes when this stale fixture test is deselected.
- But release discipline says unmodified regression should not stay red.

Required action:

- Update test fixture to apply 038 + 039 or rely on current migration-head schema.

Defect:

- `defects/DEFECTS.md#def-001`

### P2 — ARQ daily certificate expiry alert job logged DB unavailable

Impact:

- Does not break public trace read path.
- May affect compliance-risk alerting and detection freshness.

Required action:

- Verify ARQ DB env/retry behavior and add dry-run worker smoke.

Defect:

- `defects/DEFECTS.md#def-003`

### P3 — Execution file Alembic command needs wrapper/env sourcing

Impact:

- Raw command fails without Vault env; wrapper works.

Required action:

- Update execution file to use `./scripts/db-migrate.sh current`.

Defect:

- `defects/DEFECTS.md#def-004`

---

## Invariant coverage assessment

### Opaque public trace ID

Status: **PASS at source-test level; runtime positive path blocked**

Evidence:

- Backend sealing/public trace tests included opaque ID and business-code rejection cases.
- Public invalid `ABC123` returns `404`.

Gap:

- Need persistent valid public trace fixture for runtime positive page.

### Fail-closed public trace

Status: **PASS**

Evidence:

- Source tests cover sealed-only/public-enabled behavior.
- Runtime invalid and injection-shaped trace IDs return `404`.
- Browser invalid trace renders clean not-found UI.

### Immutable sealed snapshot

Status: **PASS at source-test level**

Evidence:

- Backend sealing tests passed in broader regression after stale fixture deselect.

Gap:

- Runtime/browser positive snapshot rendering not proven due missing fixture.

### CB/provider-authoritative supplier eligibility

Status: **PASS at source-test level, with one stale fixture issue**

Evidence:

- Supplier eligibility route/service tests largely passed.
- Business self-authorize and provider authority tests included in backend suite.

Gap:

- One stale fixture test must be repaired and re-enabled.

### Cross-tenant/provider boundaries

Status: **PASS at source-test level**

Evidence:

- Supply-chain regression includes cross-tenant material/batch/supplier/photo and provider authority tests.

Gap:

- Live browser/API role smoke with real credentials not run.

### Audit/compliance

Status: **PARTIAL**

Evidence:

- Some audit-side effects covered in tests.

Gap:

- Full audit/compliance matrix from execution file not exhaustively run.
- ARQ risk alert job failure requires follow-up.

---

## Evidence index

Terminal evidence:

- `00-environment-baseline.txt`
- `01-alembic-current-wrapper.txt`
- `09-copy-backend-tests-into-container.txt`
- `09b-pytest-harness-config.txt`
- `10-backend-p0-focused-tests.txt`
- `11-backend-p0-focused-tests-retry.txt`
- `12-backend-p0-focused-tests-excluding-stale-fixture.txt`
- `13-backend-supply-chain-regression.txt`
- `20-frontend-supply-chain-guardrails.txt`
- `21-frontend-lint.txt`
- `22-frontend-build.txt`
- `23-frontend-full-vitest.txt`
- `30-runtime-smoke.txt`
- `31-public-trace-fixture-candidates.txt`
- `31b-production-batches-schema.txt`
- `32-high-signal-log-scan.txt`
- `40-git-hygiene.txt`

API/browser artifacts:

- `evidence/api/local-home.html`
- `evidence/api/public-home.html`
- `evidence/api/public-trace-invalid-ABC123.html`
- `evidence/api/public-trace-invalid-injection.html`
- `evidence/api/local-trace-invalid-ABC123.html`
- `evidence/screenshots/public-invalid-trace-not-found.png`

Defects:

- `defects/DEFECTS.md`

---

## Commands run

Representative commands:

```bash
./scripts/db-migrate.sh current

docker compose exec -T aminra-backend pytest \
  /app/tests/test_supply_chain_sealing.py \
  /app/tests/test_supply_chain_batches.py \
  /app/tests/test_supply_chain_materials.py \
  /app/tests/test_supply_chain_supplier_eligibility_routes.py \
  /app/tests/test_supplier_eligibility_service.py \
  /app/tests/test_migrations_supplier_eligibility.py -q

docker compose exec -T aminra-backend sh -lc \
  "pytest /app/tests/test_supply_chain_*.py /app/tests/test_supplier_eligibility_service.py /app/tests/test_migrations_supplier_eligibility.py -q -k 'not test_list_eligible_suppliers_filters_fail_closed'"

cd frontend/aminra-web
npm run test:guardrails:supply-chain
npm run lint
npm run build
npm test

curl -fsS http://localhost:8100/health
curl -sS -o ... -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org/
curl -sS -o ... -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org/api/supply-chain/public/trace/ABC123
curl -sS -o ... -w 'HTTP %{http_code}\n' 'https://dev-web.silvergem.org/api/supply-chain/public/trace/%27%20OR%201%3D1--'
```

---

## Unverified gaps

1. Positive public trace live/browser path with `public_trace_enabled=true` fixture.
2. Live role E2E using real business/provider/admin credentials.
3. Full audit matrix.
4. Performance/load baseline.
5. Resilience/chaos tests.
6. Accessibility/localization browser matrix.
7. Direct migration downgrade/upgrade against disposable DB clone.
8. Worker job dry-run/integration for certificate expiry/risk alerting.

---

## Recommended next actions

### P0/P1 before production sign-off

1. Fix stale supplier eligibility test fixture and rerun unmodified backend P0 gate.
2. Seed deterministic valid public trace fixture and add positive runtime/browser smoke.
3. Add/execute real role live smoke for business/provider/admin traceability flows.
4. Investigate ARQ `daily_cert_expiry_alerts` DB-unavailable error.

### P2 before scale

1. Add k6/locust public trace load baseline.
2. Add snapshot golden-file tests for a representative sealed trace.
3. Add worker observability checks for certificate risk-alert pipeline.
4. Filter expected negative-test DB errors from release log scans, or run log scan after tests with a clean window.

---

## Final recommendation

Current state is **controlled sandbox demo capable for negative/fail-closed trace behavior and source-level traceability invariants**, but **not yet production GO** because the live positive public trace path and live role/browser matrix remain unproven.
