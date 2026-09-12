# AMINRA improvement follow-up — public trace load split + admin token helper

Generated: 2026-09-12

## Verdict

- `local_backend`: PASS — 200 requests / 50 concurrency / p95 `575.9ms` < `800ms`.
- `local_frontend_proxy`: PASS — 200 requests / 50 concurrency / p95 `670.4ms` < `800ms`.
- `public_frontend_proxy`: FAIL — 200 requests / 50 concurrency / p95 `2538.5ms` > `800ms`, 0 HTTP errors.
- Classification: `public_proxy_tunnel_or_edge_slo`; local app/backend path is not the bottleneck on this run.

## Changes

1. `scripts/qa/run-customer-ready-full-system-qa.sh`
   - Replaced the single public-only public-trace load probe with split profiles:
     - local backend: `127.0.0.1:8100`
     - local frontend proxy: `127.0.0.1:3100`
     - public frontend proxy: `dev-web.silvergem.org`
   - Captures cache/proxy headers including `x-aminra-proxy-cache` and `cf-cache-status`.
   - Classifies failures as either `app_or_local_proxy_slo` or `public_proxy_tunnel_or_edge_slo`.
   - Handles curl timeouts as classified results instead of crashing the diagnostic script mid-run.

2. `frontend/aminra-web/e2e/helpers/admin-token.ts`
   - Removed stale `/api/auth/login` dependency from the platform-admin token helper.
   - Now obtains a real Keycloak password-grant token from `/realms/{realm}/protocol/openid-connect/token` using `TEST_ADMIN_EMAIL` + `TEST_ADMIN_PASSWORD`, without printing secrets.

## Evidence

- Split load evidence: `docs/qa/2026-09-12-improvement-follow-up-load-split/evidence/terminal/002-public-trace-split-load-profile-timeout-classified.txt`
- Runner syntax check: `bash -n scripts/qa/run-customer-ready-full-system-qa.sh` PASS.
- Admin helper focused Playwright: `npx playwright test e2e/20-admin-unified-auth.spec.ts --project=desktop-chromium` => `1 passed, 1 skipped`.

## Interpretation

This does **not** make AMINRA production/customer GO. It narrows the red load gate: local backend and local frontend proxy are inside the 800ms target, while the public path remains red with Cloudflare reporting `cf-cache-status: DYNAMIC`. The next real fix is at the public edge/tunnel/cache rule or hosting layer, not another backend optimization pass unless new evidence contradicts this split.
