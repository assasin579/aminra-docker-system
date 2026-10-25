# AMINRA Dashboard UX & chart contracts — 2026-10-24

## Verdict

**PARTIAL — scoped dashboard gates and frontend-only deployment PASS; repository-wide FE tests/lint and browser visual QA remain incomplete.** This is not end-to-end acceptance or a pilot GO. STOP C remains unchanged.

## Scope delivered

- Admin Analytics: renamed the status-count visualization as a *status distribution* (not a conversion funnel), made the chart data accessible, and presented monthly issuance as a time series with missing months zero-filled rather than omitted. Expiry groups use non-overlapping day ranges.
- Business dashboard: added status/score visual breakdowns, made the score sample explicit, removed the hard-coded `/7` quota, differentiated unscored uploaded documents from missing uploads, and added visible retryable API failure states.
- Provider owner/auditor page: added role-specific workload/status charts from existing API values and visible retryable errors for failed stats/queue requests.
- Shared chart UI: SVG/HTML visualizations include accessible labels and a tabular alternative (visible on small screens, screen-reader accessible at larger breakpoints). No chart dependency was added and no synthetic KPI/trend was introduced.
- Tests added/updated for semantics, monthly gaps, role-specific chart content, accessibility labels and API failure/retry behavior.

## Verification

- Focused Vitest on the exact release-context tree: **12 passed** (2 files).
- Existing deploy-gate root/landing + OIDC contracts: **33 passed**.
- Targeted ESLint on all six changed dashboard/component/test files — **PASS**, zero warnings; `npx tsc --noEmit` — **PASS**; `git diff --check` — **PASS**.
- Production build: host `npm run build` and Docker webpack build from the exact release-context tree — **PASS**.
- `npm audit --omit=dev` — **0 production dependency findings**. Full lockfile audit returned **2 high + 3 moderate**, all outside the production dependency graph; remediation was not mixed into this dashboard change.
- Default frontend deploy dry-run ran root/OIDC tests (**33 passed**) but stopped at repository-wide ESLint with **4 existing errors** in unchanged `app/audits/[id]/page.tsx` (2 `react-hooks/refs`) and `app/documents/page.tsx` (2 `react-hooks/refs`). These files are not part of the dashboard commit.
- Full Vitest on the release-context tree: **281 passed, 4 failed** across 50 files / 285 tests. The failures are outside dashboard scope and in files not modified for this task:
  - `admin-user-keycloak-only-contract.test.ts`: expected one POST target, source now exposes three deletion workflow targets.
  - 3 cases in `supply-chain-eligible-suppliers.test.tsx`: test runtime sees the fail-closed `supplier_management` module gate, so the expected eligible-supplier UI is not reached.
  These failures were not changed to avoid broadening scope or weakening module/identity guardrails.
- After the scoped gates above, the project `frontend-only.sh --skip-tests --base HEAD~1` lane built and recreated only `aminra-frontend`; its protected-service start-time guard passed. Frontend container is healthy; local and public smoke: `/` → `307 /landing`, `/landing` → `200`; local Admin/Business/Provider dashboard routes returned `200`. Running image: `sha256:0b6270b1a0b7742550eb64cabfe0a6ece5779a1c1f81f7092332b226968f59a0`; rollback tag `aminra-frontend:rollback-dashboard-008c9fd` preserves prior image `sha256:818b7e4cddbeadaa6ddafa92a502b311dcd0ba991073be315512bdd5927cd829`.
- Commits: feature branch `008c9fd` (`feat(dashboard): add role-specific analytics charts`); release worktree `fb3a673` on top of landing release `cbf1d55`. The six dashboard paths match between commits; the release tree additionally contains its landing-release changes. No push performed.
- Browser visual QA: **not run**. No system Chromium/browser executable is available. No browser/dependency was installed and no credentialed role UAT was attempted. No visual screenshot is claimed.

## Safety / release boundary

- Only the frontend runtime was recreated; backend, Postgres, Qdrant, Redis, Keycloak, and worker were not restarted. No migration or business-data mutation was performed.
- No credentials or customer data were used or included in this report.
- STOP C and customer-pilot NO-GO remain in force.
- Full-suite failures, existing repository-wide lint errors, and absent browser/role evidence prevent claiming end-to-end 100% acceptance.

## Changed paths

- `frontend/aminra-web/components/dashboard/DashboardCharts.tsx`
- `frontend/aminra-web/app/admin/analytics/page.tsx`
- `frontend/aminra-web/app/dashboard/business/page.tsx`
- `frontend/aminra-web/app/dashboard/provider/page.tsx`
- `frontend/aminra-web/__tests__/dashboard-visual-contracts.test.tsx`
- `frontend/aminra-web/__tests__/admin-analytics.test.tsx`
