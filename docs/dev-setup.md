# Developer Setup — AMINRA

Last reviewed: 2026-04-29 · Phase 0 baseline.

## 0. Prerequisites

- Docker + Docker Compose v2 (`docker compose version`)
- Git ≥ 2.30
- Python 3.11+ (for pre-commit; venv-based, no system pollute)
- Node 20+ (for frontend dev outside container)
- 16 GB RAM recommended (Qdrant + Postgres + 2 Node + 1 Python in stack)

## 1. Clone + bootstrap

```bash
git clone https://github.com/assasin579/aminra-docker-system.git
cd aminra-docker-system
```

### Vault — first-time bring-up
```bash
docker compose -f vault/docker-compose.vault.yml up -d
bash vault/scripts/init-vault.sh           # initialise + unseal + seed secrets
```

Persists `vault/approle/init-keys.json` — **do not commit**.

### Application stack
```bash
docker compose up -d                                  # production-like
docker compose --profile dev up -d aminra-frontend-dev  # frontend hot reload on :3100
```

Backend on `http://localhost:8100`, frontend on `http://localhost:3100`, Qdrant on `:6433`.

## 2. Pre-commit hooks (mandatory)

```bash
python3 -m venv ~/.local/venv-precommit
~/.local/venv-precommit/bin/pip install pre-commit
ln -sf ~/.local/venv-precommit/bin/pre-commit ~/.local/bin/pre-commit
export PATH="$HOME/.local/bin:$PATH"           # add to ~/.bashrc

cd aminra-docker-system
pre-commit install --install-hooks             # one-time hook install + env download
```

Sanity check:
```bash
pre-commit run --all-files                     # ~25s on cold cache
```

What runs on `git commit`:
- File hygiene: trailing whitespace, EOF, yaml/json/toml syntax, large-file guard, secret-scan (gitleaks)
- Backend: ruff lint + format (excludes `tests/`, `alembic/`)
- Frontend: prettier (excludes `package-lock.json`, `.next/`)
- Commit msg: conventional-commits format check

What runs **manually only** (Phase 0 soft gates):
- mypy-fast: `pre-commit run --hook-stage manual mypy-fast` — see backlog at `backend/ruff.toml`

## 3. Run tests

### Backend (pytest, in-container)
```bash
cd backend
./run_tests.sh                                 # all
./run_tests.sh tests/test_auth.py              # one file
./run_tests.sh tests/test_auth.py -k login     # by name
./run_tests.sh --cov                           # coverage, fail < 80%
```

### Frontend unit + component (Vitest)
```bash
cd frontend/aminra-web
npm test
npm run test:watch
npm run test:cov
```

### Frontend e2e (Playwright, multi-browser)
```bash
npm run test:e2e          # desktop chromium
npm run test:e2e:mobile   # Pixel 5
npm run test:e2e:all      # full matrix
npm run test:e2e:ui       # debug
npm run test:e2e:report   # last HTML report
```

### Smoke (curl-based, ~30s)
```bash
bash /tmp/aminra_smoke_test_v2.sh
```

## 4. Database migrations

```bash
./scripts/db-migrate.sh current               # show DB rev
./scripts/db-migrate.sh history
./scripts/db-migrate.sh upgrade               # to head
./scripts/db-migrate.sh upgrade <rev>
./scripts/db-migrate.sh downgrade -1
./scripts/db-migrate.sh new "describe migration"
./scripts/db-migrate.sh stamp                 # mark current as head (existing DB)
```

Conventions: additive-only migrations; `def downgrade()` mandatory; review SQL diff before applying. Schema impact analysis required for every new feature (`docs/features/<feature>/schema.md`).

## 5. Secret rotation

```bash
bash vault/scripts/rotate-secrets.sh api-keys      # OpenRouter + DeepSeek
bash vault/scripts/rotate-secrets.sh database      # PostgreSQL pwd
bash vault/scripts/rotate-secrets.sh auth          # JWT + admin
bash vault/scripts/rotate-secrets.sh web-push      # VAPID keypair
bash vault/scripts/rotate-secrets.sh all
```

Runbook for VAPID specifically: `docs/runbooks/vapid-rotation.md`.

## 6. Backup + restore

```bash
./scripts/backup.sh                           # full
./scripts/backup.sh --db-only
./scripts/backup.sh --qdrant-only
./scripts/restore.sh <backup-dir>
./scripts/restore.sh --yes <backup-dir>       # non-interactive
```

Cron config: `scripts/backup-cron.sh`. Retention: 7 days (auto-prune).

## 7. Branching + PR workflow

- Feature branches: `feat/<short-slug>` (e.g. `feat/ihc-meeting-records`)
- Fix branches: `fix/<short-slug>`
- PR title MUST follow Conventional Commits: `feat(scope): subject`
- Allowed types: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `security`, `revert`
- Per-feature workflow: see `methodology_engineering_bar.md` (Stage 1–8 framework)

### Required per-feature deliverables
1. `docs/features/<feature>/spec.md` — business rule, state machine, multi-tenant boundary
2. `docs/features/<feature>/threat-model.md` — STRIDE table
3. `docs/features/<feature>/schema.md` — schema design + migration UP/DOWN
4. `docs/features/<feature>/test-plan.md` — 50 cases × 6 types
5. `docs/features/<feature>/test-report.md` — execution + coverage
6. `docs/features/<feature>/runbook.md` — rollback + ops

### CI gates (must pass)
- `.github/workflows/ci.yml` — lint, smoke
- `.github/workflows/test.yml` — full pytest + vitest + Playwright
- `.github/workflows/security-scan.yml` — bandit, pip-audit, npm audit, gitleaks, semgrep, trivy
- All 6 deliverables above present

## 8. Phase 0 baseline + open backlog

- `docs/system-evaluation-2026-04-29.md` — system inventory + Phase 0 plan
- `docs/security/bandit-triage-2026-04-29.md` — backend SAST baseline
- `docs/security/branch-protection-2026-04-29.md` — branch protection gap + recommended settings (NOT yet applied)
- Tech debt:
  - 4 real F821 ruff bugs (audit_router.py:1462, submission_router.py:1095/1096, anchor.py:39)
  - 10 mypy errors (data_export, anchor_bitcoin, router, submission, certificate, audit, anchor)
  - Missing observability instrumentation (Prometheus, structured logs, frontend Sentry) — Phase 0 Day 4
  - No feature flag system — Phase 0 Day 6

## 9. Useful URLs (dev)

- Backend: http://localhost:8100/health
- Frontend (dev hot-reload): http://localhost:3100
- Frontend (prod build, port 3000 if running): http://localhost:3000
- Qdrant: http://localhost:6433/dashboard
- Postgres: `docker exec -it aminra-docker-system-postgres-db-1 psql -U aminra_user -d aminra`
- Vault UI: http://localhost:8200/ui (token from `vault/approle/init-keys.json`)
- Grafana: http://localhost:3200
- Prometheus: http://localhost:9090
- Cloudflare tunnel preview: https://dev-web.silvergem.org

## 10. Common issues

| Symptom | Fix |
|---|---|
| `pre-commit: command not found` | `export PATH="$HOME/.local/bin:$PATH"` (add to `~/.bashrc`) |
| Hook hangs on first install | Network — let it finish (~5min total cold install) |
| `vault.read … permission denied` in vault-agent logs | Re-run `vault policy write aminra-backend vault/policies/aminra-backend.hcl`; restart `vault-agent` |
| Backend SQL injection bandit warnings | Triage in `docs/security/bandit-triage-2026-04-29.md`; new dynamic SQL must follow whitelist + parameterized pattern |
| Next.js dev container has stale code after volume edit | `docker restart aminra-docker-system-aminra-frontend-dev-1` (Linux inotify quirk) |
| Frontend TS error after Next bump | Clear: `rm -rf frontend/aminra-web/.next frontend/aminra-web/.tsbuildinfo` |
| Rebuild backend after code change (image-based, not volume) | `docker compose build aminra-backend && docker compose up -d aminra-backend` |
