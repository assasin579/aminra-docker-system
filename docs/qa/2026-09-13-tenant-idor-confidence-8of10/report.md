# Tenant / IDOR / Data Isolation Confidence Report — 2026-09-13

## Executive verdict

**Current confidence: 8/10 — PASS WITH RESIDUAL WARNINGS.**

The previous blockers for an honest 8/10 have been closed in this evidence pass: live-token Keycloak tenant UAT now runs to completion, top P0 route-family negative tests are executable, all P0 route inventory rows are mapped to evidence, and static tenant-boundary scanner HIGH findings are closed. This is not a production GO by itself; it is a tenant/IDOR confidence verdict for this repo/environment.

## What was implemented / hardened

- Route inventory generator: `scripts/qa/build_route_tenant_inventory.py`
- Route coverage pytest gate: `backend/tests/test_route_tenant_inventory_coverage.py`
- Static tenant-boundary scanner: `scripts/qa/scan_tenant_boundary_risks.py`
- Allowlist scaffold: `docs/qa/tenant-boundary-allowlist.yml`
- Live-token UAT DB fallback for host/container execution: `backend/tests/uat/conftest.py`
- Token enrichment fixes for query-token document/audit/certificate file routes:
  - `backend/auth/document_router.py`
  - `backend/auth/audit_router.py`
  - `backend/auth/certificate_router.py`
- Anonymous boundary hardening/negative tests for resource/file/token-adjacent routes:
  - `backend/tests/test_unauth_route_boundaries.py`
- Evidence pack: `docs/qa/2026-09-13-tenant-idor-confidence-8of10/`

## Route inventory summary

- Total routes inventoried: **242**
- Risk classes:
  - P0_RESOURCE_IDOR: 129
  - P0_FILE_OBJECT: 36
  - P1_TENANT_LIST: 31
  - P0_ADMIN_GLOBAL: 30
  - P2_HEALTH_OR_STATIC: 13
  - P1_PUBLIC_SEALED: 3

- Coverage statuses:
  - covered: 240
  - deferred: 2

- Deferred route rows: **2**
- Deferred P0 route rows: **0**

Deferred rows remaining:
- GET `/api/feature-flags/me` — P1_TENANT_LIST (backend/auth/feature_flags_router.py:63)
- GET `/auth/me` — P1_TENANT_LIST (backend/auth/router.py:150)

## Evidence run

1. Route inventory coverage gate:
   - Evidence: `evidence/terminal/011-route-inventory-coverage-after-family-expansion.txt`
   - Result: **3 passed**

2. Live-token tenant/IDOR UAT with QA platform-admin env:
   - Evidence: `evidence/terminal/008-tenant-uat-final-live-token.txt`
   - Result: **50 passed / 0 failed**
   - Earlier failures on document preview/file route returned `500`; fixed by enriching raw Keycloak query/header token claims before role/tenant checks.

3. P0 anonymous/resource boundary deterministic tests:
   - Evidence: `evidence/terminal/009-p0-anonymous-resource-boundaries-final.txt`
   - Result: **32 passed / 0 failed**
   - Covers high-risk unauthenticated probes for document preview/file, certificate PDF, audit report PDF, jobs, reviews, admin/supply-chain/document routes.

4. Static scanner:
   - Evidence: `static-scan-findings.json`
   - Findings: **169** total — **0 HIGH**, **161 MEDIUM**, **8 INFO**.
   - Previous HIGH findings are closed via route auth hardening, token-enrichment fixes, scanner intent recognition, and deterministic negative tests.

5. Historical baseline evidence retained for traceability:
   - `001-route-inventory-coverage-gate.txt`: **3 passed** before final family expansion.
   - `002-existing-tenant-idor-suite-rerun.txt`: **65 passed / 55 skipped** before QA admin env was loaded.
   - `005-tenant-uat-with-admin-env-asyncpg-db.txt`: **48 passed / 2 failed** exposing document file/preview 500s.
   - `006-tenant-uat-after-doc-file-preview-fix.txt`: **50 passed** after fix.
   - `007-p0-anonymous-resource-boundaries.txt`: **31 passed / 1 failed** due stale certificate route path; superseded by final `009` run.

## Why 8/10 is now defensible

The prior blockers are closed:

1. **Live-token/UAT skip blocker closed** — tenant UAT final run is `50 passed`, not skipped.
2. **Deferred P0 route rows closed** — route inventory has `0` deferred P0 rows.
3. **Static HIGH findings closed** — scanner now reports `0 HIGH` findings.
4. **High-risk P0 route families have deterministic negative coverage** — anonymous probes for file/doc/PDF/job/review/admin/resource routes pass.

## Residual warnings / not covered by this verdict

- `161 MEDIUM` and `8 INFO` scanner findings remain review backlog; none are currently classified as HIGH.
- Two P1 rows remain deferred: `/api/feature-flags/me` and `/auth/me`; these are identity/profile surfaces, not P0 object/file/admin routes in this inventory gate.
- This score covers tenant/IDOR/data-isolation confidence only. It does **not** override public edge SLO failure, SMTP/customer-onboarding blocker, frontend dependency vulnerabilities, or production secret/infra readiness.
- Evidence is environment-specific and should be rerun after route/auth changes.

## Verdict ladder

- Tenant/IDOR confidence: **8/10 PASS WITH RESIDUAL WARNINGS**.
- Sandbox/demo tenant-isolation support: **PASS**.
- Production GO: **not implied**; still blocked elsewhere by public edge SLO, SMTP live-send, and dependency remediation.

## Next controls

P0/P1 maintenance:
- Add this inventory + scanner + coverage gate + tenant UAT lane to CI before merging auth/router changes.
- Keep scanner HIGH at `0`; any new HIGH must fail the release gate until tested, fixed, or explicitly allowlisted with owner/review date.
- Convert the remaining two P1 deferred identity/profile rows into explicit coverage or documented allowlist.
- Review MEDIUM findings in batches, prioritizing routes with resource IDs, file artifacts, or cross-tenant list behavior.
