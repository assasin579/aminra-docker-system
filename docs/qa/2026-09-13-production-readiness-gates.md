# AMINRA — Production-Readiness Release Gates

Generated: 2026-09-13T09:45:16-04:00

## Executive decision rule

Production GO is allowed only when all P0 gates are PASS and all P1 gates are either PASS or explicitly risk-accepted by the owner. Demo PASS and production PASS are intentionally separate.

## Current verdict

- **Controlled sandbox demo:** GO WITH CAUTION.
- **Supervised pilot:** PARTIAL until public edge/CDN and production dependencies are closed or explicitly constrained.
- **Customer onboarding:** NO-GO until production SMTP verify-email/password-reset are proven.
- **Production GO:** NO-GO.

## P0 gates — must pass before production

### GATE-P0-01 — Public Edge/CDN Trace SLO

- **Why it matters:** Public QR/trace is customer-facing and can receive burst traffic.
- **Current status:** FAIL/BLOCKED.
- **Known evidence:** public route returns HTTP 200 but p95 is above 800ms and Cloudflare cache is DYNAMIC in prior run.
- **Required action:** Apply narrowly scoped Cloudflare cache rule for sealed public trace JSON only.
- **Success criteria:**
  - `GET /api/api/supply-chain/batches/trace/*` returns 200 for valid trace.
  - public p95 `<800ms` under agreed load profile.
  - `cf-cache-status: HIT` or equivalent edge-cache proof.
  - authenticated/private APIs are not cached.
- **Owner:** DevOps/platform.
- **Evidence path:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/edge-cdn/`

### GATE-P0-02 — Production SMTP / Account Email Flows

- **Why it matters:** Customer onboarding and account recovery depend on email.
- **Current status:** BLOCKED/PARTIAL; internal QA relay is not production SMTP.
- **Required action:** Configure/test production-grade TLS/auth SMTP.
- **Success criteria:**
  - Verify-email delivered externally.
  - Password-reset delivered externally.
  - Bounce/error handling observed.
  - No token/password leakage in logs.
- **Owner:** DevOps/security.
- **Evidence path:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/smtp/`

### GATE-P0-03 — Auth/RBAC/Tenant P0 Boundary Coverage

- **Why it matters:** AMINRA is regulated multi-tenant software; IDOR/cross-tenant leak is production-critical.
- **Current status:** Strong but must rerun in final pack.
- **Success criteria:**
  - 0 deferred P0 routes.
  - P0 anonymous/resource boundaries pass.
  - Live-token role matrix passes.
  - Static scanner has 0 HIGH tenant findings.
- **Owner:** QA/security.
- **Evidence path:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/rbac-tenant/`

### GATE-P0-04 — Certificate Lifecycle Integrity

- **Why it matters:** Certificates are regulated artifacts; incorrect lifecycle can create false trust.
- **Current status:** Strong after hardening but must rerun in final pack.
- **Success criteria:**
  - Provider issue -> business PDF download -> public verify passes.
  - Revoked cert cannot become active by status flip.
  - Wrong tenant PDF denied.
  - Concurrent cert numbers remain unique.
  - Audit events exist for issue/revoke.
- **Owner:** Backend/QA.
- **Evidence path:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/certificate/`

### GATE-P0-05 — Backup / Restore / Rollback

- **Why it matters:** Production confidence requires recovery, not only green tests.
- **Current status:** REQUIRED/DEFERRED.
- **Success criteria:**
  - Pre-release backup produced.
  - Restore smoke or dry-run succeeds in safe environment.
  - Rollback steps are executable and documented.
  - No destructive chaos without explicit approval.
- **Owner:** DevOps.
- **Evidence path:** `docs/qa/YYYY-MM-DD-production-readiness/evidence/recovery/`

## P1 gates — production blockers unless risk-accepted

### GATE-P1-01 — Dependency Security Remediation

- **Current status:** WARN.
- **Success criteria:** 0 unresolved direct production critical/high findings, or formal risk acceptance with compensating controls.

### GATE-P1-02 — Full Browser Matrix + Mobile Critical Flows

- **Current status:** Desktop strong; mobile/tablet must run if mobile QR/customer use is claimed.
- **Success criteria:** Full desktop green; mobile critical public QR/login/dashboard flows pass or support scope explicitly excludes mobile.

### GATE-P1-03 — Observability / High-Signal Log Scan

- **Current status:** Needs final-pack rerun.
- **Success criteria:** No unresolved critical logs after final scenario run; SLO breach detection documented.

### GATE-P1-04 — Data/Test Fixture Determinism

- **Current status:** Some env/data skips historically existed.
- **Success criteria:** No unclassified fixture/data P0/P1 skips in final production pack.

## Execution order

1. Freeze scope and release candidate commit.
2. Apply/fix Cloudflare edge cache config.
3. Configure production SMTP safely.
4. Remediate or risk-accept dependency findings.
5. Prepare backup/restore/rollback evidence.
6. Rerun full production-readiness test matrix.
7. Generate final `report.md`, `status.tsv`, `testcase-matrix.md`, and `release-gates.md`.
8. Manager signs off only if P0=0 and P1=0 unresolved.

## Final report shape

Expected directory:

```text
docs/qa/YYYY-MM-DD-production-readiness/
  report.md
  status.tsv
  testcase-matrix.md
  release-gates.md
  evidence/
    auth/
    rbac-tenant/
    trace/
    certificate/
    pdf-docs/
    admin/
    frontend-browser/
    edge-cdn/
    smtp/
    dependency/
    recovery/
```

## Explicit non-go conditions

- Public trace/QR p95 remains `>=800ms` on public edge path.
- Cloudflare stays `DYNAMIC` without alternate edge proof.
- Production SMTP not proven.
- Any P0 auth/tenant/certificate boundary fails or is deferred.
- Direct production critical/high dependency remains unresolved without risk acceptance.
- Backup/restore/rollback cannot be demonstrated.
