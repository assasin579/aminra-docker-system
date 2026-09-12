# AMINRA Production Risk Closure Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Close the remaining AMINRA production-readiness risks after supply-chain public trace P0 hardening, without over-claiming production GO before evidence exists.

**Architecture:** Treat production readiness as a gate pipeline: commit hygiene → credentialed multi-role E2E → full security/audit matrix → operational resilience → performance/load → browser/accessibility → release decision. Each risk is closed only by executable evidence saved under `docs/qa/` and reflected in the project brain.

**Tech Stack:** Docker Compose, FastAPI/Python/pytest, Next.js/Vitest/Playwright, Keycloak, PostgreSQL, ARQ/Redis, curl/browser smoke, project vault under `/home/user/Documents/all-docs/`.

---

## Success criteria

A risk can be marked closed only when all of these are true:

1. The relevant automated/manual gate has a reproducible command or checklist.
2. Evidence is written under a dated QA folder.
3. Failure modes are tested, not only happy paths.
4. Logs are scanned after runtime tests.
5. QA report, defects, session brain, and MASTER_INDEX are reconciled.
6. No commit/push/deploy happens without founder authorization.

Final production GO requires:

- Real multi-role browser E2E: PASS.
- Full supply-chain/security audit matrix: PASS or explicitly accepted residual risks.
- Load/performance soak: PASS against stated thresholds.
- Chaos/resilience tests: PASS with bounded degradation and recovery.
- Accessibility/browser matrix: PASS for critical public/admin/business/provider/auditor routes.
- Keycloak SMTP/email verification production config: PASS before any real customer onboarding.

---

## Risk inventory and priority

### P0 — must close before any customer/pilot GO

1. **R-P0-1: Uncommitted follow-up changes may be deployed/reviewed ambiguously**
   - Risk: code, QA fixture, worker infra, and vault docs are modified but not committed; reviewers cannot reason about exact release artifact.
   - Close by: review diff, split commits, no push unless authorized.

2. **R-P0-2: Real multi-role browser E2E not executed**
   - Risk: source/API tests pass but role-specific flows fail in hydrated browser with Keycloak, SW cache, proxy, or app-state issues.
   - Close by: credentialed Playwright/browser matrix for admin, CB/provider, business, auditor.

3. **R-P0-3: Full audit/security matrix not executed**
   - Risk: traceability path is hardened but broader auth/RBAC/tenant/file/data-export surfaces still have uncovered regressions.
   - Close by: run/update full 365-case matrix or scoped matrix with explicit residual-risk signoff.

4. **R-P0-4: Email verification/SMTP remains production blocker**
   - Risk: real customer onboarding either bypasses email verification or verify-email fails live.
   - Close by: configure verified sender SMTP/Resend, send live verification email, re-enable `verifyEmail=true`, test self-registration.

### P1 — must close before unsupervised pilot, can run after P0 commit hygiene

5. **R-P1-1: Load/performance soak missing**
   - Risk: public trace, dashboard, Keycloak, DB pool, ARQ jobs degrade under realistic pilot traffic.
   - Close by: load profile + thresholds + soak evidence.

6. **R-P1-2: Chaos/resilience tests missing**
   - Risk: DB/Redis/Keycloak/Qdrant outages produce unsafe behavior, partial writes, or confusing false success.
   - Close by: non-destructive dependency-failure drills in sandbox.

7. **R-P1-3: Accessibility/browser matrix missing**
   - Risk: demo-critical flows work only in one browser/device and public trace is not usable by customers/auditors.
   - Close by: Chromium/Firefox/WebKit + mobile viewport + keyboard/screen-reader checks for critical routes.

8. **R-P1-4: Direct live sandbox migration downgrade/upgrade not executed**
   - Risk: migration rollback path is only proven in transactional harness, not in live-like backup/restore workflow.
   - Close by: run on disposable DB clone or explicit founder-approved sandbox backup/restore drill.

---

## Phase 0 — Freeze scope and review the current diff

### Task 0.1: Capture exact working tree

**Objective:** Produce a reviewable inventory of uncommitted changes.

**Files:**
- Read only: repo git state.
- Evidence: `docs/qa/2026-09-11-production-risk-closure/evidence/terminal/00-working-tree.txt`

**Steps:**

```bash
mkdir -p docs/qa/2026-09-11-production-risk-closure/evidence/terminal
git status --short | tee docs/qa/2026-09-11-production-risk-closure/evidence/terminal/00-working-tree.txt
git diff --stat | tee -a docs/qa/2026-09-11-production-risk-closure/evidence/terminal/00-working-tree.txt
```

**Expected:** Shows only known follow-up code/tests/docs/QA fixture changes.

### Task 0.2: Review security-sensitive diffs

**Objective:** Ensure ARQ/DB/public trace fixes do not broaden access or leak secrets.

**Files:**
- Review: `docker-compose.yml`
- Review: `backend/services/jobs.py`
- Review: `backend/services/cert_lifecycle.py`
- Review: `scripts/qa/seed-public-trace-fixture.py`

**Steps:**

```bash
git diff -- docker-compose.yml backend/services/jobs.py backend/services/cert_lifecycle.py scripts/qa/seed-public-trace-fixture.py > docs/qa/2026-09-11-production-risk-closure/evidence/terminal/01-security-sensitive-diff.patch
```

Manual review checklist:

- No secrets printed or committed.
- `vault-secrets` is mounted read-only.
- ARQ startup/shutdown lifecycle initializes and closes DB safely.
- Seed script uses synthetic data and deterministic fixture only.
- Cert alert SQL parameter binding cannot mix text/int placeholders.

**Expected:** No blocking issue. If issue found, stop and fix before commit.

### Task 0.3: Split commits locally after founder approval

**Objective:** Make release artifact reviewable.

**Files:**
- Code commit: runtime/test/seed changes.
- Docs commit: QA report/brain docs.

**Steps:**

```bash
git diff --check
# After founder approval only:
git add docker-compose.yml backend/services/jobs.py backend/services/cert_lifecycle.py backend/tests/test_jobs_unit.py backend/tests/test_cert_lifecycle_unit.py backend/tests/test_supplier_eligibility_service.py scripts/qa/seed-public-trace-fixture.py
git commit -m "fix: harden supply-chain trace QA and worker runtime"

git add docs/qa/2026-09-11-supply-chain-traceability-production-qa-execution.md docs/qa/2026-09-11-supply-chain-traceability-production docs/plans/2026-09-11-aminra-production-risk-closure-plan.md
git commit -m "docs: record supply-chain trace production QA evidence"
```

**Expected:** Local commits only. No push/release tag.

---

## Phase 1 — Real multi-role browser E2E

### Task 1.1: Define credential source without exposing secrets

**Objective:** Run real role flows using env-provided credentials only.

**Files:**
- Create: `docs/qa/2026-09-11-production-risk-closure/e2e-credential-requirements.md`
- Possibly modify: `.env.qa.local.example` if project has one.

**Required env variables:**

```bash
AMINRA_E2E_ADMIN_EMAIL
AMINRA_E2E_ADMIN_PASSWORD
AMINRA_E2E_CB_EMAIL
AMINRA_E2E_CB_PASSWORD
AMINRA_E2E_BUSINESS_EMAIL
AMINRA_E2E_BUSINESS_PASSWORD
AMINRA_E2E_AUDITOR_EMAIL
AMINRA_E2E_AUDITOR_PASSWORD
```

**Acceptance:** No password appears in git diff, logs, screenshots, or report.

### Task 1.2: Admin browser E2E

**Objective:** Prove admin SSO, admin panel, user management, and sidebar role-boundary work in browser.

**Files:**
- Test: `frontend/aminra-web/tests/e2e/admin-role-smoke.spec.ts`
- Evidence: screenshot + terminal output under dated QA folder.

**Core assertions:**

- `/admin` redirects through Keycloak and returns admin panel.
- `/api/auth/me` returns platform admin identity.
- Admin-only sidebar visible.
- CB/provider/business/auditor menu chrome is hidden.
- Logout reaches Keycloak confirmation where intended and clears app state.

**Run:**

```bash
cd frontend/aminra-web
npm run test:e2e -- tests/e2e/admin-role-smoke.spec.ts
```

**Expected:** PASS. Any stale `/api/admin/login` dependency is a blocker to fix, not bypass.

### Task 1.3: CB/provider browser E2E

**Objective:** Prove provider can manage permitted certification/supplier eligibility flows and cannot cross-provider take over.

**Files:**
- Test: `frontend/aminra-web/tests/e2e/provider-supply-chain-smoke.spec.ts`

**Core assertions:**

- Provider login succeeds.
- Certificate risk/eligibility pages load.
- Provider can view own permitted data.
- Cross-provider or unauthorized supplier eligibility action fails closed.

### Task 1.4: Business browser E2E

**Objective:** Prove business supply-chain flow works end-to-end with current auth/proxy/SW state.

**Files:**
- Test: `frontend/aminra-web/tests/e2e/business-supply-chain-smoke.spec.ts`

**Core assertions:**

- Business login succeeds.
- Eligible supplier dropdown filters by material category.
- Create/update process/material/batch write actions surface non-2xx errors correctly.
- Public trace link is generated only after seal/public enablement.

### Task 1.5: Auditor browser E2E

**Objective:** Prove auditor can access permitted read/review surfaces and cannot mutate forbidden business/provider data.

**Files:**
- Test: `frontend/aminra-web/tests/e2e/auditor-readonly-smoke.spec.ts`

**Core assertions:**

- Auditor login succeeds.
- Permitted pages load.
- Mutating routes are absent or return 403.

### Task 1.6: Multi-role log scan and report update

**Objective:** Prevent silent runtime errors from being ignored.

**Steps:**

```bash
docker compose logs --since 30m aminra-backend aminra-frontend keycloak arq-worker | grep -Ei "error|exception|traceback|failed|forbidden|unauthorized" | tee docs/qa/2026-09-11-production-risk-closure/evidence/terminal/10-multirole-log-scan.txt
```

Classify expected 401/403 from negative tests separately.

---

## Phase 2 — Full audit/security matrix

### Task 2.1: Convert remaining 365-case matrix into executable/checkable batches

**Objective:** Avoid one huge opaque run; split matrix by invariant.

**Files:**
- Create/update: `docs/qa/2026-09-11-production-risk-closure/audit-matrix-status.md`

**Batches:**

1. Auth/session/SW/cache identity isolation.
2. RBAC role-boundary and admin/provider/business/auditor authorization.
3. Tenant isolation and cross-tenant ID guessing.
4. Supply-chain trace/seal/snapshot/public QR.
5. File/media/certificate/photo access boundaries.
6. Data export/reporting/PDF routes.
7. API validation/rate-limit/error-shape gates.
8. Background jobs and compliance alerting.

### Task 2.2: Run automated batches first

**Objective:** Maximize machine-verified coverage before manual UAT.

**Commands:**

```bash
docker compose exec -T aminra-backend pytest /app/tests -q --asyncio-mode=auto
cd frontend/aminra-web && npm run lint && npm run test && npm run build
```

If full backend suite is known long/red, run it anyway and classify every failure as:

- real production regression,
- stale harness,
- obsolete test expectation,
- environment prerequisite missing.

### Task 2.3: Negative API matrix

**Objective:** Confirm fail-closed behavior for dangerous surfaces.

**Implement/update tests around:**

- Public trace invalid UUID, injection-shaped ID, unpublished sealed batch, unsealed batch.
- Cross-tenant supplier/certificate/photo IDs.
- Post-seal mutation routes.
- Keycloak-sub vs AMINRA-id FK write paths.
- Raw `limit`/pagination params with negative/huge values.

**Expected:** 401/403/404/422 only, no 500 with SQL/body leaks.

---

## Phase 3 — Keycloak SMTP/email verification production gate

### Task 3.1: Configure SMTP/Resend with verified sender domain

**Objective:** Remove onboarding bypass before any real customer use.

**Files:**
- Do not commit secrets.
- Evidence: redacted Keycloak SMTP config dump.

**Steps:**

- Configure SMTP host, port, TLS/auth, verified from address.
- Send test email from Keycloak admin console/API.
- Re-enable realm `verifyEmail=true`.

### Task 3.2: Self-registration verify-email E2E

**Objective:** Prove new user cannot complete onboarding before verified email.

**Assertions:**

- Register new test user.
- User has VERIFY_EMAIL required action.
- Email is received via test inbox or provider logs.
- Verification link completes successfully.
- Post-verification login reaches expected app role onboarding state.

**Cleanup:** Delete/disable QA user after test.

---

## Phase 4 — Load/performance soak

### Task 4.1: Define realistic pilot profile

**Objective:** Load test against business reality, not arbitrary numbers.

**Initial thresholds:**

- Public trace p95 < 800ms under 50 concurrent public readers.
- Authenticated dashboard/API p95 < 1200ms under 20 concurrent users.
- Error rate < 0.5% excluding expected negative tests.
- No backend/FE container memory growth > 15% over 30-minute soak.
- DB pool saturation does not produce user-visible 500s.

### Task 4.2: Implement k6/Locust smoke

**Files:**
- Create: `scripts/qa/load/public-trace-smoke.js` or `scripts/qa/load/pilot-soak.py`

**Scenarios:**

- 70% public trace GET valid fixture.
- 10% invalid public trace IDs.
- 10% authenticated business read dashboard/supply-chain pages.
- 5% provider cert/risk reads.
- 5% admin reads.

### Task 4.3: Run 10-minute then 30-minute soak

**Evidence:**

- Load tool output.
- Docker stats snapshot before/during/after.
- Backend/Keycloak/ARQ logs.

---

## Phase 5 — Chaos/resilience drills

### Task 5.1: Redis/ARQ degradation drill

**Objective:** Background queue failure should not break public read path or produce false success.

**Method:** Pause/restart Redis or ARQ in sandbox only.

**Assertions:**

- Public trace still reads if DB available.
- Write actions fail clearly if queue dependency required.
- ARQ recovers and resumes job processing after restart.

### Task 5.2: Qdrant degradation drill

**Objective:** Health/reporting should degrade explicitly if vector/search dependency is unavailable.

**Assertions:**

- `/health` reports qdrant disconnected.
- Core supply-chain public trace remains available if it does not require Qdrant.
- No misleading “all healthy” UI.

### Task 5.3: Keycloak degradation drill

**Objective:** Authenticated flows fail closed; public trace remains available where intended.

**Assertions:**

- New login fails safely.
- Existing token behavior is bounded by expiry/validation rules.
- Admin/business/provider protected routes do not render stale local profiles.
- Public trace route remains readable if designed as public DB-backed route.

### Task 5.4: Post-drill recovery verification

**Objective:** Recovery is proven, not assumed.

**Commands:**

```bash
docker compose ps
docker compose exec -T aminra-backend curl -fsS http://localhost:8000/health
make runtime-smoke
```

---

## Phase 6 — Accessibility/browser matrix

### Task 6.1: Critical route matrix

**Routes:**

- `/`
- `/trace/{public_trace_id}`
- `/admin`
- `/business/dashboard`
- `/supply-chain/batches`
- provider/certificate pages
- auditor pages

**Browsers/devices:**

- Chromium desktop.
- Firefox desktop.
- WebKit/Safari equivalent.
- Mobile viewport 390x844.

### Task 6.2: Accessibility checks

**Assertions:**

- Keyboard-only navigation reaches main actions.
- Visible focus states.
- Public trace page has semantic headings and readable contrast.
- Forms have labels/errors tied to fields.
- No modal/flyout keyboard trap.

**Tools:**

- Playwright + axe if available.
- Manual screenshot for public trace and role dashboards.

---

## Phase 7 — Final release decision pack

### Task 7.1: Build final QA report

**Files:**
- Create: `docs/qa/YYYY-MM-DD-aminra-production-readiness-final/report.md`
- Create: `docs/qa/YYYY-MM-DD-aminra-production-readiness-final/defects/DEFECTS.md`

**Required sections:**

1. Verdict: PASS / PARTIAL / BLOCKED / NO-GO.
2. Scope claimed.
3. Environment and commit SHAs.
4. Evidence index.
5. Remaining residual risks.
6. Rollback plan.
7. Founder decision required.

### Task 7.2: Brain reconciliation

**Files:**
- Modify: `/home/user/Documents/all-docs/02-Projects/aminra/README.md`
- Modify: `/home/user/Documents/all-docs/02-Projects/aminra/sessions/YYYY-MM-DD.md`
- Modify: `/home/user/Documents/all-docs/MASTER_INDEX.md`

**Rule:** Update only durable state. Do not paste raw evidence logs into brain.

### Task 7.3: Release/no-release decision

**Decision options:**

- **GO controlled sandbox demo:** allowed if multi-role E2E + trace/public QA + log scan pass, but production blockers remain documented.
- **GO supervised pilot:** allowed only if SMTP/email, full audit matrix, load, chaos, and accessibility gates pass or founder accepts specific residual risks.
- **NO-GO:** any P0 invariant fails: cross-tenant leak, auth stale identity, public trace leak, unbounded 500/SQL leakage, verify-email impossible, or unrecovered dependency failure.

---

## Recommended execution order

1. Phase 0: Review diff and split local commits after approval.
2. Phase 1: Multi-role browser E2E.
3. Phase 3: Keycloak SMTP/email verification.
4. Phase 2: Full audit matrix.
5. Phase 4: Load/performance soak.
6. Phase 5: Chaos/resilience.
7. Phase 6: Accessibility/browser matrix.
8. Phase 7: Final decision pack.

Do not run destructive chaos or migration rollback on live sandbox until backup/restore path is confirmed and founder approves the blast radius.
