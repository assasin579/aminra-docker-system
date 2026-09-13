# AMINRA — Manager-Friendly Happy Path & Edge Path Test Cases

Generated: 2026-09-13T04:08:36-04:00

## Executive verdict

- **Happy paths:** sufficiently covered for a controlled sandbox/demo decision.
- **Edge path / public CDN performance:** tested, but **not yet sufficient for production-load readiness** because public Cloudflare path misses p95 SLO and remains `cf-cache-status: DYNAMIC`.
- **Production GO:** not recommended until public edge/CDN SLO, production SMTP, dependency remediation, and approved chaos/recovery evidence are complete.

## How to read the status

- **PASS:** Test succeeded with evidence.
- **FAIL:** Test ran and did not meet acceptance criteria.
- **DEFERRED:** Intentionally not executed yet; not a pass.
- **WARN:** Risk remains but does not necessarily block sandbox demo.
- **BLOCKED:** Cannot complete without environment/config/credential action.

---

## A. Happy path test cases

### HP-01 — User can authenticate through Keycloak and maintain a valid session

- **Situation:** A valid user opens the application and logs in using the configured identity provider.
- **Actor:** Business user / provider / admin, depending on assigned role.
- **Expected business result:** The user enters the app with the correct identity and role; session remains valid after reload.
- **What was tested:** Keycloak token issuance, backend identity recognition, multi-user login, token isolation, and logout behavior.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/006-01-auth-session-rbac-keycloak-token-admin-jwks-dual-auth.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/009-01-auth-session-rbac-playwright-keycloak-token-login-multiuser.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/010-01-auth-session-rbac-playwright-token-isolation-and-logout.txt`

### HP-02 — User role boundaries work during normal usage

- **Situation:** Users with different roles access their expected areas.
- **Actor:** Admin, provider, business/customer, auditor/sub-role.
- **Expected business result:** Each user sees and performs only actions allowed for their role.
- **What was tested:** Live role boundaries and admin reset flows.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/007-01-auth-session-rbac-role-boundaries-live-and-admin-reset.txt`

### HP-03 — Supply-chain record can progress through the core traceability flow

- **Situation:** A supply-chain/batch traceability record is created or seeded, with eligibility/sealing logic applied.
- **Actor:** Business/provider workflow.
- **Expected business result:** The system can produce a valid public traceable object for QR/public verification.
- **What was tested:** Core supply-chain sealing, supplier eligibility, deterministic public trace fixture setup.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/014-03-supply-chain-trace-supply-chain-core-sealing-eligibility.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/015-03-supply-chain-trace-seed-deterministic-public-trace-fixture.txt`

### HP-04 — Public user can open a valid trace / QR link

- **Situation:** A buyer or external party scans a valid QR/public trace URL.
- **Actor:** Anonymous public visitor.
- **Expected business result:** Public visitor sees the correct trace information without logging in.
- **What was tested:** Valid public trace smoke and Playwright supply-chain demo spine.
- **Result:** PASS for functionality.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/016-03-supply-chain-trace-public-trace-valid-invalid-smoke.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/017-03-supply-chain-trace-playwright-supply-chain-and-demo-spine.txt`

### HP-05 — Provider issues a Halal certificate from an approved submission

- **Situation:** A provider/certification actor issues a certificate after the required application/submission lifecycle.
- **Actor:** Provider/certification body role.
- **Expected business result:** Certificate is created with valid database references and certificate number/state.
- **What was tested:** Submission/certificate lifecycle, certificate issuance FK integrity, certificate number generation/concurrency.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/018-04-submission-cert-lifecycle-submission-revisions-sla-and-cert-lifecycle.txt`
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`

### HP-06 — Business user downloads its issued certificate PDF

- **Situation:** A business/customer downloads a certificate PDF that belongs to them.
- **Actor:** Business/customer user.
- **Expected business result:** User receives the correct protected PDF artifact.
- **What was tested:** PDF authorization, Keycloak claim enrichment, PDF rendering/integrity.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/023-06-pdf-doc-versioning-pdf-renderer-document-versioning.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/025-06-pdf-doc-versioning-pdf-visual-baselines.txt`

### HP-07 — Public user verifies the issued certificate

- **Situation:** A public party verifies a certificate from a public verification route.
- **Actor:** Anonymous public visitor.
- **Expected business result:** Public verification confirms certificate validity without exposing private data.
- **What was tested:** Public verify blockchain/certificate checks and live issue UAT.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`

### HP-08 — Admin manages users/members/auditors through CRUD flows

- **Situation:** Admin manages platform accounts or related user records.
- **Actor:** Admin.
- **Expected business result:** Admin can create/read/update/manage expected user/member/auditor records safely.
- **What was tested:** Admin user/member/auditor CRUD and Playwright admin flows.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/021-05-admin-user-crud-admin-user-member-auditor-crud.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/022-05-admin-user-crud-playwright-admin-user-flows.txt`

### HP-09 — Document/template UI and versioning work for normal document operations

- **Situation:** User interacts with document/template functions used to produce official artifacts.
- **Actor:** Admin/provider/business workflow depending on document type.
- **Expected business result:** Document templates and versions remain usable and visible through UI flows.
- **What was tested:** Template repair guard, document versioning, PDF baseline checks, Playwright template/document UI.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/024-06-pdf-doc-versioning-template-files-repair-guard.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/026-06-pdf-doc-versioning-playwright-template-document-ui.txt`

### HP-10 — Full desktop browser functional matrix remains green

- **Situation:** Representative frontend flows are run through browser automation.
- **Actor:** Multiple app roles / anonymous public user depending on test.
- **Expected business result:** No failing desktop Chromium Playwright tests in the customer-ready matrix.
- **What was tested:** Full Playwright desktop Chromium matrix after fixture/env skip triage.
- **Result:** PASS: `301 passed`, `25 skipped`, `0 failed`.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/033b-08-frontend-browser-a11y-playwright-skipped-tests-triage-after-fixes.txt`

---

## B. Edge path / negative / resilience test cases

### EP-01 — Invalid public trace ID fails closed

- **Situation:** A public visitor opens an invalid/random trace URL.
- **Actor:** Anonymous public visitor.
- **Expected business result:** System rejects the request without leaking private data.
- **What was tested:** Public trace valid/invalid smoke.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/016-03-supply-chain-trace-public-trace-valid-invalid-smoke.txt`

### EP-02 — Unauthorized users cannot cross tenant/resource boundaries

- **Situation:** A user attempts to access another tenant's protected records or protected routes without proper authority.
- **Actor:** Lower-privileged user / anonymous user.
- **Expected business result:** Cross-tenant/unauthorized access is denied.
- **What was tested:** Tenant/IDOR live-token UAT, anonymous/resource boundaries, route coverage gate.
- **Result:** PASS with residual warnings.
- **Evidence:**
  - `docs/qa/2026-09-13-tenant-idor-confidence-8of10/report.md`
  - Summary evidence: live-token UAT `50 passed`, P0 anonymous/resource boundaries `32 passed`, coverage gate `3 passed`, `0 deferred P0`.

### EP-03 — Revoked certificate cannot be reactivated by simple status flip

- **Situation:** A revoked certificate is accidentally or maliciously changed back to active.
- **Actor:** Provider/admin attempting status mutation.
- **Expected business result:** Revocation is terminal; replacement certificate must be issued instead of reactivating the old one.
- **What was tested:** Revoked status transition guard returns conflict and preserves revoked state.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`

### EP-04 — Certificate issuance does not break database integrity under required references

- **Situation:** Certificate issuance must write all required references such as `submission_id` and canonical local provider id.
- **Actor:** Provider/certification body role.
- **Expected business result:** Certificate record is valid and does not fail FK/NOT NULL constraints.
- **What was tested:** Issuance writes `submission_id`; `issued_by` uses canonical local provider id.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`

### EP-05 — Certificate numbers remain safe under concurrency

- **Situation:** Multiple certificates are issued close together.
- **Actor:** Provider/certification body role.
- **Expected business result:** Certificate numbers remain unique/consistent.
- **What was tested:** Certificate number concurrency test.
- **Result:** PASS.
- **Evidence:**
  - `docs/qa/2026-09-13-cert-uat-hardening/evidence/001-cert-hardening-test-evidence.md`

### EP-06 — Public trace path meets local backend performance SLO

- **Situation:** Trace endpoint receives repeated requests directly at backend.
- **Actor:** Public trace consumer simulated by load test.
- **Expected business result:** Backend handles the request volume under p95 `<800ms`.
- **What was tested:** `120` requests, concurrency `30`, local backend path.
- **Result:** PASS: p95 `594.3ms` in latest rerun.
- **Evidence:**
  - `docs/qa/2026-09-13-edge-cdn-fix/evidence/008-public-trace-slo-after-cert-hardening-edge-still-blocked.txt`

### EP-07 — Public trace path meets local frontend proxy/cache performance SLO

- **Situation:** Trace endpoint is requested through local frontend proxy.
- **Actor:** Public trace consumer simulated by load test.
- **Expected business result:** App proxy cache serves requests under p95 `<800ms`.
- **What was tested:** `120` requests, concurrency `30`, local frontend proxy path, cache headers.
- **Result:** PASS: p95 `406.0ms`; `x-aminra-proxy-cache: hit`.
- **Evidence:**
  - `docs/qa/2026-09-13-edge-cdn-fix/evidence/008-public-trace-slo-after-cert-hardening-edge-still-blocked.txt`

### EP-08 — Public Cloudflare/edge trace path meets production-like SLO

- **Situation:** External public users hit the public trace URL through Cloudflare/edge/tunnel.
- **Actor:** Public trace consumer simulated by load test.
- **Expected business result:** Public route returns `200`, uses edge cache as intended, and meets p95 `<800ms`.
- **What was tested:** `120` requests, concurrency `30`, public URL `https://dev-web.silvergem.org/api/api/supply-chain/batches/trace/...`.
- **Result:** FAIL/BLOCKED: HTTP `200` succeeds but p95 `978.7ms`; `cf-cache-status: DYNAMIC`.
- **Manager interpretation:** Functionally usable, but not production-load-ready for QR/public trace until Cloudflare cache rule or equivalent edge config is applied.
- **Evidence:**
  - `docs/qa/2026-09-13-edge-cdn-fix/evidence/008-public-trace-slo-after-cert-hardening-edge-still-blocked.txt`
  - `docs/qa/2026-09-13-edge-cdn-fix/report.md`

### EP-09 — SMTP email verification and password reset via production-grade email path

- **Situation:** User receives verification/password-reset emails from a production SMTP provider.
- **Actor:** New customer/user.
- **Expected business result:** Email verification and password reset work through TLS/authenticated provider and are deliverable outside the internal network.
- **What was tested:** Internal QA SMTP relay captured Keycloak verify email action.
- **Result:** PARTIAL: internal QA relay PASS; production SMTP readiness not proven.
- **Manager interpretation:** Good for internal QA, not enough for customer onboarding sign-off.
- **Evidence:**
  - `docs/qa/2026-09-13-smtp-live/report.md`

### EP-10 — Chaos/recovery behavior under infrastructure failure

- **Situation:** Service/database/network failure occurs and system must recover safely.
- **Actor:** Operations / platform reliability scenario.
- **Expected business result:** Backup/recovery and failure behavior are proven before production.
- **What was tested:** Not executed because destructive chaos requires explicit approval and backup/recovery plan.
- **Result:** DEFERRED.
- **Manager interpretation:** This blocks production GO, but not necessarily a controlled sandbox demo.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/036-09-load-chaos-deploy-chaos-drills-deferred.txt`

### EP-11 — Known dependency security issues are reviewed before production

- **Situation:** Production dependencies contain critical/high advisories.
- **Actor:** Security/release management.
- **Expected business result:** Direct production critical/high vulnerabilities are upgraded, mitigated, or formally risk-accepted.
- **What was tested:** Frontend npm and backend pip audit triage.
- **Result:** WARN.
- **Manager interpretation:** Does not block controlled demo by itself, but blocks clean production GO without remediation/risk acceptance.
- **Evidence:**
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/037-10-dependency-audit-frontend-npm-triage.txt`
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/038-10-dependency-audit-backend-pip-triage.txt`

---

## C. Manager decision matrix

### Is there enough happy-path coverage for sandbox/demo?

**Yes — with caution.**

Covered happy paths include:

- Login/session/role flows.
- Supply-chain traceability flow.
- Public trace valid link.
- Submission/certificate lifecycle.
- Provider certificate issue.
- Business PDF download.
- Public certificate verification.
- Admin/user CRUD.
- Document/template/PDF flows.
- Full desktop browser matrix.

### Is there enough edge-path coverage for production sign-off?

**No.**

The major edge-path blocker is not functionality; it is public edge/CDN performance:

- Public trace endpoint returns HTTP `200`.
- But p95 is above target.
- Cloudflare is not caching the API route at edge: `cf-cache-status: DYNAMIC`.

### Recommended decision

- **Controlled sandbox demo:** GO WITH CAUTION.
- **Supervised pilot:** PARTIAL; only if QR/public trace load claims are avoided or edge fix is completed first.
- **Unsupervised customer onboarding:** NO-GO until production SMTP and remaining readiness blockers are closed.
- **Production GO:** NO-GO until edge/CDN SLO, dependency remediation, production SMTP, and chaos/recovery evidence are complete.

---

## D. Missing items before claiming full production readiness

1. Apply Cloudflare cache rule or equivalent edge config for:
   - `GET /api/api/supply-chain/batches/trace/*`
2. Rerun public SLO and require:
   - HTTP 200 success
   - p95 `<800ms`
   - `cf-cache-status: HIT` or equivalent edge-cache proof
3. Complete production SMTP TLS/auth deliverability test.
4. Remediate or risk-accept direct production critical/high dependency advisories.
5. Run approved chaos/recovery drills with backup/recovery evidence.
6. Separately run mobile/tablet browser projects if mobile sign-off is required.
