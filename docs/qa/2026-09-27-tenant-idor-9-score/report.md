# Tenant / IDOR / Security Boundaries 9-score readiness evidence — 2026-09-27

## Verdict

Current lane verdict: PASS for the safe source/test/documentation closure targeted in this agent lane. The tenant/IDOR readiness evidence is materially closer to 9/10 because current route inventory has no deferred P0/P1 rows, high-risk anonymous/resource probes were expanded, and static scanner remains at 0 HIGH findings.

This is not a full production/customer-pilot GO. It does not close dependency vulnerabilities, public edge/SLO, SMTP/customer onboarding, or broad mobile/browser gates.

## Gaps found before changes

1. The prior 2026-09-13 evidence still reported 8/10 with two deferred P1 rows: GET /auth/me and GET /api/feature-flags/me.
2. Regenerating the route inventory on the current branch discovered newer high-risk route families not represented in the old 242-route snapshot: certification decisions, conflicts, complaints/appeals, module activation, and official artifacts.
3. Without a stricter coverage gate, P1 rows could remain deferred even when chasing 9/10 readiness.
4. The generated TSV used CSV defaults/empty terminal columns, which caused git diff --check noise after regeneration.

## What changed

- Added a stricter coverage regression in backend/tests/test_route_tenant_inventory_coverage.py: every P0/P1 row must be covered and must name executable evidence; owned deferral is no longer enough for this 9-score gate.
- Expanded backend/tests/test_unauth_route_boundaries.py with executable anonymous negative probes for:
  - /auth/me
  - /api/feature-flags/me
  - /api/official-artifacts and /api/official-artifacts/{artifact_id}/file
  - /api/certification-decisions/*
  - /api/complaints/*
  - /api/conflicts/*
  - /api/me/modules and /api/me/module-activation-requests
- Updated scripts/qa/build_route_tenant_inventory.py coverage mapping for current high-risk route families and made TSV generation git-diff-check clean by using LF line endings and n/a placeholders for covered empty owner/reason fields.
- Regenerated the route inventory both in the historical default location and in this current evidence pack.

## Evidence summary

Evidence directory: docs/qa/2026-09-27-tenant-idor-9-score/

Key outputs:

- route-inventory.tsv: 273 routes inventoried.
- status.tsv: machine-readable PASS/WARN summary for this lane.
- static-scan-findings.json: current static tenant-boundary scan.
- evidence/terminal/009-route-inventory-final-check.txt:
  - routes: 273
  - P0_ADMIN_GLOBAL: 41
  - P0_RESOURCE_IDOR: 143
  - P0_FILE_OBJECT: 38
  - P1_TENANT_LIST: 35
  - P1_PUBLIC_SEALED: 3
  - P2_HEALTH_OR_STATIC: 13
  - coverage: covered 273
  - p0_p1_deferred_or_unmapped: 0
- evidence/terminal/005-static-scan-high-check.txt:
  - finding_count: 189
  - severity_counts: INFO 8, MEDIUM 181
  - high_count: 0
- evidence/terminal/011-focused-inventory-unauth-tests-final.txt:
  - 57 passed
- evidence/terminal/007-focused-route-family-tests.txt:
  - 23 passed, 6 skipped
  - skipped tests were pre-existing env/contract skips in focused suites, not new failures from this lane.
- evidence/terminal/010-git-diff-check.txt:
  - PASS, no output.

## Residual risks

- Static scanner still reports 181 MEDIUM and 8 INFO review prompts. None are HIGH, but they remain review backlog and should be batch-triaged by route family.
- Route-inventory coverage is evidence-mapped and has anonymous negative probes for newly added families, but it is not a guarantee that every route has full wrong-role plus live cross-tenant data-mutation coverage.
- Focused route-family test run included 6 skips due existing environment/contract conditions.
- Backend manual guard/RBAC migration risk remains; backend enforcement remains authoritative.
- Production/customer-pilot readiness remains partial until dependency security backlog and non-tenant gates are closed.

## Exact next step

Convert the 181 MEDIUM scanner findings into route-family review tickets, starting with file/object and resource-id routes that still rely on representative coverage, then add wrong-role/cross-tenant live-token tests for any route family lacking direct negative coverage.

## Safety notes

- No commit, push, deploy, destructive cleanup, broad package upgrade, or audit fix was performed.
- No secrets/tokens/env values were printed.
- To run current host changes inside the backend container without deploying, selected changed test/inventory files were copied into the running container for focused pytest only; runtime services were not rebuilt/restarted.
