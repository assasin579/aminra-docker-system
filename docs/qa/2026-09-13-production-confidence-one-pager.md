# AMINRA — Manager Production Confidence One-Pager

Generated: 2026-09-13T09:45:16-04:00

## Recommendation

Do not use the old plan of only checking happy paths. Move to a production-readiness gate model.

## Current decision

- Sandbox demo: **GO WITH CAUTION**
- Supervised pilot: **PARTIAL**
- Customer onboarding: **NO-GO until production SMTP passes**
- Production: **NO-GO until P0 gates pass**

## What changed in the plan

- Test cases expanded from scenario summary to **127 manager-level cases**.
- Cases are grouped by production risk: auth, RBAC/tenant, public trace, certificate, PDF/docs, admin CRUD, frontend/browser, ops/reliability, API validation.
- Release decision is now controlled by explicit P0/P1 gates, not raw test count.

## P0 blockers to close first

1. Public Cloudflare edge/CDN trace SLO and cache proof.
2. Production SMTP verify-email/password-reset.
3. Final auth/RBAC/tenant P0 rerun with 0 deferred P0.
4. Certificate lifecycle final rerun including wrong-tenant and revocation controls.
5. Backup/restore/rollback evidence.

## Files created

- `docs/qa/2026-09-13-production-readiness-testcase-matrix.md`
- `docs/qa/2026-09-13-production-readiness-gates.md`
- `docs/qa/2026-09-13-production-confidence-one-pager.md`
