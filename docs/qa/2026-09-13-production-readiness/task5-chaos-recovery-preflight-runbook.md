# Task 5 — Chaos/recovery drill preflight + approval runbook

Date: 2026-09-13 16:38 -04:00
Scope: `/home/user/Documents/aminra-docker-system`
Verdict: **PREFLIGHT PASS / DRILL EXECUTION BLOCKED PENDING EXPLICIT APPROVAL**

## Safety boundary

No destructive or disruptive chaos was executed. I did **not** stop/restart services, kill containers, drop/recreate databases, restore over current data, run migration downgrade, or modify production-like application data.

Execution remains blocked until an owner/founder approves: exact drill(s), sandbox target, maintenance window, acceptable downtime, backup requirement, and rollback owner.

## Inventory found

### Backup / restore scripts

- `scripts/backup.sh`
  - PostgreSQL custom-format dump via `pg_dump -Fc` from `aminra-docker-system-postgres-db-1`.
  - Optional scopes: `--db-only`, `--qdrant-only`, `--volumes-only`.
  - Also creates Qdrant snapshot and Docker volume archives by default.
- `scripts/restore.sh`
  - **Destructive**: stops backend/arq, terminates DB sessions, `dropdb --if-exists`, `createdb`, then `pg_restore`.
  - Optional scopes: `--db-only`, `--qdrant-only`, `--volumes-only`; `--yes` bypasses prompt.
  - Also can overwrite Qdrant collection and clear/untar Docker volumes.
- `scripts/backup-cron.sh`
  - Runs full backup and prunes older backup directories beyond `KEEP_DAYS=7`.
  - Uses `find ... rm -rf` for retention, so should be reviewed before enabling in production/pilot.

### Recovery / chaos docs and evidence

- `docs/qa/2026-09-11-production-risk-closure/chaos-drill-plan.md`
  - Existing approval-gated drills: Redis/ARQ outage, Qdrant outage, Keycloak outage, backend recreate under traffic.
- `docs/plans/2026-09-11-aminra-production-risk-closure-plan.md`
  - Phase 5 requirements and reminder not to run destructive chaos or migration rollback without backup/restore confirmation and founder approval.
- Existing recovery evidence:
  - `docs/qa/2026-09-13-production-readiness/evidence/recovery/001-db-backup-smoke.txt`
  - `docs/qa/2026-09-13-production-readiness/evidence/recovery/002-restore-dryrun-list.txt`
- Existing deferred chaos evidence:
  - `docs/qa/2026-09-12-customer-ready-full-system/evidence/terminal/036-09-load-chaos-deploy-chaos-drills-deferred.txt`
- Historical executed chaos evidence exists under:
  - `docs/qa/2026-09-11-production-risk-closure/evidence/terminal/82..88-*`

### Runtime/deploy gates relevant to recovery

- `scripts/qa/runtime-smoke.sh` is read-only and checks Docker state, backend health, frontend pages, public hostname, Keycloak discovery, landing markers, and recent logs.
- `scripts/deploy-from-registry.sh` has a deploy safety gate:
  - default: blocked unless strategy selected;
  - `DEPLOY_STRATEGY=maintenance DEPLOY_WINDOW_APPROVED=true DRY_RUN=true` passes dry-run;
  - `DEPLOY_STRATEGY=rolling` is explicitly unsupported by current Docker Compose path.

## Non-destructive checks safely run now

Evidence saved under `docs/qa/2026-09-13-production-readiness/evidence/task5/`.

- `001-nondestructive-preflight.txt`
  - `bash -n scripts/backup.sh`: PASS
  - `bash -n scripts/restore.sh`: PASS
  - `bash -n scripts/backup-cron.sh`: PASS
  - `bash -n scripts/qa/runtime-smoke.sh`: PASS
  - `bash -n scripts/deploy-from-registry.sh`: PASS
  - `scripts/restore.sh` with no args: expected nonzero usage gate PASS
  - `docker compose config --quiet`: PASS
  - Host `pg_restore` was missing (`pg_restore: command not found`), so host-side dump inspection must use containerized Postgres tools or install client utilities.
- `002-readonly-runtime-smoke.txt`
  - `LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh`: PASS=12 WARN=0 FAIL=0
  - Backend `/health`: database=connected, qdrant=connected
  - Local frontend and public `https://dev-web.silvergem.org`: HTTP 200
  - Keycloak OIDC discovery: HTTP 200
  - Fresh log scan: no high-signal errors in last 10 minutes
- `003-pg-restore-list-container.txt`
  - Existing dump `backups/qa-production-readiness-20260913_102227-db-only/postgres_aminra.dump` inspected with `pg_restore --list` inside the Postgres container: PASS

## Prerequisites before any approved drill

1. Confirm environment is **non-production sandbox** and that `dev-web.silvergem.org` disruption is acceptable.
2. Assign roles:
   - Drill commander: approves each step and abort decisions.
   - App operator: runs Docker/application commands.
   - DB owner: verifies backup/restore readiness and owns rollback.
   - Observer/scribe: captures timestamps, outputs, screenshots/log excerpts.
3. Freeze unrelated deployments and data migrations during the drill.
4. Capture baseline:
   ```bash
   cd /home/user/Documents/aminra-docker-system
   git status --short --branch
   docker compose ps
   curl -fsS http://localhost:8100/health
   LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh
   ```
5. Create or designate backup immediately before drills if any write path, DB-impacting operation, or restore validation is in scope:
   ```bash
   cd /home/user/Documents/aminra-docker-system
   scripts/backup.sh --db-only backups/pre-chaos-$(date +%Y%m%d_%H%M%S)-db-only
   docker exec aminra-docker-system-postgres-db-1 pg_restore --list /tmp/<copied-dump> | head -40
   ```
6. Define abort criteria:
   - Any cross-tenant leak.
   - Auth path opens unexpectedly during Keycloak outage.
   - Public API returns stack traces/secrets/SQL traces.
   - Recovery exceeds approved downtime.
   - Backup cannot be inspected or restore plan is ambiguous.
7. Confirm rollback commands are ready but not run unless needed.

## Blast radius and rollback map

- Redis/ARQ outage
  - Blast radius: background jobs, queue/cache-dependent writes, worker logs.
  - Expected safe behavior: public DB-backed reads remain available; queue failures are bounded and recover after Redis returns.
  - Rollback/recovery: `docker compose start redis`; verify `redis-cli ping` returns `PONG`; rerun runtime smoke and inspect arq/backend logs.
- Qdrant outage
  - Blast radius: vector/RAG/search features and qdrant health signal.
  - Expected safe behavior: core public trace/read-only compliance pages remain available if not vector-dependent; qdrant-dependent paths fail closed.
  - Rollback/recovery: `docker compose start qdrant-db`; wait for `/readyz`; rerun backend `/health` and runtime smoke.
- Keycloak outage
  - Blast radius: login, token refresh, protected API, admin/business/provider/auditor pages.
  - Expected safe behavior: new login fails clearly; protected paths remain 401/403; anonymous public trace remains available.
  - Rollback/recovery: `docker compose start keycloak`; wait for discovery; rerun token/role smoke.
- Backend recreate during traffic
  - Blast radius: API availability during single-backend Docker Compose recreate.
  - Expected safe behavior: bounded connection resets/5xx only; recovery time documented.
  - Rollback/recovery: `docker compose up -d aminra-backend`; health-gated smoke; use deploy/runbook rollback if image/tag changed.
- Full restore
  - Blast radius: **high/destructive**: stops services, drops/recreates DB, may overwrite Qdrant/volumes.
  - Status: blocked except in disposable clone or explicit maintenance window.

## Ready-to-approve staged drill sequence

### Stage 0 — approval gate

Required approval statement:

```text
I approve Task 5 chaos/recovery drill on the non-production sandbox for: [Redis/Qdrant/Keycloak/backend recreate/restore clone]. Approved window: [start/end]. Acceptable disruption: [N minutes]. Backup requirement: [yes/no]. Rollback owner: [name]. Public dev-web disruption: [allowed/not allowed].
```

No drill commands below should be run before this gate is satisfied.

### Stage 1 — baseline and backup gate

```bash
cd /home/user/Documents/aminra-docker-system
mkdir -p docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence

date --iso-8601=seconds | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/000-start.txt
git status --short --branch | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/001-git-status.txt
docker compose ps | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/002-compose-ps-before.txt
curl -fsS http://localhost:8100/health | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/003-health-before.json
LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/004-runtime-smoke-before.txt

# If backup required:
scripts/backup.sh --db-only backups/pre-chaos-$(date +%Y%m%d_%H%M%S)-db-only | tee docs/qa/$(date +%Y-%m-%d)-task5-approved/evidence/005-pre-chaos-db-backup.txt
```

Safety gate to continue: baseline smoke has `FAIL=0`; backup completes with `Errors 0` if required.

### Stage 2 — Redis/ARQ drill

```bash
cd /home/user/Documents/aminra-docker-system
docker compose ps redis arq-worker aminra-backend | tee evidence/redis-001-before.txt
curl -fsS http://localhost:8100/health | tee evidence/redis-002-health-before.json

docker compose stop redis | tee evidence/redis-003-stop.txt
curl -sS -o evidence/redis-004-health-during.body -w 'HTTP %{http_code}\n' http://localhost:8100/health | tee evidence/redis-004-health-during.status
docker compose logs --since 5m arq-worker aminra-backend | tee evidence/redis-005-logs-during.txt

docker compose start redis | tee evidence/redis-006-start.txt
docker compose exec -T redis redis-cli ping | tee evidence/redis-007-ping.txt
LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh | tee evidence/redis-008-smoke-after.txt
```

Continue only if recovery smoke has `FAIL=0` and no user-facing secret/trace leakage is observed.

### Stage 3 — Qdrant drill

```bash
cd /home/user/Documents/aminra-docker-system
curl -fsS http://localhost:6433/readyz | tee evidence/qdrant-001-ready-before.txt
curl -fsS http://localhost:8100/health | tee evidence/qdrant-002-health-before.json

docker compose stop qdrant-db | tee evidence/qdrant-003-stop.txt
curl -sS -o evidence/qdrant-004-health-during.body -w 'HTTP %{http_code}\n' http://localhost:8100/health | tee evidence/qdrant-004-health-during.status
docker compose logs --since 5m aminra-backend | tee evidence/qdrant-005-logs-during.txt

docker compose start qdrant-db | tee evidence/qdrant-006-start.txt
curl -fsS http://localhost:6433/readyz | tee evidence/qdrant-007-ready-after.txt
LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh | tee evidence/qdrant-008-smoke-after.txt
```

### Stage 4 — Keycloak drill

```bash
cd /home/user/Documents/aminra-docker-system
curl -fsS https://auth.silvergem.org/realms/aminra/.well-known/openid-configuration | tee evidence/keycloak-001-discovery-before.json

docker compose stop keycloak | tee evidence/keycloak-002-stop.txt
curl -k -sS -o evidence/keycloak-003-discovery-during.body -w 'HTTP %{http_code}\n' https://auth.silvergem.org/realms/aminra/.well-known/openid-configuration | tee evidence/keycloak-003-discovery-during.status
curl -sS -o evidence/keycloak-004-public-during.body -w 'HTTP %{http_code}\n' https://dev-web.silvergem.org | tee evidence/keycloak-004-public-during.status

docker compose start keycloak | tee evidence/keycloak-005-start.txt
curl -fsS https://auth.silvergem.org/realms/aminra/.well-known/openid-configuration | tee evidence/keycloak-006-discovery-after.json
LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh | tee evidence/keycloak-007-smoke-after.txt
```

### Stage 5 — backend recreate under low-rate read traffic

```bash
cd /home/user/Documents/aminra-docker-system
for i in $(seq 1 60); do date --iso-8601=seconds; curl -sS -o /dev/null -w 'health=%{http_code}\n' http://localhost:8100/health; sleep 1; done | tee evidence/backend-recreate-probe-loop.txt &
PROBE_PID=$!

docker compose up -d --no-deps --force-recreate aminra-backend | tee evidence/backend-recreate-command.txt
wait $PROBE_PID || true
LOG_SCAN_MINUTES=10 bash scripts/qa/runtime-smoke.sh | tee evidence/backend-recreate-smoke-after.txt
```

### Stage 6 — post-drill closure

```bash
cd /home/user/Documents/aminra-docker-system
docker compose ps | tee evidence/final-compose-ps.txt
curl -fsS http://localhost:8100/health | tee evidence/final-health.json
LOG_SCAN_MINUTES=30 bash scripts/qa/runtime-smoke.sh | tee evidence/final-runtime-smoke.txt
docker compose logs --since 30m aminra-backend aminra-frontend keycloak arq-worker redis qdrant-db | tee evidence/final-logs.txt
```

Pass criteria:

- Final runtime smoke has `FAIL=0`.
- Database and qdrant report connected in `/health` unless qdrant degradation was intentionally accepted and documented.
- No stack traces/secrets/SQL traces in user-facing responses.
- Protected paths fail closed during auth outage.
- Recovery time is within approved window.

## Blocked pending approval

- `docker compose stop redis/qdrant-db/keycloak`
- `docker compose up -d --force-recreate aminra-backend`
- `scripts/restore.sh` in any mode against the current stack
- DB migration downgrade/upgrade against current sandbox
- Full Qdrant/volume restore
- Any command using `--yes` for restore

## Issues / gaps

- Host lacks `pg_restore`; use Postgres container tooling or install PostgreSQL client tools before relying on host-side restore inspection.
- `scripts/restore.sh` has a prompt by default, but `--yes` can bypass; keep `--yes` restricted to approved windows/disposable clones.
- `scripts/backup-cron.sh` retention uses `rm -rf`; safe only after backup directory scope is confirmed.
- Current Docker Compose deploy/recreate path is not zero-downtime for a single backend; maintenance-window approval is required.
