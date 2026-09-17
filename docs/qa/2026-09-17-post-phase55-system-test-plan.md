# AMINRA Post-Phase 5.5 Full-System Test Plan

> **Status:** plan only — no tests executed by this document.
> **Created:** 2026-09-17 03:34 local
> **Code HEAD at planning time:** `8382941`
> **Goal:** rebuild confidence after 2026-09-16→17 auth/login UX, Keycloak/auth-domain/SMTP, modular monolith Phase 0-5.5, Docker/containerd recovery, Redis AOF repair, and immutable deploy work.

## Executive decision

Run this as a **risk-based confidence sweep**, not a raw “run everything” marathon. The pass/fail verdict must be split into lanes:

- **Runtime recovery:** Docker/Redis/Postgres/Qdrant/Keycloak/backend/frontend stable.
- **Release pipeline:** verify/build/deploy scripts remain reproducible.
- **Auth/session:** business/provider/admin/demo-account SSO and logout/session isolation still work.
- **Modularization:** module registry, `/api/me/modules`, default-off guards, sidebar rendering remain correct.
- **Core business flows:** supply-chain materials/process/batches and public landing/login surfaces still work.
- **Security boundaries:** tenant/role/anonymous route negatives still reject access.
- **Production caveats:** anything SMTP/edge/customer-onboarding related remains separate from local/dev PASS.

Final labels:

- `PASS` — executed and meets expected result with evidence.
- `WARN` — works but with known caveat or residual risk.
- `FAIL` — regression/product defect.
- `BLOCKED` — missing credential/tool/environment.
- `DEFERRED` — intentionally not run because destructive/high-load/manual approval required.

## Scope

### In scope

1. Docker/runtime health after incident recovery.
2. Final images/containers produced by Phase 5.5.
3. Database migration state `041_module_registry`.
4. Redis AOF recovery stability.
5. Backend Playwright/PDF-render dependency sanity.
6. Public/local frontend availability.
7. Login pages and `← Về trang chủ` exit link.
8. Keycloak SSO CTA and callback path.
9. `/api/me/modules` module endpoint and sidebar module visibility.
10. Guard default-off behavior for supply-chain materials/process routes.
11. Representative auth/RBAC/tenant negative checks.
12. Existing focused unit/integration/Playwright suites that were touched since yesterday.

### Out of scope unless explicitly approved

1. Destructive chaos drills: stopping Postgres/Qdrant/Keycloak/Redis under load.
2. Docker daemon/cache/system pruning.
3. Pushing commits/images or remote deploy.
4. Enabling `MODULE_GUARDS_ENABLED=true` broadly.
5. Real customer-production onboarding sign-off.
6. High public load against `aminra.org` beyond light smoke.

## Evidence directory

Create one new evidence folder for the run:

```bash
OUT=docs/qa/20260917-post-phase55-confidence-sweep
mkdir -p "$OUT"/evidence/{terminal,raw,screenshots,network,console}
```

Required outputs:

```text
docs/qa/20260917-post-phase55-confidence-sweep/
  report.md
  status.tsv
  evidence/
```

`status.tsv` schema:

```text
domain	status	step	evidence	note
```

## P0 Gate 0 — preflight and safety snapshot

**Objective:** Freeze the starting state before testing.

Steps:

1. Record date, HEAD, branch, dirty tree.
2. Record Docker compose state.
3. Record image IDs for backend/frontend/base.
4. Record DB migration current.
5. Confirm no existing background build/deploy process is running.

Commands:

```bash
date
cd /home/user/Documents/aminra-docker-system
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD
git status --short
docker compose ps
docker compose images aminra-backend aminra-frontend
docker image ls --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}} {{.Size}}' | grep -E 'aminra-backend-base|aminra-docker-system-aminra-(backend|frontend)' || true
docker compose exec -T aminra-backend alembic current
ps -ef | grep -E 'docker build|modularization-phase-gate|playwright test|pytest' | grep -v grep || true
```

Pass criteria:

- Backend/frontend/postgres/qdrant/redis/keycloak are running and healthy.
- DB current is `041_module_registry (head)`.
- No unexpected long-running build/deploy process.
- Dirty tree is recorded, not ignored.

## P0 Gate 1 — runtime health and stability

**Objective:** Prove the system is not merely up once, but stable after incident recovery.

Steps:

1. Backend `/health` local.
2. Frontend local root.
3. Public root.
4. Business/provider login HTTP.
5. Redis `PONG`.
6. Keycloak readiness/admin/discovery.
7. 12-sample stability loop, 5 seconds apart.
8. Recent fatal log scan.

Commands:

```bash
curl -fsS http://127.0.0.1:8100/health | tee "$OUT/evidence/raw/backend-health.json"
curl -fsSI http://127.0.0.1:3100 | tee "$OUT/evidence/raw/frontend-local-head.txt"
curl -fsSI https://aminra.org | tee "$OUT/evidence/raw/public-root-head.txt"
curl -fsSI https://aminra.org/business/login | tee "$OUT/evidence/raw/public-business-login-head.txt"
curl -fsSI https://aminra.org/provider/login | tee "$OUT/evidence/raw/public-provider-login-head.txt"
docker compose exec -T redis redis-cli ping | tee "$OUT/evidence/raw/redis-ping.txt"
curl -fsSI http://127.0.0.1:8180/realms/aminra/.well-known/openid-configuration | tee "$OUT/evidence/raw/keycloak-discovery-head.txt"
```

Stability loop:

```bash
for i in $(seq 1 12); do
  echo "sample $i"
  docker compose ps aminra-backend aminra-frontend postgres-db qdrant-db redis keycloak
  curl -fsS -o /dev/null http://127.0.0.1:8100/health
  curl -fsS -o /dev/null http://127.0.0.1:3100
  curl -fsS -o /dev/null https://aminra.org
  docker compose exec -T redis redis-cli ping >/dev/null
  sleep 5
done | tee "$OUT/evidence/terminal/runtime-stability-12-samples.txt"
```

Fatal log scan:

```bash
docker compose logs --since=30m aminra-backend aminra-frontend keycloak redis \
  | tee "$OUT/evidence/terminal/recent-logs.txt" \
  | grep -Ei 'traceback|uncaught|fatal|panic|segmentation fault|bad file format|read-only file system|database is locked' || true
```

Pass criteria:

- 12/12 samples pass.
- No fatal/storage/AOF/read-only patterns after the run starts.
- Redis has no AOF bad-format recurrence.

## P0 Gate 2 — Phase 5.5 release pipeline reproducibility

**Objective:** Verify the newly hardened script can still run without mutating more than intended.

Sequence:

1. `verify-only` first.
2. `build-only` second only if verify passes.
3. `immutable-deploy` only after build-only passes and runtime is healthy.

Commands:

```bash
MODE=verify-only scripts/automation/modularization-phase-gate.sh
BUILD_TIMEOUT_SECONDS=2400 BUILD_RETRIES=2 REBUILD_BACKEND_BASE=auto scripts/automation/modularization-phase-gate.sh build-only
BUILD_TIMEOUT_SECONDS=2400 BUILD_RETRIES=2 REBUILD_BACKEND_BASE=auto STABILITY_SAMPLES=6 STABILITY_INTERVAL_SECONDS=5 scripts/automation/modularization-phase-gate.sh immutable-deploy
```

Pass criteria:

- Focused backend tests: `18 passed`.
- FE module/admin tests: `6 passed`.
- FE lint PASS.
- Python compile/diff/Alembic gates PASS.
- Fresh containers healthy after deploy.
- Local/public smoke and 6/6 stability pass.

Stop criteria:

- Any Docker/containerd read-only error.
- Any backend Playwright/browser segfault.
- Any compose service fails to become healthy within the script’s wait window.
- Any fatal log pattern after deploy.

## P0 Gate 3 — backend Playwright/PDF-render dependency sanity

**Objective:** Specifically guard against the Playwright 1.63 segfault class that triggered the last failure.

Commands:

```bash
docker compose exec -T aminra-backend sh -lc 'python - <<"PY"
import asyncio, importlib.metadata as md
print("playwright", md.version("playwright"))
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        await page.set_content("<html><body><h1>AMINRA QA</h1></body></html>")
        title = await page.locator("h1").inner_text()
        print("browser_text", title)
        await b.close()
asyncio.run(main())
PY'
```

Pass criteria:

- Version reports `playwright 1.56.0`.
- Browser launches and extracts text.
- No segfault/fatal log.

## P0 Gate 4 — auth/login/browser session smoke

**Objective:** Prove yesterday’s login UX/auth-domain changes still work in a real browser, not curl only.

Test cases:

1. Anonymous `/business/login` renders.
2. Anonymous `/provider/login` renders.
3. `← Về trang chủ` visible on both login pages.
4. Clicking exit link navigates to landing/home.
5. Keycloak SSO CTA visible when enabled.
6. Clicking CTA redirects to `https://auth.aminra.org/realms/aminra/...client_id=aminra-frontend...`.
7. Browser console has no page-crashing errors.

Commands:

```bash
cd frontend/aminra-web
PW_BASE_URL=https://aminra.org npx playwright test \
  e2e/08-login-ui.spec.ts \
  e2e/keycloak/02-login-ui-flow.spec.ts \
  --project=desktop-chromium
```

Pass criteria:

- Existing focused login/OIDC tests pass, SMTP-dependent cases may be skipped only if explicitly marked.
- Screenshots/video retained in Playwright output.
- No redirect to legacy `auth.silvergem.org`.

## P0 Gate 5 — auth/RBAC identity matrix

**Objective:** Confirm real-role identity mapping did not regress through Keycloak/domain/deploy changes.

Required roles if credentials are available from gitignored QA env:

- platform admin
- business owner
- provider/CB owner
- auditor/sub-role
- disabled account negative if fixture exists

Checks per role:

1. IdP token acquisition.
2. `/api/auth/me` or `/auth/me` effective role/status/tenant.
3. Representative allowed route returns `200`.
4. Representative forbidden route returns `401/403/404`, not `200`.
5. Logout/session cleanup for at least admin and business.

Suggested existing command candidates:

```bash
# Source only gitignored QA credentials; never print them.
set -a
[ -f .env ] && . ./.env
[ -f .qa/aminra-demo-credentials.env ] && . ./.qa/aminra-demo-credentials.env
set +a

# Use existing AMINRA auth/RBAC smoke scripts/tests if present.
find scripts tests frontend/aminra-web/e2e -maxdepth 4 -iname '*auth*' -o -iname '*login*' -o -iname '*role*'
```

Pass criteria:

- No role gets access to a forbidden admin/provider/business-owner surface.
- Admin retains platform authority from Keycloak realm roles.
- No stale profile/account-switch mismatch.

If credentials are missing:

- Mark `BLOCKED`, not PASS.
- Still run anonymous route-boundary and source-level tests.

## P0 Gate 6 — modular monolith module registry and guard regression

**Objective:** Prove Phase 0-5.5 modularization did not break current default behavior.

Commands:

```bash
docker compose exec -T aminra-backend pytest \
  tests/test_module_registry_migration.py \
  tests/test_module_service.py \
  tests/test_module_route_contract.py \
  tests/test_module_guard.py \
  -q

cd frontend/aminra-web
npm run test -- sidebar-module-navigation-contract.test.tsx sidebar-admin-navigation-contract.test.tsx
```

Runtime checks:

- Unauthenticated `/api/me/modules` returns `401`.
- Authenticated business account sees expected modules if credentials available.
- `MODULE_GUARDS_ENABLED=false` keeps existing demo flow fail-open.
- Guard unit tests prove `MODULE_GUARDS_ENABLED=true` denies disabled/missing modules.

Pass criteria:

- Backend focused suite: `18 passed` or newer equivalent with no failures.
- FE focused suite: `6 passed` or newer equivalent with no failures.
- No broad guard enablement in runtime env.

## P1 Gate 7 — core business flow smoke

**Objective:** Catch obvious regressions outside auth/modularization.

Run focused suites/smokes covering:

1. Supply-chain materials/process/batches API writes via shared FE API client.
2. Public trace sealed-snapshot positive/negative fixture if deterministic fixture exists.
3. Admin password reset/session revocation focused tests.
4. Demo account login smoke script.
5. Pre-demo/runtime smoke script.

Suggested commands to discover exact existing scripts first:

```bash
find scripts/qa backend/tests frontend/aminra-web/e2e -maxdepth 4 \
  \( -iname '*supply*' -o -iname '*trace*' -o -iname '*admin*' -o -iname '*demo*' -o -iname '*smoke*' \) \
  | sort
```

Then run only high-signal, non-destructive candidates.

Pass criteria:

- Write flows use QA/demo data only.
- Cleanup is verified for any created QA users/records.
- No false-success UI behavior on non-2xx responses.

## P1 Gate 8 — tenant/IDOR/security boundary smoke

**Objective:** Prove no obvious cross-tenant or anonymous access regression.

Prioritize existing focused tests for:

- anonymous protected route boundary
- tenant A/B read/write negatives
- supply-chain photos/certificates/materials/batches
- admin lower-role denial
- public trace invalid/injection IDs

Pass criteria:

- Forbidden routes do not return `200`.
- Invalid public trace IDs return safe `404`/not-found.
- No private fields in public trace response.

## P1 Gate 9 — frontend browser health matrix

**Objective:** Browser runtime catches what curl cannot.

Minimum:

```bash
cd frontend/aminra-web
npm run lint -- --quiet
npm run build
PW_BASE_URL=https://aminra.org npx playwright test --project=desktop-chromium
```

If time allows:

```bash
PW_BASE_URL=https://aminra.org npx playwright test --project=desktop-firefox
PW_BASE_URL=https://aminra.org npx playwright test --project=desktop-webkit
```

Pass criteria:

- Chromium matrix has no failed core auth/business/admin tests.
- Firefox/WebKit failures are classified, not ignored.
- Skips are counted and categorized: SMTP-deferred, fixture/env, mobile/tablet project-gated, stale legacy.

## P2 Gate 10 — lightweight performance/public edge sanity

**Objective:** Ensure public site did not become obviously slow/unavailable after deploy without running destructive load.

Commands:

```bash
for url in https://aminra.org https://aminra.org/business/login https://aminra.org/provider/login; do
  echo "$url"
  for i in $(seq 1 10); do
    curl -fsS -o /dev/null -w 'code=%{http_code} total=%{time_total} connect=%{time_connect} ttfb=%{time_starttransfer}\n' "$url"
  done
done | tee "$OUT/evidence/terminal/public-light-perf.txt"
```

Pass criteria:

- No 5xx.
- No severe outlier pattern across 10 requests/page.
- This does not replace the known public-edge SLO gate for production GO.

## P2 Gate 11 — docs/evidence consistency

**Objective:** Prevent false confidence from stale docs.

Checks:

1. Verify code repo status.
2. Verify all-docs dirty status is understood.
3. Verify final report matches actual evidence.
4. Ensure brain is not updated to GO/production-ready unless gates justify it.

Commands:

```bash
git status --short
cd /home/user/Documents/all-docs && git status --short
```

Pass criteria:

- Any dirty/untracked docs are listed in final report.
- No production GO claim from local-only evidence.

## Final report template

`report.md` must contain:

```markdown
# AMINRA Post-Phase 5.5 Confidence Sweep Report

## Verdict
- Runtime recovery:
- Release pipeline:
- Auth/session:
- Modularization:
- Core business flows:
- Security boundaries:
- Public edge/perf:
- Overall:

## Environment
- Date:
- Repo:
- HEAD:
- Branch:
- Dirty tree:
- URLs:

## Executed gates
[Summarize status.tsv]

## Defects / blockers
[P0/P1 first]

## Evidence index
[Link key logs/screenshots]

## Skips / deferred
[Do not hide missing coverage]

## Recommendation
- Safe for local/demo maintenance?
- Safe for supervised pilot?
- Safe for production/customer onboarding?
```

## Recommended execution order

1. P0 Gate 0 — preflight snapshot.
2. P0 Gate 1 — runtime/stability.
3. P0 Gate 3 — backend Playwright sanity.
4. P0 Gate 6 — modularization focused suites.
5. P0 Gate 4 — login/browser smoke.
6. P0 Gate 5 — auth/RBAC if credentials available.
7. P1 Gate 7 — core business smokes.
8. P1 Gate 8 — tenant/security boundaries.
9. P1 Gate 9 — frontend browser matrix.
10. P2 Gate 10 — light public perf.
11. P0 Gate 2 — rerun release pipeline only if we want to prove reproducibility again after the above, because it mutates/recreates containers.
12. P2 Gate 11 — docs/evidence consistency.

## Stop-the-line conditions

Stop and triage before continuing if any of these appear:

- Docker/containerd read-only or metadata write error.
- Redis AOF bad-format recurrence.
- Backend Playwright segfault or browser launch failure.
- Backend/frontend fails health after recreate.
- Keycloak issuer/domain regresses to `auth.silvergem.org`.
- Any forbidden lower-role/admin route returns `200`.
- Any public trace/private endpoint leaks tenant/internal/private fields.
- Browser auth flow shows stale account/profile after logout/account switch.

## Expected final confidence if all P0/P1 pass

If all P0/P1 gates pass, the honest verdict should be:

```text
Local/dev runtime and sandbox demo maintenance: PASS
Supervised pilot: PARTIAL unless customer-specific UAT and existing pre-pilot blockers are closed
Production/customer onboarding: NOT PASS; remains gated by separate production-readiness backlog
```
