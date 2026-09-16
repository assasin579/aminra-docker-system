# AMINRA — Functional Completion Scorecard

Generated: 2026-09-13

## Scope and evidence

This scorecard is a source + evidence review, not a fresh full-system rerun. Evidence reviewed:

- Backend inventory: 210 Python files, 228 route decorators, 40 Alembic migrations.
- Test inventory: 74 backend test files, 4 backend UAT files, 34 frontend unit/integration test files, 50 Playwright E2E specs.
- Frontend inventory: 48 app pages, 29 component TSX files.
- QA reports:
  - `docs/qa/2026-09-13-production-readiness/report.md`
  - `docs/qa/2026-09-13-production-readiness/status.tsv`
  - `docs/qa/2026-09-12-customer-ready-full-system/status.tsv`
  - `docs/qa/2026-09-12-customer-ready-full-system/report.md`
- Current working tree status: rebase/detached state, conflict files resolved/staged, QA docs/scripts untracked.

## Scoring rubric

- 90–100: implemented + runtime verified + production gates green.
- 75–89: largely implemented; remaining blockers are narrow and evidenced.
- 60–74: functional but incomplete coverage/ops or customer-readiness gaps.
- 40–59: partial; important workflow/security/runtime gaps.
- <40: prototype/planned only.

## Executive verdict

- Sandbox demo: **75/100 — conditional**
- Supervised pilot: **63/100 — not yet, unless scope is tightly controlled**
- Production/customer onboarding: **51/100 — NO-GO**

Main reason: the product has substantial implementation depth, but production-readiness gates remain red/blocked: public edge/CDN SLO/cache, production SMTP verify/reset, dependency findings, deferred chaos, and one credentialed certificate lifecycle E2E failure.

## Functional group scores

### 1. Auth / Keycloak / session / email verification — 78/100

Evidence:
- Keycloak/OIDC files present: `backend/auth/router.py`, `keycloak_validator.py`, `keycloak_admin.py`, `jwt_utils.py`, `frontend/aminra-web/lib/auth-oidc.ts`.
- Customer-ready status has auth/session/RBAC gates mostly PASS, but SMTP deferred.
- Production readiness SMTP check FAIL: internal `aminra-qa-smtp:2525`, no transport security.

Gaps:
- Verify-email and password-reset through production SMTP are not proven.
- Production onboarding cannot pass until SMTP TLS/auth and live delivery are green.

### 2. RBAC / tenant isolation / IDOR — 82/100

Evidence:
- Dedicated route-boundary and cross-tenant tests exist.
- Customer-ready status shows `cross-tenant-and-unauth-boundaries` PASS and `route-inventory-unknown-risk-scan` PASS.
- Test keyword scan: tenant 62 hits, IDOR 3 direct hits.

Gaps:
- IDOR direct named coverage is still thinner than tenant/RBAC coverage.
- Static route inventory should remain converted into executable negative cases over time.

### 3. Supply-chain traceability / batch sealing / public QR — 76/100

Evidence:
- Supply chain routers/services exist: suppliers, materials, process, batches, eligibility service.
- Public trace migration/page/cache-contract present.
- Local backend/proxy public trace SLO passed in production-readiness evidence.

Gaps:
- Public Cloudflare edge SLO failed: public p95 1650.5ms, `cf-cache-status: DYNAMIC`.
- Cloudflare cache rule blocked by missing `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ZONE_ID`.
- Public buyer/QR path is not production-safe until public edge cache/SLO passes.

### 4. Supplier/NCC eligibility and CB authority — 78/100

Evidence:
- Migrations 038/039 and supplier eligibility service/tests exist.
- Tests cover supplier eligibility service and supply-chain routes.
- Customer-ready supply-chain core sealing/eligibility gate PASS.

Gaps:
- Needs continuous regression that provider authority cannot be spoofed and seal/release-time revalidation remains fail-closed.
- External certifier/provider authority semantics require business UAT, not only automated tests.

### 5. Submission and certification lifecycle — 67/100

Evidence:
- Submission router, SLA service, state-machine/document-lock tests exist.
- Certificate router, lifecycle service, concurrency and scope tests exist.
- Backend-focused lifecycle tests mostly present.

Gaps:
- Customer-ready Playwright cert/state-scoring gate failed: provider Keycloak token grant 401 for `cb-demo@demo.aminra.vn`.
- This blocks high-confidence provider-facing certificate lifecycle sign-off.

### 6. Admin / user CRUD / identity consistency — 80/100

Evidence:
- Admin router, analytics, AdminUserManager, admin CRUD and password reset tests exist.
- Customer-ready admin CRUD and Playwright admin flows PASS in status evidence.

Gaps:
- Must keep Keycloak ↔ Postgres consistency checks in every release; stale credential drift has already appeared in provider E2E.
- Full platform-admin positive path remains credential-sensitive.

### 7. PDF / document rendering / templates / official artifacts — 76/100

Evidence:
- PDF renderer routes/services and certificate PDF/security tests exist.
- Customer-ready status has PDF renderer, template repair, visual baseline, and template UI PASS.

Gaps:
- Official artifact readiness still depends on visual/regression evidence and runtime template volume integrity after deploy.
- Security around template upload/render must stay in release gates.

### 8. Jobs / audit / compliance workers / data rights — 70/100

Evidence:
- Jobs service, jobs tests, audit/data export/delete services exist.
- Customer-ready status shows jobs-audit-data-upload PASS.

Gaps:
- Chaos and outage drills remain deferred.
- Need explicit worker runtime proof after deploy: env/secrets init, DB init, idempotent jobs, log/alert checks.

### 9. Frontend UX / browser / mobile / accessibility — 72/100

Evidence:
- 48 frontend pages, 50 E2E specs, 34 frontend tests.
- Frontend build/lint/vitest/a11y critical gates passed in previous customer-ready evidence.

Gaps:
- Full Playwright/browser matrix was deferred in the report narrative; current status file does not fully cover domains 08/09.
- Mobile/tablet/Safari-like coverage cannot be called production-complete without explicit matrix evidence.

### 10. Observability / deployment / recovery / operations — 58/100

Evidence:
- Observability setup in backend app, monitoring folder, QA runner, backup smoke, restore dry-run PASS.
- DB dump and `pg_restore --list` dry-run passed.

Gaps:
- Destructive chaos drills deferred.
- Deployment mode/zero-downtime proof not sufficient for production claim.
- Dependency audit has critical/high findings.
- Current repo boundary is not a clean committed release candidate.

### 11. Dependency / security hygiene — 55/100

Evidence:
- Dependency audit triage exists.

Gaps:
- Frontend npm audit: 1 critical, 8 high; direct `next` critical and `axios` high.
- Backend `ecdsa` vulnerabilities remain.
- Needs remediation or formal risk acceptance before production GO.

### 12. QA/release management — 68/100

Evidence:
- 127-case production-readiness matrix exists.
- Production-readiness status: PASS 4, BLOCKED 2, FAIL 2, WARN 1, DEFERRED 1.
- Release-boundary conflicts resolved and focused TS/ESLint checks passed.

Gaps:
- Matrix is expanded but not fully executed: 66 REQUIRED, 3 BLOCKED/P0, 1 FAIL/P0, 1 DEFERRED/P0, 1 WARN/P0, 1 WARN/P1.
- Current state still includes untracked QA artifacts and detached/rebase state; no final RC commit.

## Top P0/P1 closure order

1. Apply Cloudflare cache rule for public trace API and rerun split SLO until public p95 <800ms and edge cache proof exists.
2. Configure production SMTP TLS/auth and prove verify-email + password-reset live delivery.
3. Fix provider demo credential drift / Keycloak token grant 401 and rerun cert lifecycle Playwright gate.
4. Remediate direct critical/high dependency findings or obtain formal risk acceptance.
5. Execute approved chaos/recovery drill with backup, recovery probes, and post-chaos regression.
6. Convert current detached/rebase state into a clean release candidate boundary; no untracked/unstaged QA artifacts left ambiguous.
7. Rerun the 127-case production-readiness matrix and publish updated `status.tsv` + report.
