# Defects — AMINRA Supply-Chain Traceability Production QA

Date: 2026-09-11  
Scope: supply-chain traceability production QA execution

---

## DEF-001 — Stale supplier eligibility unit-test fixture applies migration 038 only, while production service now selects 039 authority columns

Severity: P2 Medium / QA harness drift  
Category: Test reliability / regression harness  
Status: Fixed / verified 2026-09-11

Role/Area: backend test harness, supplier eligibility service tests

Evidence:

- `evidence/terminal/11-backend-p0-focused-tests-retry.txt`
- `evidence/terminal/12-backend-p0-focused-tests-excluding-stale-fixture.txt`
- `evidence/terminal/31b-production-batches-schema.txt` is unrelated but environment evidence; direct DB schema check for `supplier_eligibilities` during triage showed `provider_id` exists in persistent DB.
- Fix/retest evidence: `evidence/terminal/41-focused-regression-after-next-actions.txt` — unmodified backend P0 gate now passes **163 passed, 1 skipped**.

Repro:

```bash
docker compose exec -T aminra-backend pytest /app/tests/test_supplier_eligibility_service.py::test_list_eligible_suppliers_filters_fail_closed -q
```

Expected:

- Test fixture schema should match current production service expectations after migrations 039/040.
- `list_eligible_suppliers()` should be testable with current columns: `provider_id`, `source_certificate_id`.

Actual:

- The test autouse fixture imports and applies `038_cb_supplier_certificate_eligibility.py` only, recreating `supplier_eligibilities` without `provider_id`.
- Current service query selects `e.provider_id`, producing:

```text
asyncpg.exceptions.UndefinedColumnError: column e.provider_id does not exist
```

Risk:

- False red in P0 regression gate can mask real regressions or train engineers to ignore red tests.
- The product schema appears healthy at migration head, but the harness is stale.

Recommended fix:

- Update `backend/tests/test_supplier_eligibility_service.py` fixture to apply 038 + 039 authority migration, or stop recreating legacy schema manually and rely on migration-head test DB.
- Keep this test enabled after fixture migration; do not permanently deselect it.

Retest:

- Run focused test without `-k` deselect.
- Then run full supply-chain regression.

---

## DEF-002 — No persistent valid public-enabled sealed trace fixture available for runtime/browser 200-path smoke

Severity: P1 High / Release evidence gap  
Category: Runtime coverage gap  
Status: Fixed / verified 2026-09-11

Role/Area: public trace runtime smoke

Evidence:

- `evidence/terminal/31-public-trace-fixture-candidates.txt`
- `evidence/terminal/30-runtime-smoke.txt`
- `evidence/screenshots/public-invalid-trace-not-found.png`
- Seed evidence: `evidence/terminal/33-seed-public-trace-fixture.txt`
- Positive API/page smoke: `evidence/terminal/34-positive-public-trace-smoke.txt`
- Browser screenshot: `evidence/screenshots/public-valid-trace-qa-fixture.png`
- Post-backend-recreate evidence: `evidence/terminal/46-backend-recreate-after-build.txt`, `evidence/terminal/47-reseed-public-trace-fixture-after-backend-recreate.txt`, `evidence/terminal/50-public-trace-correct-endpoint-resmoke-after-recreate.txt`, `evidence/terminal/52-public-next-actual-proxy-resmoke.txt`, `evidence/screenshots/public-valid-trace-after-backend-recreate.png`

Repro:

```bash
docker compose exec -T postgres-db psql -U aminra_user -d aminra -Atc \
  "SELECT public_trace_id, status, public_trace_enabled, approved_at IS NOT NULL, sealed_data IS NOT NULL FROM production_batches WHERE public_trace_id IS NOT NULL ORDER BY created_at DESC LIMIT 5;"
```

Expected:

- Sandbox should have one deterministic QA/public trace fixture that is sealed, has sealed snapshot, and `public_trace_enabled=true` for smoke testing the positive public path.

Actual:

- Existing candidates had `public_trace_enabled=false`; no positive public runtime fixture was available.
- Negative public trace fail-closed path passed, but valid `200` public trace browser/API smoke is `BLOCKED`.

Risk:

- Cannot prove deployed/public sandbox renders the positive trace page from a real persistent fixture without creating new test data or obtaining credentials.

Recommended fix:

- Add a deterministic QA fixture seed command or pre-seeded sandbox batch:
  - `QA-TRACE-PUBLISHED-SEALED-001`
  - sealed_data present
  - public_trace_enabled true
  - non-sensitive synthetic supplier/material/certificate data
- Add a smoke script that asserts `GET /trace/<public_trace_id>` renders the expected marker and no private/internal fields.

Retest:

- Runtime curl + browser screenshot for valid trace page.
- Verify invalid trace still returns safe not-found.

---

## DEF-003 — ARQ worker logged `daily_cert_expiry_alerts` database unavailable during QA window

Severity: P2 Medium / Observability-runtime follow-up  
Category: Background worker reliability  
Status: Fixed / verified 2026-09-11

Evidence:

- `evidence/terminal/32-high-signal-log-scan.txt`
- Root-cause/recreate evidence: `evidence/terminal/36-arq-worker-after-recreate.txt`, `evidence/terminal/38-arq-worker-after-second-recreate.txt`
- Dry-run verification: `evidence/terminal/39-arq-daily-cert-dry-run-after-param-fix.txt` — `daily_cert_expiry_alerts` completed with `{'sent': 1, 'failed': 0, 'checked': 1}`.

Observed:

```text
arq-worker-1 | cron:daily_cert_expiry_alerts failed, RuntimeError: Database not available
```

Expected:

- Background jobs should either connect to DB reliably or log controlled transient retry/degrade with alerting context.

Actual:

- Backend health showed DB connected, but ARQ job logged `Database not available`.

Risk:

- Certificate expiry/risk alert automation may silently miss daily detection windows.
- This does not directly break public trace read path, but it affects compliance-risk alerting.

Recommended fix:

- Verify ARQ worker database env sourcing and retry behavior.
- Add a worker health/smoke for `daily_cert_expiry_alerts` using QA-safe dry-run mode.

Retest:

- Run worker job dry-run or focused unit/integration test.
- Re-scan logs after worker job execution.

---

## DEF-004 — Execution file's raw `docker compose exec aminra-backend alembic current` command misses Vault env sourcing

Severity: P3 Low / QA procedure bug  
Category: Execution command accuracy  
Status: Open

Evidence:

- `evidence/terminal/00-environment-baseline.txt`
- `evidence/terminal/01-alembic-current-wrapper.txt`

Expected:

- The documented Alembic current command should work from a running backend container.

Actual:

- Raw command failed with SQLAlchemy URL dialect error because env was not sourced.
- Project wrapper succeeded:

```bash
./scripts/db-migrate.sh current
# 040_public_trace_id (head)
```

Recommended fix:

- Update execution file to prefer:

```bash
./scripts/db-migrate.sh current
```

or source Vault env explicitly inside the container.

---

## Notes on expected negative-test DB errors

The high-signal log scan contains multiple Postgres `ERROR` lines from intentional negative tests: overlong values, duplicate unique key, invalid enums, FK violations. These are expected side effects of validation tests and are not product defects by themselves. They should be filtered or isolated in future QA log scans so real runtime defects stand out.
