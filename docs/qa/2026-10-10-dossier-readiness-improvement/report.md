# AMINRA Dossier Readiness Improvement — 2026-10-10

## Verdict

**PASS for the tested source slice and local sandbox deployment. PARTIAL for the complete certification-readiness journey; not a public-production/customer-pilot GO.**

Scope completed: fail-closed dossier readiness, role/canonical-tenant enforcement, API response contract, frontend runtime payload validation, and business-facing command-panel UX. Changes were committed and pushed in `a47d2f7`, `07eaaa6`, and `93b9b97`; backend and frontend deployed to the local sandbox only. Public endpoints remain blocked/403; no public production release or customer-pilot GO is claimed.

## Changes in this improvement lane

- `backend/services/dossier_readiness.py`
  - Empty required-document checklist fails closed (`requirements_unconfigured`, 0% readiness, issuance blocked).
  - Computes lifecycle state and next action/role, reports the earliest deadline among blocking NCR/CAPA items, and separates all active NCRs from decision-blocking NCRs.
  - Only explicitly `minor` NCRs are non-blocking; unknown/missing severity remains fail-closed.
  - An approved decision without an active certificate is `certificate_pending`, never `certified`; public trace remains unavailable.
- `backend/auth/dossier_router.py`
  - Readiness route is restricted to the business role and uses the canonical resolved tenant, not a caller-supplied tenant claim.
- `frontend/aminra-web/app/dossiers/[id]/page.tsx`
  - Shows human-readable state, action, owner role, due date, and blockers; minor NCRs are informational, not shown as decision blockers.
  - Fails visibly when dossier readiness cannot be loaded; does not assume readiness exists.
- Added/updated backend route/service/auth tests and frontend command-panel tests, including fail-closed checklist, major/minor NCR, certificate-pending, tenant-claim mismatch, unauthorized-role, loading/error contract, and due-date presentation cases.

## Parent-review findings and corrections (TDD)

Independent review found two false-ready paths; follow-up review also drove tenant-bound decision scoping and response-shape hardening:

1. Certificate lookup ordered by nonexistent `issued_at` (schema has `issue_date`) and counted any `active` row, including future-issued/expired certificates. Added a fail-first SQL-contract test, observed RED, then changed lookup to require `issue_date <= CURRENT_DATE`, `expiry_date >= CURRENT_DATE`, and order by `issue_date DESC`.
2. A legacy `documents.status='approved'` could override the current version-control `approval_status='draft'`. Added a fail-first regression (RED), then made current approval state authoritative when present; legacy status remains the fallback only when approval state is absent.
3. Decision lookup was scoped to the latest dossier-linked submission, canonical business tenant, and provider; submission selection now has a deterministic `id` tie-breaker. Earlier submission decisions cannot satisfy the current submission.
4. Added a Pydantic API response contract (readiness 0–100; validated nested items) plus frontend runtime shape validation. Regressions reject out-of-range readiness and malformed nested arrays instead of allowing false-ready/crash behavior.

## Verification evidence

- Backend dossier readiness + route/auth tests: **21 passed**.
- Frontend command-panel tests: **4 passed**.
- Frontend root/auth contract tests: **33 passed**.
- ESLint on touched frontend files: **PASS**, zero warnings; ESLint 9 / `eslint-config-next` 16.4.0.
- Frontend TypeScript: **PASS** (`tsc --noEmit`).
- Frontend production build: **PASS** using Next.js **16.4.0**; static generation completed.
- Tenant route inventory: **274 routes, all 274 classified covered** by the existing inventory gate; coverage gate **4 passed**.
- Tenant-boundary heuristic scan: **189 findings — 0 HIGH, 181 MEDIUM, 8 INFO**. MEDIUM/INFO findings remain review backlog; scan is heuristic, not proof of absence of vulnerabilities.
- Python compile for touched backend files with isolated `/tmp` pycache: **PASS**.
- `git diff --check`: **PASS**.

## Local sandbox deployment (2026-10-10)

- Backend and frontend were built from clean release snapshots and deployed service-by-service with `--no-deps`; protected services' start times were asserted unchanged.
- Backend image health: **healthy**; post-deploy readiness/auth suite: **21 passed**; `/health`: **200**.
- Frontend image health: **healthy**; runtime Next.js version: **16.4.0**. Local smoke: `/` → `307 /landing`, `/landing` **200**, `/dossiers/{id}` **200**. This is HTTP route smoke, not authenticated browser UAT.
- Compose health at final verification: backend, frontend, Keycloak, Postgres, Qdrant, Redis healthy; ARQ worker running.
- Dependency audit on the final lockfile: **0 vulnerabilities** in both full tree and production-only tree. The earlier frontend build was stopped before container replacement after the old lockfile exposed a critical Next advisory; the patched lockfile was tested and deployed instead.
- Implementation commits pushed on `feat/cb-trust-core-rbac-decisions`: `a47d2f7`, `07eaaa6`, `93b9b97`. QA evidence is recorded in this report as a separate docs-only artifact.
- `https://aminra.org/` and `/landing` still return **403**. No public release occurred; the local route smoke does not establish production, customer-pilot, or full-lifecycle readiness.

## Assessment calibration

No numeric readiness score is issued from source/build evidence alone. The tested source slice is **PASS** for the stated gates; the whole certification journey remains **PARTIAL** because live-token/browser UAT across document → review → NCR/CAPA → independent decision → certificate artifact/public trace was not run here. Expiry/near-expiry behavior is now constrained by certificate validity dates in the query, but no live database-backed expiry-boundary test was executed. Named-person assignment is also not established by this slice.

## Residual risks / next gates

1. Run credentialed live-token UAT against an approved sandbox runtime, including business-vs-provider role negatives and cross-tenant IDs; do not infer runtime behavior from source tests.
2. Browser-test the whole workflow with a deterministic seed dossier, and verify that only approved decision/artifact state enables public trace.
3. Confirm the checklist-misconfigured remediation owner (currently represented as the `admin` role) and whether NCR deadlines are the only supported source for readiness `due_date`.
4. Triage the 181 MEDIUM scanner findings separately; do not blanket allowlist them.
5. Main worktree remains at `07eaaa6` with uncommitted changes to `frontend/aminra-web/package.json` and `package-lock.json`; these were not overwritten or staged. Reconcile those edits against the pushed release before the next local pull/commit.
