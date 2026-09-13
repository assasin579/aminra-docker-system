# Load / Chaos / Deploy + Dependency Security Improvement Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Raise AMINRA risk-based test coverage for `load/chaos/deploy` and `dependency security` to at least **8.0/10** without hiding production blockers or weakening gates.

**Architecture:** Split the work into two independent lanes: resilience/release-operability and dependency-vulnerability remediation. Each lane must produce executable gates, durable evidence under `docs/qa/`, and an updated readiness verdict. Public edge/CDN SLO and dependency audit results must be treated as release gates, not advisory-only notes.

**Tech Stack:** Docker Compose, FastAPI backend, Next.js frontend, Playwright, pytest, npm audit, pip-audit, Cloudflare/public edge path, existing QA evidence structure.

---

## Success Criteria

Target scores:

- `09-load-chaos-deploy`: **5.5/10 -> >=8.0/10**
- `10-dependency-audit`: **5.5/10 -> >=8.0/10**
- Overall functional QA coverage: **7.4/10 -> >=8.0/10**

Required PASS gates:

1. Public trace SLO: `dev-web.silvergem.org` path `/api/api/supply-chain/batches/trace/*` reaches p95 `<800ms` under the established load profile, with Cloudflare/cache status `HIT` or explicit cache-eligible evidence after warmup.
2. Local backend and local frontend/proxy SLO remain PASS after changes.
3. Non-destructive chaos/recovery drills pass with documented degraded-mode expectations.
4. Deploy safety gates pass and include rollback/recreate evidence.
5. Frontend direct critical/high production dependency advisories are resolved or formally risk-accepted with compensating controls.
6. Backend `python-jose`/`ecdsa` risk is remediated or replaced/accepted with auth-sensitive justification.
7. Final report updates `status.tsv`, `report.md`, and AMINRA brain with honest verdict lanes.

Non-goals:

- Do not run destructive chaos without explicit founder approval and backup verification.
- Do not use `npm audit fix --force` blindly.
- Do not claim production GO unless SMTP/customer-onboarding is also resolved separately.

---

## Phase 0 — Baseline Lock and Evidence Setup

### Task 0.1: Capture baseline boundary

**Objective:** Freeze the before-state so improvements are auditable.

**Files:**
- Create: `docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/001-baseline.txt`
- Create/update: `docs/qa/2026-09-13-load-chaos-depsec-8of10/status.tsv`
- Create/update: `docs/qa/2026-09-13-load-chaos-depsec-8of10/report.md`

**Commands:**

```bash
mkdir -p docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal
{
  date -Is
  git rev-parse --show-toplevel
  git rev-parse HEAD
  git status --short
  docker compose ps
} 2>&1 | tee docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/001-baseline.txt
```

**Expected:** Evidence file exists, secrets are not printed.

---

## Phase 1 — Public Edge/CDN SLO Closure

### Task 1.1: Re-run split SLO profile before changes

**Objective:** Confirm current failure and preserve local-vs-public split.

**Files:**
- Evidence: `docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/010-public-trace-slo-before.txt`

**Commands:**

Use the existing public trace fixture/SLO script from prior evidence. Capture:

- local backend p50/p95/max/errors
- local frontend proxy p50/p95/max/errors
- public frontend p50/p95/max/errors
- `cache-control`, `cdn-cache-control`, `cloudflare-cdn-cache-control`
- `cf-cache-status`
- `x-aminra-proxy-cache`

**Expected current baseline:** local backend/proxy PASS, public `dev-web` FAIL with `cf-cache-status: DYNAMIC` unless already fixed externally.

### Task 1.2: Identify edge ownership path

**Objective:** Determine whether the fix lives in Cloudflare UI/API, Terraform, tunnel config, frontend route config, or proxy headers.

**Files to inspect:**
- `docker-compose.yml`
- frontend proxy/API route files under `frontend/aminra-web/`
- any Cloudflare/tunnel/deploy scripts if present
- docs mentioning `dev-web.silvergem.org`, Cloudflare, or tunnel

**Decision:**

- If Cloudflare credentials/config are available: implement Cloudflare Cache Rule/Worker/Page Rule.
- If not available: mark edge fix BLOCKED and propose the exact Cloudflare rule for manual application.

### Task 1.3: Implement public trace cache eligibility

**Objective:** Make public sealed trace JSON edge-cacheable without caching private data.

**Acceptance guardrails:**

- Only `GET` sealed public trace endpoint is cacheable.
- Invalid/unsealed/private trace responses must not leak private data.
- Do not cache authenticated/private endpoints.
- TTL should be short and safe: edge TTL 30-60s, stale-while-revalidate 30-60s.

**Candidate Cloudflare rule:**

```text
if http.request.method == "GET"
and http.host == "dev-web.silvergem.org"
and starts_with(http.request.uri.path, "/api/api/supply-chain/batches/trace/")
then cache eligible / cache everything for status 200 with Edge TTL 30-60s
```

**Expected:** After warmup, `cf-cache-status` should be `HIT` or equivalent cache-eligible status for valid sealed trace.

### Task 1.4: Rerun SLO after edge fix

**Objective:** Prove public SLO closure.

**Evidence:**
- `docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/011-public-trace-slo-after.txt`

**Expected PASS:**

- local backend p95 `<800ms`
- local frontend/proxy p95 `<800ms`
- public `dev-web` p95 `<800ms`
- no 5xx/errors
- cache status proves edge cache eligibility/HIT after warmup

---

## Phase 2 — Non-Destructive Chaos / Recovery Gates

### Task 2.1: Define safe chaos matrix

**Objective:** Run only drills that do not destroy data and can be restored quickly.

**Matrix:**

- Redis restart: sessions/jobs degrade/recover.
- Qdrant restart/disconnect: RAG/chat degraded but core auth/supply-chain remains alive.
- Keycloak restart: authenticated requests fail closed; public sealed trace remains available.
- Backend recreate: public trace and health recover within target window.
- Frontend recreate: public routes recover; no service-worker stale hard failure.

**Evidence:**
- `docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/020-chaos-matrix-plan.txt`

### Task 2.2: Verify backup/recovery preconditions

**Objective:** Avoid unsafe chaos.

**Commands:**

```bash
{
  date -Is
  docker compose ps
  # Include existing backup check command if project has one.
} 2>&1 | tee docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/021-chaos-preconditions.txt
```

**Expected:** All services healthy before drills; backup path known for DB-impacting drills. If backup is not confirmed, skip destructive DB drills.

### Task 2.3: Run safe drill one service at a time

**Objective:** Prove controlled degradation/recovery.

**Evidence:**
- `022-chaos-redis-restart.txt`
- `023-chaos-qdrant-restart.txt`
- `024-chaos-keycloak-restart.txt`
- `025-chaos-backend-recreate.txt`
- `026-chaos-frontend-recreate.txt`

**For each drill:**

1. Capture before health.
2. Restart/recreate exactly one service.
3. Probe critical endpoints during outage.
4. Wait for recovery.
5. Probe after health.
6. Record elapsed recovery time and expected degraded behavior.

**PASS criteria:**

- No data loss.
- Public trace remains available during non-dependent outages where expected.
- Auth fails closed during Keycloak outage.
- Service returns healthy within agreed recovery window.
- No persistent 5xx after recovery.

---

## Phase 3 — Deploy Safety / Rollback Evidence

### Task 3.1: Rerun deploy safety gates

**Objective:** Confirm unsafe deploy paths fail closed and approved dry-run works.

**Evidence:**
- `docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/030-deploy-safety-gates.txt`

**Expected:**

- unsafe default deploy fails
- maintenance-window dry-run passes
- unsupported rolling path fails closed or is explicitly not implemented

### Task 3.2: Add rollback/recreate smoke

**Objective:** Ensure rollback/recreate is operationally testable, not just documented.

**Evidence:**
- `031-rollback-smoke.txt`

**PASS criteria:**

- Can identify current image/tag/digest.
- Can dry-run rollback/recreate command safely.
- Health smoke passes after recreate.
- If real rollback is not executed, status is PARTIAL with reason.

---

## Phase 4 — Frontend Dependency Security Remediation

### Task 4.1: Capture exact npm audit JSON

**Objective:** Know the real advisories and dependency paths before changing packages.

**Files:**
- Evidence: `040-frontend-npm-audit-before.json`
- Summary: `041-frontend-npm-audit-before-summary.txt`

**Commands:**

```bash
cd frontend/aminra-web
npm audit --json > ../../docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/040-frontend-npm-audit-before.json || true
npm audit 2>&1 | tee ../../docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/041-frontend-npm-audit-before-summary.txt
```

### Task 4.2: Controlled upgrade plan

**Objective:** Upgrade direct production blockers without forcing breaking unrelated transitive jumps.

**Rules:**

- Do not run `npm audit fix --force` as first move.
- Upgrade direct vulnerable packages explicitly.
- Prioritize production runtime packages over dev-only packages.
- If Next upgrade triggers ESLint/React/build changes, handle deliberately.

**Likely files:**
- `frontend/aminra-web/package.json`
- `frontend/aminra-web/package-lock.json`

**Expected direct target:**

- Upgrade `next@16.2.4` to a patched compatible version if available in registry.
- Upgrade other direct high/critical runtime packages from audit output.

### Task 4.3: Verify frontend after upgrades

**Evidence:**
- `042-frontend-install.txt`
- `043-frontend-lint.txt`
- `044-frontend-vitest.txt`
- `045-frontend-build.txt`
- `046-frontend-playwright-focused.txt`
- `047-frontend-npm-audit-after.txt`

**Commands:**

```bash
cd frontend/aminra-web
npm install
npm run lint
npm test
npm run build
npm audit
```

Run focused Playwright auth/admin/public trace specs after build if the app is running.

**PASS criteria:**

- lint PASS
- tests PASS
- build PASS
- audit no direct critical/high production blocker, or any remaining finding has reachability/risk acceptance documented

---

## Phase 5 — Backend Dependency Security Remediation

### Task 5.1: Capture exact pip audit JSON

**Objective:** Confirm `ecdsa`/`python-jose` path and any other current findings.

**Evidence:**
- `050-backend-pip-audit-before.txt`

**Command:**

```bash
cd backend
pip-audit 2>&1 | tee ../docs/qa/2026-09-13-load-chaos-depsec-8of10/evidence/terminal/050-backend-pip-audit-before.txt
```

### Task 5.2: Decide jose remediation path

**Objective:** Remove or justify auth-sensitive crypto warning.

**Preferred option:**

- Replace `python-jose` with maintained `PyJWT[crypto]` or `authlib` if code surface is small and tests can prove compatibility.

**Fallback option:**

- If replacement is too risky for this sprint, create formal risk acceptance with:
  - affected package/path
  - actual code reachability
  - compensating controls
  - owner
  - expiry date
  - follow-up ticket

**Files likely touched:**
- backend dependency manifest (`requirements*.txt`, `pyproject.toml`, or similar)
- JWT/auth utility files if replacing library
- auth tests around JWT validation/JWKS/role boundaries

### Task 5.3: Verify backend auth/security after remediation

**Evidence:**
- `051-backend-dep-install.txt`
- `052-backend-auth-tests.txt`
- `053-backend-tenant-tests.txt`
- `054-backend-pip-audit-after.txt`

**Commands:**

```bash
cd backend
pytest tests/test_keycloak_token_security.py tests/test_keycloak_jwks_edge.py tests/test_dual_auth_unit.py tests/test_role_boundaries_live_smoke.py -q
pytest tests/uat/test_uat_c_tenant_isolation.py -q
pip-audit
```

**PASS criteria:**

- Auth/JWKS/tenant tests pass.
- No untriaged auth-sensitive high/critical dependency finding remains.

---

## Phase 6 — Final Full Regression and Score Update

### Task 6.1: Rerun critical customer-ready gates

**Objective:** Ensure load/dep changes did not regress the broader system.

**Evidence:**
- `060-final-critical-gates.txt`

**Minimum gates:**

- backend tenant UAT: `50 passed`
- P0 anonymous boundary: `32 passed`
- frontend lint/test/build PASS
- Playwright desktop focused or full matrix PASS depending runtime time budget
- public trace SLO PASS
- npm audit/pip-audit final PASS/WARN accepted

### Task 6.2: Write final score report

**Objective:** Update score with evidence-backed verdict.

**Files:**
- `docs/qa/2026-09-13-load-chaos-depsec-8of10/report.md`
- `docs/qa/2026-09-13-load-chaos-depsec-8of10/status.tsv`
- `docs/qa/2026-09-12-customer-ready-full-system/report.md`
- `docs/qa/2026-09-12-customer-ready-full-system/status.tsv`
- `/home/user/Documents/all-docs/02-Projects/aminra/README.md`
- `/home/user/Documents/all-docs/02-Projects/aminra/sessions/2026-09-13.md`
- `/home/user/Documents/all-docs/MASTER_INDEX.md`

**Expected final score if all gates pass:**

- Load/chaos/deploy: `>=8.0/10`
- Dependency security: `>=8.0/10`
- Overall QA coverage: `>=8.0/10`

**If any P0 remains:** mark PARTIAL/BLOCKED; do not round up.

---

## Execution Order

P0 first:

1. Baseline evidence.
2. Public edge/CDN SLO fix and rerun.
3. Frontend dependency controlled upgrade.
4. Backend dependency remediation/risk acceptance.
5. Non-destructive chaos drills.
6. Deploy rollback/recreate evidence.
7. Final regression + report/brain update.

## Rollback / Safety

- Before dependency upgrades, preserve `package-lock.json` and backend dependency diff in git.
- Commit in small logical chunks only after green gates and user authorization.
- Do not push/deploy without explicit approval.
- Do not run destructive chaos against DB/object storage without backup and explicit approval.
