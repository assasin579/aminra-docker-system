# Tenant / IDOR / Data Isolation Confidence 8/10 Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task if execution is approved.

**Goal:** Raise confidence for AMINRA Tenant / IDOR / Data Isolation from the current partial evidence level to **8/10** with route-inventory coverage, live cross-tenant negative tests, static query-risk checks, and durable release-gate evidence.

**Architecture:** Keep schema-per-tenant as the primary isolation boundary, but prove route-level authorization and resource ownership checks across high-risk HTTP surfaces. Convert the existing static route inventory into executable negative tests and add a CI/release gate that fails when protected routes lack tenant/auth coverage.

**Tech Stack:** FastAPI, PostgreSQL schema-per-tenant, Keycloak/OIDC, pytest, docker compose, Playwright only where browser/session evidence is needed.

---

## Success Criteria — what “8/10 confidence” means

A score of 8/10 is allowed only when all gates below pass in the same evidence pack:

1. **Route coverage gate:** 100% of high-risk route inventory has explicit classification: public-safe, admin-global, tenant-scoped, provider-business-scoped, public sealed snapshot, or deferred with owner/reason.
2. **Executable negative gate:** At least 90% of high-risk non-public routes have automated unauth + wrong-role + cross-tenant/foreign-ID negative coverage.
3. **Live identity gate:** Representative tests use real Keycloak tokens for admin, provider/CB, business, auditor/sub-user, and anonymous — not only monkeypatch/unit tests.
4. **Data-class gate:** Cross-tenant denial is proven for submissions, certificates, PDFs/DOCX, file/media/photo, supply-chain processes/materials/batches/suppliers, users/invites, audit logs, and GDPR/data export.
5. **Static guard gate:** CI has a route/query risk scanner that flags new routes or raw SQL/resource-ID lookups without tenant scope or allowlisted global/admin classification.
6. **Evidence gate:** A markdown report and machine-readable `status.tsv` exist with PASS/WARN/FAIL per route family; no skipped tenant-isolation tests are silently counted as PASS.
7. **Residual risk gate:** Remaining untested routes are explicitly listed and bounded; no P0 route remains untested.

A score of 9–10 is not claimed until property/fuzz tests, broader browser evidence, and RBAC engine migration reduce manual guard risk.

---

## Current baseline / gap

Current evidence exists but is not enough for 8/10:

- Existing QA evidence: `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/012-02-tenant-idor-route-boundary-cross-tenant-and-unauth-boundaries.txt`
- Current result in that pack: `65 passed, 55 skipped`
- Static inventory exists: `docs/qa/route-auth-tenant-inventory.md`
- High-risk problem: many tests are representative, not route-inventory complete; UAT tenant tests are mostly skipped; static inventory still includes `public/unknown` and `tenant note: unknown` entries.

Therefore target is not “write more tests blindly”; target is to close inventory → executable coverage mapping.

---

## Phase 0 — Freeze evidence scope and scoring rubric

### Task 0.1: Create the route-family scorecard

**Objective:** Define the evidence categories that will decide the confidence score.

**Files:**
- Create: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/scorecard.md`
- Create: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/status.tsv`

**Steps:**
1. Create rows for route families:
   - auth/session/profile
   - admin users/templates/placeholders/analytics
   - provider/business audit routes
   - submissions/revisions/cert lifecycle
   - certificate registry/PDF/document export
   - supply-chain process/material/batch/supplier/photo/certificate
   - notification/audit logs/jobs
   - GDPR/data export
   - public sealed trace routes
2. For each family, record: route count, tested count, skipped count, evidence path, residual risk, owner.
3. Gate rule: P0 route family with skipped-only evidence cannot exceed confidence 6/10.

**Verification:**
- `status.tsv` has one row per route family.
- No row has empty `owner`, `risk`, or `evidence`.

---

## Phase 1 — Convert static route inventory into executable coverage map

### Task 1.1: Generate machine-readable route inventory

**Objective:** Convert `docs/qa/route-auth-tenant-inventory.md` into JSON/TSV so tests can assert coverage.

**Files:**
- Create: `scripts/qa/build_route_tenant_inventory.py`
- Create output: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv`

**Implementation requirements:**
- Parse backend route decorators from:
  - `backend/app.py`
  - `backend/auth/*_router.py`
  - `backend/supply_chain/*_router.py`
- Columns:
  - `method`
  - `path`
  - `handler`
  - `source_file`
  - `auth_signal`
  - `tenant_class`
  - `risk_class`
  - `coverage_test`
  - `coverage_status`
- Risk classes:
  - `P0_RESOURCE_IDOR`
  - `P0_FILE_OBJECT`
  - `P0_ADMIN_GLOBAL`
  - `P1_TENANT_LIST`
  - `P1_PUBLIC_SEALED`
  - `P2_HEALTH_OR_STATIC`

**Verification command:**

```bash
python3 scripts/qa/build_route_tenant_inventory.py \
  --repo . \
  --out docs/qa/2026-09-13-tenant-idor-confidence-8of10/route-inventory.tsv
```

**Expected:** route count matches or exceeds the prior static count; unknown auth/tenant fields are surfaced, not hidden.

### Task 1.2: Add inventory coverage assertion

**Objective:** Fail when a P0/P1 route lacks coverage mapping.

**Files:**
- Create: `backend/tests/test_route_tenant_inventory_coverage.py`

**Test behavior:**
- Load `route-inventory.tsv`.
- Fail if any `P0_*` route has `coverage_status != covered` unless explicitly `deferred` with owner and deadline.
- Warn/report but do not fail for P2 route gaps.

**Verification command:**

```bash
docker compose exec -T aminra-backend sh -lc 'cd /app && PYTHONPATH=/app pytest -q tests/test_route_tenant_inventory_coverage.py'
```

---

## Phase 2 — Replace skipped UAT tenant tests with deterministic fixtures

### Task 2.1: Inspect skipped tenant UAT predicates

**Objective:** Identify why `tests/uat/test_uat_c_tenant_isolation.py` skips and remove environment ambiguity.

**Files:**
- Modify: `backend/tests/uat/test_uat_c_tenant_isolation.py`
- Create/update fixtures in: `backend/tests/conftest.py` or `backend/tests/fixtures/tenant_isolation.py`

**Steps:**
1. Read every `pytest.skip`, `skipif`, and missing fixture branch.
2. Classify skip reason: missing DB seed, missing Keycloak token, destructive test safety, obsolete route.
3. Replace missing seed skips with deterministic fixture setup/teardown.
4. Keep destructive tests behind explicit marker, but ensure non-destructive negative cases run.

**Verification command:**

```bash
docker compose exec -T -e DEMO_PW -e PROVIDER_DEMO_PW -e ADMIN_DEMO_PW aminra-backend sh -lc \
  'cd /app && PYTHONPATH=/app pytest -q tests/uat/test_uat_c_tenant_isolation.py -rs'
```

**Target:** reduce tenant UAT skips from ~48+ to <=10, all remaining skips justified.

### Task 2.2: Add deterministic cross-tenant seed builder

**Objective:** Build tenant A/B fixtures with real IDs for resource swapping tests.

**Files:**
- Create: `backend/tests/fixtures/cross_tenant_seed.py`

**Seed entities:**
- tenant A business + user
- tenant B business + user
- provider/CB user
- submission owned by tenant A and tenant B
- certificate or PDF artifact owned by tenant A and tenant B
- supply-chain process/material/batch/supplier/photo owned by tenant A and tenant B
- audit log / notification / GDPR export target where applicable

**Verification:** each fixture returns IDs and cleanup function; no QA data remains after test.

---

## Phase 3 — Add high-risk IDOR negative test families

### Task 3.1: Submission/certification/resource-ID swap tests

**Objective:** Prove users cannot fetch or mutate foreign submissions, dossiers, scores, certificates, or revisions by guessing IDs.

**Files:**
- Create: `backend/tests/security/test_idor_submission_cert_routes.py`

**Required tests:**
- business A cannot GET/PUT/POST actions against business B submission/revision/cert IDs.
- provider not assigned/authorized cannot access another provider’s business dossier.
- auditor/sub-user cannot escalate to owner/provider-only cert mutation.
- admin-global routes are admin-only and do not expose tenant secrets unnecessarily.

**Expected:** 403 or 404 fail-closed; no 500; no object body from foreign tenant.

### Task 3.2: File/object boundary tests

**Objective:** Prove file/object references do not bypass tenant checks.

**Files:**
- Create: `backend/tests/security/test_idor_file_object_routes.py`

**Required objects:**
- certificate PDF
- DOCX export
- template/reference file view if admin-only
- supply-chain step photo
- supplier certificate attachment
- GDPR/data export file if implemented

**Expected:** foreign IDs and path traversal attempts deny with 401/403/404; no private path leakage.

### Task 3.3: Supply-chain cross-tenant route matrix

**Objective:** Extend existing supply-chain tests from representative cases to route-family matrix.

**Files:**
- Modify/create: `backend/tests/security/test_idor_supply_chain_routes.py`

**Required routes:**
- process template list/detail/create/update/delete
- material create/update with foreign supplier/process refs
- batch create/list/detail/update/seal/release using foreign IDs
- supplier eligibility and risk alert access
- photo upload/view/delete

**Expected:** all foreign refs deny; public trace remains sealed-snapshot-only and does not expose tenant-owned mutable tables.

### Task 3.4: Admin/user/invite boundary tests

**Objective:** Prove admin routes are globally admin-only and tenant admin-ish users cannot mutate platform/global resources.

**Files:**
- Create: `backend/tests/security/test_idor_admin_user_routes.py`

**Required tests:**
- non-admin roles cannot list/create/update/delete users.
- provider/business owner cannot approve/reject providers.
- cross-tenant invite/member/auditor delete cannot remove another tenant’s Keycloak or PG user.
- admin reset-password route denies lower roles and invalid target safely.

---

## Phase 4 — Live Keycloak/token lane

### Task 4.1: Build real-token role matrix smoke

**Objective:** Avoid false confidence from monkeypatch-only auth tests.

**Files:**
- Create: `backend/tests/security/test_live_token_tenant_boundaries.py`

**Roles:**
- anonymous
- business owner tenant A
- business owner tenant B
- provider/CB
- auditor/sub-user
- platform_admin

**Required assertions:**
- each role obtains token from Keycloak direct grant or documented fixture.
- `/auth/me` returns expected role + tenant binding.
- each lower role is denied at least one admin, one provider-only, and one foreign resource route.

**Verification command:**

```bash
docker compose exec -T \
  -e DEMO_PW -e PROVIDER_DEMO_PW -e ADMIN_DEMO_PW \
  -e KEYCLOAK_TOKEN_URL -e KEYCLOAK_CLIENT_ID -e KEYCLOAK_REALM \
  aminra-backend sh -lc 'cd /app && PYTHONPATH=/app pytest -q tests/security/test_live_token_tenant_boundaries.py'
```

---

## Phase 5 — Static guardrails against regression

### Task 5.1: Add raw SQL / unscoped resource scanner

**Objective:** Catch common tenant-boundary mistakes before runtime.

**Files:**
- Create: `scripts/qa/scan_tenant_boundary_risks.py`
- Create: `backend/tests/test_tenant_boundary_static_guard.py`

**Scanner flags:**
- route handlers with `{id}` path params and no `get_current_user`/`require_*` dependency.
- SQL selecting by `id = $1` without tenant/schema/resource-owner join near the query.
- file-serving routes without auth or path normalization.
- `public/unknown` auth signal in route inventory.

**Allowlist file:**
- Create: `docs/qa/tenant-boundary-allowlist.yml`
- Every allowlist entry requires reason, owner, expiry/review date.

**Verification:** static guard test fails for deliberately injected unsafe fixture route/query.

### Task 5.2: Add CI/release command

**Objective:** Make the tenant-isolation gate repeatable.

**Files:**
- Modify: `scripts/qa/run_customer_ready_full_system.py` or equivalent QA runner.
- Add lane: `02-tenant-idor-data-isolation-8of10`.

**Command should run:**
- inventory generator
- inventory coverage assertion
- deterministic IDOR test suite
- live token role matrix
- static scanner

**Evidence output:**
- `docs/qa/YYYY-MM-DD-tenant-idor-confidence-8of10/report.md`
- `status.tsv`
- raw pytest logs
- route-inventory.tsv

---

## Phase 6 — Final scoring and report

### Task 6.1: Write confidence report

**Objective:** Produce a senior-QA verdict that explains why confidence is 8/10 or not.

**Files:**
- Create: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/report.md`

**Report sections:**
1. Executive verdict and confidence score.
2. Route inventory summary.
3. Coverage by route family.
4. Live-token role matrix results.
5. Cross-tenant IDOR negative matrix.
6. Static scanner findings.
7. Skips/deferred items and why they do or do not block 8/10.
8. Residual risk and path to 9/10.

**8/10 threshold:**
- PASS if P0 route families have executable evidence and no active FAIL.
- PARTIAL if any P0 family remains skipped/deferred.
- NO-GO if any cross-tenant leak, foreign object fetch, or unauthorized mutation succeeds.

---

## Recommended execution order

1. Phase 1: route inventory → coverage map.
2. Phase 2: remove UAT skips through deterministic fixtures.
3. Phase 3: add IDOR route-family negative tests.
4. Phase 4: run live Keycloak token matrix.
5. Phase 5: add static regression guard.
6. Phase 6: generate report and score.

Do not update the confidence score to 8/10 until Phase 6 evidence exists.

---

## Expected effort

- Minimum useful pass: 0.5–1 day if existing fixtures are reusable.
- Proper 8/10 evidence pack: 1–2 days.
- 9/10+ hardening: additional property/fuzz testing, browser multi-role session isolation, and RBAC-engine migration.
