# AMINRA — Production-Readiness Test Case Matrix

Generated: 2026-09-13T09:45:16-04:00

> Manager-readable matrix. This is not a raw automation log; it translates existing and required production gates into business-readable test cases.

## Verdict model

- **PASS/RETEST:** previously evidenced but must be rerun in the final production pack.
- **REQUIRED:** must be executed or linked to evidence before production sign-off.
- **FAIL/P0:** known blocker from current evidence.
- **BLOCKED/P0:** cannot pass until environment/config/credential action is completed.
- **WARN/P1:** production risk requiring remediation or formal risk acceptance.
- **DEFERRED/P0:** not a pass; requires explicit approval/execution or production risk acceptance.

## Summary
- Total manager-level test cases: **127**
- Design target: production confidence, not vanity test count.
- Current known blockers: public Cloudflare trace SLO/cache, production SMTP, dependency risk, chaos/recovery, mobile/tablet critical coverage where required.

## AUTH — Auth / Session / Account

### TC-AUTH-001 — Business user logs in via Keycloak and reaches business portal

- **Type:** HP
- **Actor:** business
- **Precondition:** Valid credentials; user enabled
- **Expected result:** Session established; /auth/me returns business role and correct tenant
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-001.txt` or linked existing evidence

### TC-AUTH-002 — Provider user logs in via Keycloak and reaches provider workspace

- **Type:** HP
- **Actor:** provider
- **Precondition:** Valid provider account
- **Expected result:** Session established; provider workspace visible
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-002.txt` or linked existing evidence

### TC-AUTH-003 — Platform admin logs in and reaches admin console

- **Type:** HP
- **Actor:** platform_admin
- **Precondition:** Valid admin account
- **Expected result:** Admin console visible; admin APIs allowed
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-003.txt` or linked existing evidence

### TC-AUTH-004 — Auditor/sub-role logs in and reaches read-only/assigned workspace

- **Type:** HP
- **Actor:** auditor
- **Precondition:** Valid auditor/sub-role
- **Expected result:** Read surfaces visible; mutation controls hidden/denied
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-004.txt` or linked existing evidence

### TC-AUTH-005 — Session survives browser reload

- **Type:** HP
- **Actor:** authenticated user
- **Precondition:** User already logged in
- **Expected result:** Identity and role remain stable after reload
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-005.txt` or linked existing evidence

### TC-AUTH-006 — Logout clears local session

- **Type:** HP
- **Actor:** authenticated user
- **Precondition:** Active session
- **Expected result:** User redirected/logged out; protected routes no longer accessible
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-006.txt` or linked existing evidence

### TC-AUTH-007 — Account switching does not keep stale company/role

- **Type:** HP
- **Actor:** two users
- **Precondition:** User A logged out before User B login
- **Expected result:** UI and /auth/me show only User B identity
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-007.txt` or linked existing evidence

### TC-AUTH-008 — Wrong password is rejected

- **Type:** NEG
- **Actor:** any user
- **Precondition:** Known email with wrong password
- **Expected result:** Login fails without creating session
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-008.txt` or linked existing evidence

### TC-AUTH-009 — Disabled user cannot log in

- **Type:** NEG
- **Actor:** disabled user
- **Precondition:** Account disabled in IdP
- **Expected result:** Token/session not issued or backend rejects
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-009.txt` or linked existing evidence

### TC-AUTH-010 — Expired token is rejected

- **Type:** NEG
- **Actor:** authenticated user
- **Precondition:** Expired token used
- **Expected result:** Protected APIs return 401/403
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-010.txt` or linked existing evidence

### TC-AUTH-011 — Malformed token is rejected

- **Type:** NEG
- **Actor:** attacker
- **Precondition:** Invalid JWT string
- **Expected result:** Protected APIs return 401 without server error
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-011.txt` or linked existing evidence

### TC-AUTH-012 — Unverified email onboarding behavior is explicit

- **Type:** EDGE
- **Actor:** new customer
- **Precondition:** Email not verified
- **Expected result:** App either blocks or clearly marks pending verification per policy
- **Current status:** REQUIRED
- **Release impact:** Customer onboarding, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-012.txt` or linked existing evidence

### TC-AUTH-013 — Password reset email flow completes through production SMTP

- **Type:** EDGE
- **Actor:** customer
- **Precondition:** Production SMTP configured
- **Expected result:** Reset email delivered; link/action works; logs redacted
- **Current status:** BLOCKED/P0
- **Release impact:** Customer onboarding, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-013.txt` or linked existing evidence

### TC-AUTH-014 — Verify-email flow completes through production SMTP

- **Type:** EDGE
- **Actor:** new customer
- **Precondition:** Production SMTP configured
- **Expected result:** Verification email delivered; account state changes correctly
- **Current status:** BLOCKED/P0
- **Release impact:** Customer onboarding, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-014.txt` or linked existing evidence

### TC-AUTH-015 — Tokens/cookies are not printed in logs/evidence

- **Type:** SEC
- **Actor:** ops/security
- **Precondition:** Auth tests executed
- **Expected result:** No secrets in logs, reports, screenshots
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/auth/TC-AUTH-015.txt` or linked existing evidence

## RBAC — RBAC / Tenant / IDOR

### TC-RBAC-016 — Anonymous visitor cannot access business portal

- **Type:** SEC
- **Actor:** anonymous
- **Precondition:** No session
- **Expected result:** Protected business route denied
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-016.txt` or linked existing evidence

### TC-RBAC-017 — Anonymous visitor cannot access provider workspace

- **Type:** SEC
- **Actor:** anonymous
- **Precondition:** No session
- **Expected result:** Protected provider route denied
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-017.txt` or linked existing evidence

### TC-RBAC-018 — Anonymous visitor cannot access admin console

- **Type:** SEC
- **Actor:** anonymous
- **Precondition:** No session
- **Expected result:** Admin route denied
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-018.txt` or linked existing evidence

### TC-RBAC-019 — Business user cannot access platform admin APIs

- **Type:** SEC
- **Actor:** business
- **Precondition:** Valid business token
- **Expected result:** Admin API denied
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-019.txt` or linked existing evidence

### TC-RBAC-020 — Provider user cannot access platform admin APIs

- **Type:** SEC
- **Actor:** provider
- **Precondition:** Valid provider token
- **Expected result:** Admin API denied unless platform admin
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-020.txt` or linked existing evidence

### TC-RBAC-021 — Auditor cannot mutate provider-owned records

- **Type:** SEC
- **Actor:** auditor
- **Precondition:** Auditor token
- **Expected result:** Write attempt denied
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-021.txt` or linked existing evidence

### TC-RBAC-022 — Business A cannot read Business B records by ID tampering

- **Type:** SEC
- **Actor:** business
- **Precondition:** Two tenants seeded
- **Expected result:** Cross-tenant read denied
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-022.txt` or linked existing evidence

### TC-RBAC-023 — Business A cannot update Business B records

- **Type:** SEC
- **Actor:** business
- **Precondition:** Two tenants seeded
- **Expected result:** Cross-tenant write denied
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-023.txt` or linked existing evidence

### TC-RBAC-024 — Provider A cannot take over Provider B eligibility records

- **Type:** SEC
- **Actor:** provider
- **Precondition:** Two providers seeded
- **Expected result:** Cross-provider mutation denied
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-024.txt` or linked existing evidence

### TC-RBAC-025 — Certificate PDF cannot be downloaded by wrong tenant

- **Type:** SEC
- **Actor:** business
- **Precondition:** Cert belongs to other tenant
- **Expected result:** Download denied
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-025.txt` or linked existing evidence

### TC-RBAC-026 — Documents cannot be listed across tenant boundary

- **Type:** SEC
- **Actor:** business/provider
- **Precondition:** Two tenants seeded
- **Expected result:** Only own-tenant docs returned
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-026.txt` or linked existing evidence

### TC-RBAC-027 — Route inventory has 0 deferred P0 routes

- **Type:** SEC
- **Actor:** QA/security
- **Precondition:** Route inventory generated
- **Expected result:** All P0 protected routes have explicit auth/tenant coverage
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-027.txt` or linked existing evidence

### TC-RBAC-028 — Tenant static scanner has 0 HIGH findings

- **Type:** SEC
- **Actor:** QA/security
- **Precondition:** Scanner run
- **Expected result:** No HIGH tenant boundary findings
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-028.txt` or linked existing evidence

### TC-RBAC-029 — Public responses do not expose tenant-private fields

- **Type:** SEC
- **Actor:** anonymous
- **Precondition:** Public endpoints queried
- **Expected result:** No internal IDs/secrets/private docs in payload
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-029.txt` or linked existing evidence

### TC-RBAC-030 — Audit log records sensitive admin/user actions

- **Type:** SEC
- **Actor:** admin
- **Precondition:** Admin mutation performed
- **Expected result:** Audit event has actor/action/target/time
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-030.txt` or linked existing evidence

### TC-RBAC-031 — Lower-role direct API calls mirror UI restrictions

- **Type:** SEC
- **Actor:** business/provider/auditor
- **Precondition:** Direct curl/API calls
- **Expected result:** Backend denies forbidden actions regardless of UI
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac/TC-RBAC-031.txt` or linked existing evidence

## TRACE — Supply Chain / Public Trace / QR

### TC-TRACE-032 — Eligible supplier can be used in a traceable batch

- **Type:** HP
- **Actor:** business/provider
- **Precondition:** Supplier eligibility active
- **Expected result:** Batch creation/association succeeds
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-032.txt` or linked existing evidence

### TC-TRACE-033 — Ineligible supplier cannot be used in compliance-critical batch

- **Type:** NEG
- **Actor:** business
- **Precondition:** Supplier missing/expired eligibility
- **Expected result:** Batch/material gate fails closed
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-033.txt` or linked existing evidence

### TC-TRACE-034 — Batch can be sealed/snapshotted for public trace

- **Type:** HP
- **Actor:** business/provider
- **Precondition:** Valid batch data
- **Expected result:** Sealed snapshot created and immutable enough for QR
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-034.txt` or linked existing evidence

### TC-TRACE-035 — Valid public QR/trace URL returns trace data

- **Type:** HP
- **Actor:** anonymous
- **Precondition:** Public trace enabled
- **Expected result:** HTTP 200 and expected public markers
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-035.txt` or linked existing evidence

### TC-TRACE-036 — Invalid trace UUID returns not found

- **Type:** NEG
- **Actor:** anonymous
- **Precondition:** Random UUID
- **Expected result:** 404/fail-closed; no private data
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-036.txt` or linked existing evidence

### TC-TRACE-037 — Injection-shaped trace ID is safe

- **Type:** NEG
- **Actor:** anonymous/attacker
- **Precondition:** SQL/script-shaped ID
- **Expected result:** Rejected without server error/leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-037.txt` or linked existing evidence

### TC-TRACE-038 — Unsealed/private batch is not publicly visible

- **Type:** NEG
- **Actor:** anonymous
- **Precondition:** Batch not sealed/public
- **Expected result:** Public route denied/not found
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-038.txt` or linked existing evidence

### TC-TRACE-039 — Public trace payload excludes private fields

- **Type:** SEC
- **Actor:** anonymous
- **Precondition:** Valid trace
- **Expected result:** No private docs, tokens, tenant internals
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-039.txt` or linked existing evidence

### TC-TRACE-040 — Local backend trace SLO p95 < 800ms

- **Type:** EDGE
- **Actor:** public traffic simulation
- **Precondition:** Seeded valid trace
- **Expected result:** All 200; p95 < 800ms
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-040.txt` or linked existing evidence

### TC-TRACE-041 — Local frontend proxy/cache trace SLO p95 < 800ms

- **Type:** EDGE
- **Actor:** public traffic simulation
- **Precondition:** Seeded valid trace
- **Expected result:** All 200; proxy cache hit; p95 < 800ms
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-041.txt` or linked existing evidence

### TC-TRACE-042 — Public Cloudflare trace SLO p95 < 800ms

- **Type:** EDGE
- **Actor:** external public traffic
- **Precondition:** Cloudflare route configured
- **Expected result:** All 200; p95 < 800ms
- **Current status:** FAIL/P0
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-042.txt` or linked existing evidence

### TC-TRACE-043 — Cloudflare cache status proves edge caching

- **Type:** EDGE
- **Actor:** external public traffic
- **Precondition:** Cache rule applied
- **Expected result:** cf-cache-status HIT/eligible or equivalent
- **Current status:** BLOCKED/P0
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-043.txt` or linked existing evidence

### TC-TRACE-044 — Authenticated/private APIs are not cached at public edge

- **Type:** SEC
- **Actor:** authenticated user
- **Precondition:** Cache rule deployed
- **Expected result:** Private endpoints bypass/no-store; no cross-user cache leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-044.txt` or linked existing evidence

### TC-TRACE-045 — CDN purge/invalidation path is documented/tested

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Cache rule deployed
- **Expected result:** Can purge affected trace cache safely
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-045.txt` or linked existing evidence

### TC-TRACE-046 — QR trace remains usable during app-proxy cache stale-while-revalidate

- **Type:** EDGE
- **Actor:** anonymous
- **Precondition:** Trace cache warm/stale
- **Expected result:** User still receives valid public data
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/trace/TC-TRACE-046.txt` or linked existing evidence

## CERT — Submission / Certificate Lifecycle

### TC-CERT-047 — Business submits certification application

- **Type:** HP
- **Actor:** business
- **Precondition:** Valid business account/data
- **Expected result:** Submission created with correct tenant/status
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-047.txt` or linked existing evidence

### TC-CERT-048 — Provider reviews submitted application

- **Type:** HP
- **Actor:** provider
- **Precondition:** Assigned submission exists
- **Expected result:** Provider can view/review allowed submission
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-048.txt` or linked existing evidence

### TC-CERT-049 — Provider requests revision

- **Type:** HP
- **Actor:** provider
- **Precondition:** Submission under review
- **Expected result:** Revision request recorded and visible to business
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-049.txt` or linked existing evidence

### TC-CERT-050 — Business resubmits after revision

- **Type:** HP
- **Actor:** business
- **Precondition:** Revision requested
- **Expected result:** Updated submission accepted and locked/versioned per policy
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-050.txt` or linked existing evidence

### TC-CERT-051 — Provider approves application

- **Type:** HP
- **Actor:** provider
- **Precondition:** Review complete
- **Expected result:** Status transitions to approved/ready for certificate
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-051.txt` or linked existing evidence

### TC-CERT-052 — Provider issues certificate

- **Type:** HP
- **Actor:** provider
- **Precondition:** Approved submission
- **Expected result:** Certificate created with valid submission/provider refs
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-052.txt` or linked existing evidence

### TC-CERT-053 — Business downloads own certificate PDF

- **Type:** HP
- **Actor:** business
- **Precondition:** Issued cert belongs to tenant
- **Expected result:** PDF download succeeds
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-053.txt` or linked existing evidence

### TC-CERT-054 — Public party verifies issued certificate

- **Type:** HP
- **Actor:** anonymous
- **Precondition:** Public certificate verification route
- **Expected result:** Valid status/data returned without private leak
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-054.txt` or linked existing evidence

### TC-CERT-055 — Wrong tenant cannot download certificate PDF

- **Type:** NEG
- **Actor:** business
- **Precondition:** Cert belongs to another tenant
- **Expected result:** 403/404 without leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-055.txt` or linked existing evidence

### TC-CERT-056 — Revoked certificate cannot be reactivated by status flip

- **Type:** NEG
- **Actor:** provider/admin
- **Precondition:** Certificate revoked
- **Expected result:** Conflict/denial; remains revoked
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-056.txt` or linked existing evidence

### TC-CERT-057 — Replacement certificate flow after revocation is explicit

- **Type:** EDGE
- **Actor:** provider
- **Precondition:** Certificate revoked
- **Expected result:** New certificate issued with trace/audit link to old one
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-057.txt` or linked existing evidence

### TC-CERT-058 — Expired certificate is not treated as active

- **Type:** EDGE
- **Actor:** public/business
- **Precondition:** Expired certificate fixture
- **Expected result:** Status/eligibility fail-closed
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-058.txt` or linked existing evidence

### TC-CERT-059 — Concurrent certificate issuance keeps unique numbers

- **Type:** EDGE
- **Actor:** provider/load
- **Precondition:** Parallel issuance
- **Expected result:** No duplicate certificate numbers
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-059.txt` or linked existing evidence

### TC-CERT-060 — Issue certificate without required submission ref fails safely

- **Type:** NEG
- **Actor:** provider/attacker
- **Precondition:** Missing/invalid submission_id
- **Expected result:** Request denied; no orphan cert
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-060.txt` or linked existing evidence

### TC-CERT-061 — Provider without authority cannot issue certificate for tenant

- **Type:** NEG
- **Actor:** provider
- **Precondition:** No ownership/authority evidence
- **Expected result:** Issuance denied
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-061.txt` or linked existing evidence

### TC-CERT-062 — Certificate lifecycle actions are audited

- **Type:** SEC
- **Actor:** provider/admin
- **Precondition:** Issue/revoke/update action
- **Expected result:** Audit event written
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/cert/TC-CERT-062.txt` or linked existing evidence

## PDF — PDF / Documents / Official Artifacts

### TC-PDF-063 — Certificate PDF renders for valid certificate

- **Type:** HP
- **Actor:** business/provider
- **Precondition:** Valid issued cert
- **Expected result:** Readable PDF generated
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-063.txt` or linked existing evidence

### TC-PDF-064 — PDF contains expected official fields

- **Type:** HP
- **Actor:** business/provider
- **Precondition:** Valid cert data
- **Expected result:** Business/cert dates/status fields present
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-064.txt` or linked existing evidence

### TC-PDF-065 — PDF visual baseline remains stable

- **Type:** EDGE
- **Actor:** QA
- **Precondition:** Baseline available
- **Expected result:** No unintended visual regression
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-065.txt` or linked existing evidence

### TC-PDF-066 — PDF generation does not expose private data to wrong role

- **Type:** SEC
- **Actor:** wrong tenant/lower role
- **Precondition:** Direct PDF URL/API call
- **Expected result:** Denied
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-066.txt` or linked existing evidence

### TC-PDF-067 — Missing optional PDF field degrades gracefully

- **Type:** EDGE
- **Actor:** business/provider
- **Precondition:** Fixture with optional gaps
- **Expected result:** No server error; approved placeholder/blank behavior
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-067.txt` or linked existing evidence

### TC-PDF-068 — Document version list works

- **Type:** HP
- **Actor:** authenticated user
- **Precondition:** Versioned document exists
- **Expected result:** Versions visible per permission
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-068.txt` or linked existing evidence

### TC-PDF-069 — Template/document UI loads without broken references

- **Type:** HP
- **Actor:** admin/provider
- **Precondition:** Template files present
- **Expected result:** UI loads and actions available
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-069.txt` or linked existing evidence

### TC-PDF-070 — Document upload/list APIs enforce tenant scope

- **Type:** SEC
- **Actor:** business/provider
- **Precondition:** Two tenants seeded
- **Expected result:** Only own docs visible
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-070.txt` or linked existing evidence

### TC-PDF-071 — Template repair guard catches missing required template

- **Type:** OPS
- **Actor:** QA/ops
- **Precondition:** Guard executed
- **Expected result:** Missing required template fails build/gate
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-071.txt` or linked existing evidence

### TC-PDF-072 — Large but allowed PDF/document request completes within timeout

- **Type:** EDGE
- **Actor:** business/provider
- **Precondition:** Large fixture within limits
- **Expected result:** Completes or returns controlled error
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/pdf/TC-PDF-072.txt` or linked existing evidence

## ADMIN — Admin / User / Organization CRUD

### TC-ADMIN-073 — Admin creates QA user/member

- **Type:** HP
- **Actor:** admin
- **Precondition:** Admin account
- **Expected result:** QA-prefixed user/member created
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-073.txt` or linked existing evidence

### TC-ADMIN-074 — Admin updates QA user/member

- **Type:** HP
- **Actor:** admin
- **Precondition:** QA user exists
- **Expected result:** Update visible and audited
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-074.txt` or linked existing evidence

### TC-ADMIN-075 — Admin disables QA user/member

- **Type:** HP
- **Actor:** admin
- **Precondition:** QA user exists
- **Expected result:** Disabled user cannot access protected resources
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-075.txt` or linked existing evidence

### TC-ADMIN-076 — Admin manages auditor/sub-role

- **Type:** HP
- **Actor:** admin
- **Precondition:** Org/user exists
- **Expected result:** Sub-role assigned/updated as policy allows
- **Current status:** PASS/RETEST
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-076.txt` or linked existing evidence

### TC-ADMIN-077 — Business user cannot create platform users

- **Type:** NEG
- **Actor:** business
- **Precondition:** Business token
- **Expected result:** Admin CRUD denied
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-077.txt` or linked existing evidence

### TC-ADMIN-078 — Provider user cannot reset another tenant user

- **Type:** NEG
- **Actor:** provider
- **Precondition:** Provider token
- **Expected result:** Forbidden
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-078.txt` or linked existing evidence

### TC-ADMIN-079 — Admin credential reset uses IdP API not ignored local field

- **Type:** SEC
- **Actor:** admin
- **Precondition:** QA user exists
- **Expected result:** Old/new login behavior proves reset
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-079.txt` or linked existing evidence

### TC-ADMIN-080 — Admin CRUD actions are audited

- **Type:** SEC
- **Actor:** admin
- **Precondition:** Create/update/disable actions
- **Expected result:** Audit records with actor/target
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-080.txt` or linked existing evidence

### TC-ADMIN-081 — QA-created admin records are cleaned up or documented

- **Type:** OPS
- **Actor:** QA/admin
- **Precondition:** QA test data created
- **Expected result:** Cleanup evidence exists
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-081.txt` or linked existing evidence

### TC-ADMIN-082 — Duplicate user email handling is safe

- **Type:** EDGE
- **Actor:** admin
- **Precondition:** Existing email
- **Expected result:** Clear validation error; no duplicate identity
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/admin/TC-ADMIN-082.txt` or linked existing evidence

## FE — Frontend / Browser / UX Critical

### TC-FE-083 — Full desktop Chromium matrix has zero failed tests

- **Type:** HP
- **Actor:** QA
- **Precondition:** Test env ready
- **Expected result:** 0 failed in full matrix
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-083.txt` or linked existing evidence

### TC-FE-084 — Frontend unit/component tests pass

- **Type:** HP
- **Actor:** QA
- **Precondition:** Dependencies installed
- **Expected result:** Vitest passes
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-084.txt` or linked existing evidence

### TC-FE-085 — Frontend lint passes

- **Type:** OPS
- **Actor:** QA/dev
- **Precondition:** Source tree ready
- **Expected result:** Lint returns success or only accepted warnings
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-085.txt` or linked existing evidence

### TC-FE-086 — Frontend production build passes

- **Type:** OPS
- **Actor:** QA/dev
- **Precondition:** Source tree ready
- **Expected result:** Next production build succeeds
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-086.txt` or linked existing evidence

### TC-FE-087 — Critical mobile public trace flow works

- **Type:** EDGE
- **Actor:** mobile visitor
- **Precondition:** Mobile browser/project
- **Expected result:** QR/trace page readable; no overflow/blocking
- **Current status:** REQUIRED
- **Release impact:** Production if mobile QR claim
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-087.txt` or linked existing evidence

### TC-FE-088 — Critical mobile login/dashboard works

- **Type:** EDGE
- **Actor:** mobile user
- **Precondition:** Mobile browser/project
- **Expected result:** Login and critical dashboard usable
- **Current status:** REQUIRED
- **Release impact:** Production if mobile users
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-088.txt` or linked existing evidence

### TC-FE-089 — Tablet layout does not break critical flows

- **Type:** EDGE
- **Actor:** tablet user
- **Precondition:** Tablet browser/project
- **Expected result:** No blocking layout issue
- **Current status:** REQUIRED
- **Release impact:** Production if tablet supported
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-089.txt` or linked existing evidence

### TC-FE-090 — Frontend does not expose protected content before auth

- **Type:** NEG
- **Actor:** anonymous
- **Precondition:** Direct route navigation
- **Expected result:** Protected content not rendered/leaked
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-090.txt` or linked existing evidence

### TC-FE-091 — Skipped browser tests are classified

- **Type:** OPS
- **Actor:** QA
- **Precondition:** Full matrix run
- **Expected result:** No unclassified P0/P1 skips
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-091.txt` or linked existing evidence

### TC-FE-092 — Critical pages have no obvious keyboard/accessibility blockers

- **Type:** A11Y
- **Actor:** user
- **Precondition:** Browser checks
- **Expected result:** Nav/forms usable at minimum
- **Current status:** REQUIRED
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/fe/TC-FE-092.txt` or linked existing evidence

## OPS — Reliability / Ops / Release

### TC-OPS-093 — Docker/services health check is green

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Stack started
- **Expected result:** Required services healthy
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-093.txt` or linked existing evidence

### TC-OPS-094 — Runtime smoke script passes

- **Type:** OPS
- **Actor:** ops/QA
- **Precondition:** Stack healthy
- **Expected result:** Core HTTP smoke passes
- **Current status:** PASS/RETEST
- **Release impact:** Demo, Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-094.txt` or linked existing evidence

### TC-OPS-095 — Deploy safety gates pass

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Release candidate
- **Expected result:** Pre-deploy checks green
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-095.txt` or linked existing evidence

### TC-OPS-096 — Rollback plan is documented and executable

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Release candidate
- **Expected result:** Rollback steps tested/dry-run
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-096.txt` or linked existing evidence

### TC-OPS-097 — Database backup exists before release

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Prod-like DB
- **Expected result:** Backup created and restorable artifact known
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-097.txt` or linked existing evidence

### TC-OPS-098 — Restore smoke or dry-run succeeds

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Backup artifact
- **Expected result:** Restore verified in safe environment
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-098.txt` or linked existing evidence

### TC-OPS-099 — Service restart does not corrupt state

- **Type:** CHAOS
- **Actor:** ops
- **Precondition:** Backup/approval
- **Expected result:** Service restarts cleanly; app recovers
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-099.txt` or linked existing evidence

### TC-OPS-100 — DB/network failure behavior is controlled

- **Type:** CHAOS
- **Actor:** ops
- **Precondition:** Explicit approval
- **Expected result:** Errors are safe; recovery steps proven
- **Current status:** DEFERRED/P0
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-100.txt` or linked existing evidence

### TC-OPS-101 — High-signal log scan has no critical runtime errors

- **Type:** OPS
- **Actor:** QA/ops
- **Precondition:** Scenario suite executed
- **Expected result:** No unresolved CRIT/P0 log patterns
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-101.txt` or linked existing evidence

### TC-OPS-102 — Rate-limit/security config present for auth/public routes

- **Type:** SEC
- **Actor:** security
- **Precondition:** Config accessible
- **Expected result:** Rate-limit posture documented/enforced
- **Current status:** PASS/RETEST
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-102.txt` or linked existing evidence

### TC-OPS-103 — Frontend dependency critical/high direct findings remediated or accepted

- **Type:** SEC
- **Actor:** security
- **Precondition:** npm audit run
- **Expected result:** 0 unresolved direct prod critical/high or formal acceptance
- **Current status:** WARN/P0
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-103.txt` or linked existing evidence

### TC-OPS-104 — Backend dependency auth-sensitive findings remediated or accepted

- **Type:** SEC
- **Actor:** security
- **Precondition:** pip audit run
- **Expected result:** No unresolved auth-sensitive unacceptable risk
- **Current status:** WARN/P1
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-104.txt` or linked existing evidence

### TC-OPS-105 — Secrets are not committed or printed

- **Type:** SEC
- **Actor:** security
- **Precondition:** Git/evidence scan
- **Expected result:** No secret leakage
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-105.txt` or linked existing evidence

### TC-OPS-106 — Monitoring/alert path for public trace/API is documented

- **Type:** OPS
- **Actor:** ops
- **Precondition:** Monitoring config
- **Expected result:** SLO breach can be detected
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-106.txt` or linked existing evidence

### TC-OPS-107 — Customer support runbook exists for certificate/QR issues

- **Type:** OPS
- **Actor:** ops/support
- **Precondition:** Runbook path
- **Expected result:** Support can triage common failures
- **Current status:** REQUIRED
- **Release impact:** Pilot, Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/ops/TC-OPS-107.txt` or linked existing evidence

## API — API Contract / Validation Coverage

### TC-API-108 — Direct API route `submissions` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-108.txt` or linked existing evidence

### TC-API-109 — Direct API route `certificates` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-109.txt` or linked existing evidence

### TC-API-110 — Direct API route `documents` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-110.txt` or linked existing evidence

### TC-API-111 — Direct API route `organizations` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-111.txt` or linked existing evidence

### TC-API-112 — Direct API route `users` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-112.txt` or linked existing evidence

### TC-API-113 — Direct API route `batches` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-113.txt` or linked existing evidence

### TC-API-114 — Direct API route `suppliers` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-114.txt` or linked existing evidence

### TC-API-115 — Direct API route `audit-events` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-115.txt` or linked existing evidence

### TC-API-116 — Direct API route `admin-settings` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-116.txt` or linked existing evidence

### TC-API-117 — Direct API route `public-verify` enforces auth and tenant boundary

- **Type:** SEC
- **Actor:** role matrix
- **Precondition:** Route included in inventory
- **Expected result:** Allowed roles pass; forbidden roles denied; no tenant leak
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-117.txt` or linked existing evidence

### TC-API-118 — Invalid or missing required fields for submission return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-118.txt` or linked existing evidence

### TC-API-119 — Invalid or missing required fields for certificate return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-119.txt` or linked existing evidence

### TC-API-120 — Invalid or missing required fields for batch return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-120.txt` or linked existing evidence

### TC-API-121 — Invalid or missing required fields for supplier return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-121.txt` or linked existing evidence

### TC-API-122 — Invalid or missing required fields for document return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-122.txt` or linked existing evidence

### TC-API-123 — Invalid or missing required fields for user return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-123.txt` or linked existing evidence

### TC-API-124 — Invalid or missing required fields for organization return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-124.txt` or linked existing evidence

### TC-API-125 — Invalid or missing required fields for auditor return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-125.txt` or linked existing evidence

### TC-API-126 — Invalid or missing required fields for template return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-126.txt` or linked existing evidence

### TC-API-127 — Invalid or missing required fields for trace fixture return clear validation error

- **Type:** NEG
- **Actor:** user/API client
- **Precondition:** Malformed payload
- **Expected result:** 4xx validation; no partial corrupt write
- **Current status:** REQUIRED
- **Release impact:** Production
- **Evidence slot:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/api/TC-API-127.txt` or linked existing evidence
