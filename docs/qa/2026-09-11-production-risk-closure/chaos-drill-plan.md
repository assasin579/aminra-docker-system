# AMINRA Chaos Drill Plan — approval required before execution

Date: 2026-09-11
Scope: Non-production sandbox only. Destructive/disruptive drills are NOT executed until founder explicitly approves blast radius.

## Verdict rule

A drill is PASS only if:

1. The intended dependency failure is visible and fails closed.
2. Recovery brings the service back without data corruption.
3. User-facing/API errors do not leak secrets, SQL traces, stack traces, or cross-tenant data.
4. Logs clearly distinguish expected drill failures from unexpected runtime errors.
5. Evidence captures pre-state, failure-state, recovery-state, and log scan.

## Preconditions

- Confirm environment is sandbox, not customer production.
- Capture `docker compose ps` and `/health` before drills.
- Create DB backup if any drill touches Postgres or write paths.
- Use deterministic public trace fixture `73695b8a-3c10-570b-8bba-92c12da9b56e` for read-only trace probes.
- Keep SMTP out of scope unless separately approved.

## Drill 1 — Redis outage / ARQ queue unavailable

Blast radius: background jobs and any Redis-backed queues/cache.

Steps:

1. Pre-state: `docker compose ps redis arq-worker aminra-backend`; backend `/health`; ARQ logs baseline.
2. Stop Redis: `docker compose stop redis`.
3. Probe:
   - backend `/health`;
   - public trace API;
   - ARQ worker logs for bounded queue connection errors.
4. Recover: `docker compose start redis`; wait for `redis-cli ping` = `PONG`.
5. Re-run ARQ dry-run job and scan logs.

Expected:

- Public read surfaces remain available if Redis is not required for that path.
- Background job failure is bounded and recovers after Redis returns.
- No uncaught tracebacks in user-facing API responses.

## Drill 2 — Qdrant outage / vector dependency unavailable

Blast radius: AI/vector search features and backend health qdrant signal.

Steps:

1. Pre-state: Qdrant `/readyz`, backend `/health`.
2. Stop Qdrant: `docker compose stop qdrant-db`.
3. Probe:
   - backend `/health` should report degraded/disconnected qdrant, not crash;
   - public trace API should remain available if it does not depend on vector search;
   - any AI/vector endpoint should fail closed with structured error.
4. Recover: `docker compose start qdrant-db`; wait for `/readyz`.
5. Re-probe backend `/health` and public trace.

Expected:

- Qdrant outage does not break public trace/read-only compliance pages.
- Qdrant-dependent features expose safe degraded behavior.

## Drill 3 — Keycloak outage / auth unavailable

Blast radius: login, token refresh, protected API requests.

Steps:

1. Pre-state: Keycloak discovery `HTTP 200`; existing role smoke baseline.
2. Stop Keycloak: `docker compose stop keycloak`.
3. Probe:
   - anonymous public trace remains available;
   - new login/token request fails clearly;
   - protected API with no/invalid token remains `401/403` fail-closed;
   - existing token behavior is classified based on JWT validation/cache rules.
4. Recover: `docker compose start keycloak`; wait for health/discovery.
5. Re-run business/provider/auditor token smoke and demo spine.

Expected:

- Anonymous public trace unaffected.
- Protected paths do not accidentally open during IdP outage.
- Recovery restores auth without manual DB surgery.

## Drill 4 — Backend recreate during traffic

Blast radius: API availability during deployment.

Steps:

1. Run low-rate read probe loop against public trace and `/health`.
2. `docker compose up -d --no-deps --force-recreate aminra-backend`.
3. Continue probe; capture failures and recovery time.
4. Scan backend logs after healthy.

Expected:

- Brief 5xx/connection resets may occur in sandbox unless load balancer has zero-downtime config.
- Recovery time and failure count are bounded and documented.

## Approval required

Do not execute these drills automatically. Ask founder to approve:

- which drill(s);
- acceptable downtime window;
- whether DB backup is required immediately before run;
- whether public `dev-web.silvergem.org` traffic can be disrupted.
