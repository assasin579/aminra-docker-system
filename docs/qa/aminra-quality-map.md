# AMINRA Quality Map — risk-based QA spine

Generated/started: 2026-09-02
Scope: pre-pilot maintenance hardening. This document is a working QA artifact; source-of-truth code must be verified before action.

## Verdict model

- **GO**: P0 security + runtime smoke green; no open P0/P1 unknowns in changed area.
- **CONDITIONAL GO**: controlled sandbox demo only; caveats explicitly scripted.
- **NO-GO**: auth, tenant isolation, certificate/document integrity, or runtime public hostname is broken.
- **BLOCKED**: required credentials/runtime/data missing, so no readiness claim is allowed.

## P0 release-blocking domains

1. **Auth/Keycloak/email** — registration/login/callback/verify-email must work in the selected mode. If Keycloak `verifyEmail=true`, SMTP must be configured and a live send test must pass.
2. **Tenant isolation / IDOR** — Tenant A cannot read or mutate Tenant B supply-chain, document, certificate, photo, dossier, submission, export, or job data.
3. **RBAC** — backend enforces role boundaries even when UI hides controls. Admin/provider/business/auditor/anonymous negative cases are mandatory.
4. **Certificate + PDF integrity** — official-looking artifacts require authorized role/state; public verify returns only safe fields and correct revocation/expiry status.
5. **Supply-chain traceability** — supplier/material/process/batch/step/photo access is scoped by ownership; public trace is filtered.
6. **Runtime capability** — containers healthy is insufficient; smoke must verify frontend, backend, Keycloak discovery, auth redirect, log scan, and public hostnames.

## P1 domains

- Upload validation and storage path safety.
- Async job status privacy.
- Audit log coverage for sensitive actions.
- GDPR export/deletion flows.
- Demo seed data determinism and cleanup.

## Test suite target split

- `release-p0-security`: tenant isolation, RBAC, public/private leak, official PDF permission, upload/path safety.
- `release-core-api`: registration/auth-me/documents/submissions/certificates/supply-chain lifecycle.
- `frontend-critical-contract`: landing CTA, auth callback, protected-route guard, critical forms, error states.
- `e2e-demo-spine`: 8–12 browser flows with QA seed accounts.
- `runtime-smoke`: read-only deploy checks; fails on P0 capability drift.
- `legacy-regression-quarantine`: known red/stale/flaky tests with owner/date; not mixed into release-blocking signal.

## Definition of Done for AMINRA hardening

A change is **DONE** only when:

- Targeted tests pass.
- P0/security suite is not regressed.
- Frontend build/type checks pass if frontend changed.
- Runtime smoke passes if Docker/env/auth/public URL changed.
- Any found bug is reported before fixing unless Khaled explicitly approved the fix.
- Remaining gaps are labelled PARTIAL/BLOCKED, not hidden.
