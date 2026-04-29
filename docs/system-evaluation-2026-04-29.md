# AMINRA System Evaluation — Pre-flight Baseline

**Date:** 2026-04-29
**Purpose:** Baseline trước khi triển khai Tier-1 (6 module Halal MVP) với ngưỡng ≥300 tests/feature.
**Sign-off required:** ✅ before starting Feature #24 Document Version Control.

---

## Executive Summary

AMINRA có **nền tảng kỹ thuật trưởng thành** ở phần lõi: 25 tables, 167 endpoints, 295 backend tests + 134 frontend tests + 37 Playwright specs, 4 GitHub Actions workflows, deployment rollback automated, Prometheus+Loki+Grafana stack, Sentry tracking. Tuy nhiên, **DevSecOps chains bị thủng nhiều mắt xích** — không có pre-commit, không có SAST/secrets scan trong CI, frontend đang ship 5 dependency vulns (2 high), 2 secrets bị lộ trong git history, code có 1 high + 46 medium bandit issues. Observability mature về stack nhưng backend chưa instrumented Prometheus, Sentry sample 10% — không đủ để declare SLO per endpoint.

**Verdict:** ✅ **Đủ điều kiện proceed**, nhưng phải **Phase 0 setup** trước khi Feature #24 — fix 7 critical security findings + add SAST/secrets/dep-audit gates trong CI. Estimate Phase 0: **5–7 working days**.

---

## A. Test Infrastructure Inventory

### Backend (pytest 8+, asyncio auto-mode)
- **295 test functions** across 36 files (~5,051 LoC)
- Pattern: `*_unit.py` (15 files), `*_integration.py` (10 files), other (11)
- Fixtures: 3 session-scoped (`client`, `admin_credentials`, `admin_token`) — minimal
- Coverage: pytest-cov, fail-under 80%, không có baseline artifact đã commit
- Mocking: respx (LLM), pytest-mock, fakeredis, aiosmtpd, eth-tester
- **GAPS for ≥300/feature target:**
  - ❌ No factory_boy / model_bakery (rapid fixture generation)
  - ❌ No locust / k6 / pytest-benchmark (load test)
  - ❌ No security suite (no OWASP ZAP, no SQLi/XSS payload builder)
  - ❌ No hypothesis (property-based testing)
  - ❌ No pytest-bdd / behave (Gherkin for UAT)

### Frontend (Vitest 4 + Playwright 1.59)
- **39+ component tests** colocated + `__tests__/` (97 test blocks counted)
- **37 Playwright e2e specs** (multi-browser, multi-viewport)
- Coverage thresholds: lines 80%, functions 80%, branches 75%
- A11y: `@axe-core/playwright` đã có
- **GAPS:**
  - ❌ No visual regression (Percy/Chromatic)
  - ❌ No Lighthouse CI / Web Vitals
  - ❌ No MSW for API mocking at scale

### Action items
- **A1** [Phase 0]: Install `factory_boy`, `pytest-bdd`, `hypothesis`, `locust` → backend dev deps
- **A2** [Phase 0]: Setup test data factories cho 6 personas (business owner, member, provider admin, auditor, IHC member, admin)
- **A3** [Phase 0]: Add `axe-core` accessibility tests vào Playwright suite
- **A4** [Per-feature]: Maintain 50 each × 6 types floor; track in `/docs/features/<feature>/test-report.md`

---

## B. Database Schema Map

### State after migration 015 (HEAD)
**25 tables**, post-self-assessment removal:

| Domain | Tables |
|---|---|
| Identity | users, password_reset_tokens, deletion_tokens, push_subscriptions |
| Documents | documents, audit_logs |
| Submissions | submissions, submission_comments, submission_evaluations, submission_revision_requests |
| Certificates | halal_certificates, cert_anchor_proofs |
| Audits | audit_checklist_templates, audit_visits, audit_visit_items, audit_ncr |
| Supply chain | suppliers, supplier_certificates, materials, process_templates, production_batches, batch_materials, batch_steps, batch_anchor_proofs |
| Notifications | notifications |
| Blockchain | blockchain_anchors |

### Hot tables (FK fanout ≥3)
- **users** — 8+ FK refs (cao nhất, mọi entity link tới)
- **submissions** — 7+ FK refs
- **halal_certificates** — 3+ FK refs (renewal self-ref + cert_anchor_proofs)
- **audit_visits** — 3+ FK refs
- **production_batches** — 3+ FK refs

### Tier-1 → table impact

| Feature | Tables touched (additive) | New tables expected |
|---|---|---|
| #24 Doc version control | `documents` (add `version_parent_id`, `version_number`, `approver_id`, `effective_date`, `next_review_date`, `retention_period`, `approved_at`) | `document_versions` (audit trail) |
| #23 Training Matrix | references `users` only | `training_templates`, `training_assignments`, `training_completions` |
| #22 IHC Meeting | references `users`, `documents` (link minutes attachment) | `ihc_meetings`, `ihc_attendees`, `ihc_decisions`, `ihc_action_items` |
| #28 Hazard Analysis | references `process_templates`, `materials` | `hazard_analyses`, `hazards`, `hazard_controls` |
| #29 CCP table | references `audit_visits`, `batch_steps`, `process_templates` | `ccps`, `ccp_critical_limits`, `ccp_monitoring_records`, `ccp_verifications` |
| #27 Internal Audit | similar pattern to `audit_visits` (internal scope) | `internal_audits`, `internal_audit_items`, `internal_audit_findings` |
| #30 Recall | references `production_batches`, `halal_certificates`, `notifications` | `complaints`, `recalls`, `recall_actions`, `recall_notifications`, `mock_recall_drills` |

### Migrations strategy (zero-regression)
- ✅ **Always additive**: `ADD COLUMN nullable` hoặc `DEFAULT` an toàn
- ❌ **Forbidden**: DROP COLUMN, RENAME COLUMN, ALTER constraint trên cột đang dùng — trừ khi qua deprecation cycle ≥1 release
- ✅ **New tables**: link via FK tới hot tables, không sửa hot tables
- ✅ **Indexes**: composite `(tenant_id, created_at)` cho mọi list endpoint
- ✅ **Migration reversibility**: `def downgrade()` BẮT BUỘC, test apply+rollback trước merge

### Action items
- **B1** [Per-feature]: Schema design doc (`/docs/features/<feature>/schema.md`) gồm migration UP/DOWN + index plan + backfill strategy
- **B2** [Phase 0]: Verify alembic downgrade path of all migrations 001→015 vẫn chạy được trên dev clone

---

## C. Endpoint Inventory + Hot Paths

### 167 endpoints across 6 domains

| Domain | Endpoints | Prefix | Notes |
|---|---:|---|---|
| Auth + Admin | 26 | `/auth` | login, register, invite, members, password reset, admin approve providers |
| Submissions + Workflow | 32 | `/api/submissions` | submit, revisions, evaluations, certificate issuance |
| Documents | 12 | `/api` | upload, evaluate, promote, IHC minutes export |
| Certificates | 10 | `/api/submissions/certificates` | issue, public registry, PDF, status (suspend/revoke), renewal |
| Notifications | 8 | `/api/notifications` | feed, push subscriptions, preferences |
| Onsite Audits | 24 | `/api/audits` | visits CRUD, items, NCR, signatures, reports, GPS |
| Supply Chain | 32 | `/api/supply-chain` | suppliers, materials, processes, batches, QR trace |
| GDPR | 5 | `/api/users` | export, deletion |
| Admin Analytics | 4 | `/auth/admin` | analytics, audit logs, overdue submissions |
| Public/Open | 2+ | various | cert verify, supplier portal token |

### Rate limits (nginx, in-place)
- Zone `api`: 10r/s, burst=20 cho `/api/*`, burst=10 cho `/auth/*`
- Zone `upload`: 2r/s, burst=5 cho `/api/upload`
- ❌ No cụ thể login/register rate limit (relying on `api` zone)
- ❌ No public endpoint rate limit khác biệt với auth'd endpoints

### Hot endpoints (high traffic, no specific rate limit beyond zone)
1. POST `/auth/login` — every session start
2. GET `/auth/me` — every component mount, every permission check
3. GET `/api/notifications/` — polled by frontend
4. GET `/api/submissions/received` — provider dashboard
5. GET `/api/audits/{vid}/items` — large JSONB, frequent reads
6. POST `/api/documents/upload` — multipart, capped 50MB
7. GET `/api/submissions/certificates/registry` — public, no auth → DDoS risk
8. GET `/api/supply-chain/batches` — potentially unbounded set

### Patterns
- ✅ Pagination: `page`, `limit`, `offset` ở một số list endpoints
- ❌ Cursor pagination: NOT implemented (cần cho large datasets)
- ❌ API versioning: không có `/v1`, `/v2`
- ✅ Multi-tenant: tenant_id từ JWT sub claim — không lộ trong query string

### Action items
- **C1** [Per-feature]: Mọi endpoint mới phải có pagination (default limit 50), index `(tenant_id, ...)`, rate limit zone phù hợp
- **C2** [Phase 0]: Setup nginx rate limit zone riêng cho `/auth/login` (2r/s burst=5) chống brute force
- **C3** [Per-feature]: SLO declared per endpoint trong spec doc (latency p95 + error budget)

---

## D. CI/CD Gap Analysis

### Hiện có (4 GitHub workflows)
- `ci.yml` — lint + smoke tests (PR trigger)
- `test.yml` — full test suite + coverage (PR + push)
- `build-push.yml` — Docker build + GHCR push (push to main/tags)
- `deploy.yml` — auto-deploy after build success + manual dispatch

### Gap matrix vs DevSecOps target

| Gate | Target | Hiện tại | Action |
|---|---|---|---|
| Pre-commit hooks | lint, format, type, fast tests | ❌ Không có `.pre-commit-config.yaml` | **Phase 0** |
| Backend lint | ruff check | ✅ Có | OK |
| Backend format | ruff format | ❌ Chỉ check, không format | Phase 0 |
| Backend type | mypy | ❌ Không có | Phase 0 |
| Frontend lint | next lint | ✅ Có | OK |
| Frontend format | prettier | ❌ Không có config | Phase 0 |
| Frontend type | tsc --noEmit | ⚠ Implicit qua build | Phase 0: explicit job |
| SAST Python | bandit + semgrep | ❌ Không có CI gate | **Phase 0** |
| SAST JS | semgrep | ❌ Không có | Phase 0 |
| Secrets scan | gitleaks | ❌ Không có CI gate | **Phase 0** |
| Dep audit Python | pip-audit | ❌ Không có CI gate | Phase 0 |
| Dep audit JS | npm audit | ❌ Không có CI gate | **Phase 0** |
| Container scan | trivy | ❌ Không có | Phase 0 |
| License check | pip-licenses + license-checker | ❌ Không có | Phase 1 (nice-to-have) |
| Test gate | pytest 80% + vitest 80% | ✅ Có cả hai | OK |
| Branch protection | require ≥1 review + CI green | ⚠ Cần check GitHub repo settings | Phase 0 verify |

### Action items
- **D1** [Phase 0]: Setup `.pre-commit-config.yaml` với ruff, prettier, gitleaks, mypy fast subset
- **D2** [Phase 0]: Add `security-scan.yml` workflow: bandit, semgrep, gitleaks, pip-audit, npm audit, trivy
- **D3** [Phase 0]: Verify GitHub branch protection: require CI green + ≥1 review

---

## E. Observability Inventory

### Stack hiện có (mature in setup, weak in instrumentation)
- ✅ **Prometheus** (port 9090, 7-day retention, 15s scrape)
- ✅ **Loki** (log aggregation, 7-day retention)
- ✅ **Promtail** (Docker container log shipping)
- ✅ **Grafana** (port 3200, datasources provisioned)
- ✅ **Sentry** (when `SENTRY_DSN` set; sample rate 10% traces + 10% profiles)

### Instrumentation status

| Layer | Logging | Metrics | Tracing |
|---|---|---|---|
| Backend | ⚠ Plain Python `logging.basicConfig(INFO)` — không structured, không có request ID | ❌ Không có `prometheus_client` instrumentation, `/metrics` endpoint không tồn tại; chỉ Prometheus scrape `/health` | ⚠ Sentry only, sample 10% |
| Frontend | ⚠ Console only | ❌ Không có | ❌ Không có Sentry/Datadog frontend |
| Nginx | ✅ Standard access/error log | ❌ Không có metrics export | N/A |
| Qdrant | N/A | ✅ `/metrics` scraped | N/A |

### Alerting
- ❌ No Prometheus alert rules
- ❌ No Grafana notification channels

### Gaps blocking SLO declaration
1. Backend không có per-endpoint latency histogram → không tính được p95
2. Backend không có per-endpoint error counter → không tính được error rate
3. Sentry sample 10% — không đủ chính xác cho SLO compliance
4. Không có request correlation ID xuyên backend → khó debug

### Action items
- **E1** [Phase 0]: Add `starlette_prometheus` middleware → expose `/metrics` endpoint với HTTP histogram per route
- **E2** [Phase 0]: Convert backend logging sang structured (JSON) với `structlog`, thêm `X-Request-ID` middleware
- **E3** [Phase 0]: Setup Sentry frontend SDK trong `app/layout.tsx`
- **E4** [Phase 1]: Define Prometheus alert rules + Grafana SLO dashboard
- **E5** [Per-feature]: SLO declaration trong feature spec doc

---

## F. Rollback Runbook

### F.1 Backend code rollback
```bash
# Check current
cat .deploy-tag

# Rollback to previous tag (script auto-verifies health)
./scripts/deploy-from-registry.sh <previous-tag>
```
Auto-rollback nếu `/health` check fail trong 150s. Concurrency-locked.

### F.2 Database migration rollback
```bash
./scripts/db-migrate.sh current
./scripts/db-migrate.sh history
./scripts/db-migrate.sh downgrade -1     # one step back
./scripts/db-migrate.sh downgrade <rev>  # to specific revision
```
**⚠ Caution:** DROP COLUMN / RENAME / DROP TABLE không reversible. Always preview migration source trước downgrade.

### F.3 Frontend rollback
**Option A** (preferred): image rollback qua `deploy-from-registry.sh <prev-tag>`.
**Option B**: route hide qua `LayoutShell.tsx` `FULL_SCREEN_PREFIXES` modification (cần redeploy).

### F.4 Feature flag flip
❌ **Hiện tại KHÔNG có hệ thống feature flag**.
- **Gap action F4**: implement minimal flag system trước Tier-1 — Redis-backed `tenant_settings.features.<feature_name>` boolean. Cần cho gradual rollout của Tier-1 modules.

### F.5 Data restore từ backup
```bash
./scripts/backup.sh                       # full backup
./scripts/restore.sh --yes <backup-dir>   # full restore
./scripts/restore.sh --db-only <dir>      # PostgreSQL only
./scripts/restore.sh --qdrant-only <dir>  # vectors only
```
Retention 7 days, daily cron at 02:00.

### F.6 Smoke verification post-rollback
```bash
# Backend
curl -sf http://localhost:8100/health
curl -sf http://localhost:8100/stats

# Frontend
curl -I http://localhost:3100

# Database
docker exec aminra-docker-system-postgres-db-1 psql -U aminra_user -d aminra -c "SELECT 1"

# Qdrant
curl -s http://localhost:6433/health
```

### Action items
- **F1** [Phase 0]: Implement minimal feature flag system (`tenant_settings.features` JSONB column on `users` or new `tenant_settings` table)
- **F2** [Per-feature]: Mỗi feature spec phải có rollback plan riêng (migration downgrade test + flag toggle test)

---

## G. Security Baseline (2026-04-29)

Run via throwaway containers (host clean).

### G.1 Frontend dependency audit (`npm audit`)
**5 vulnerabilities — 3 moderate, 2 high**

| Severity | Package | CVE/Advisory | Range affected |
|---|---|---|---|
| HIGH | `@xmldom/xmldom` | DoS via uncontrolled recursion (GHSA-2v35-w6hq-6mfw) | `>=0.9.0 <0.9.10` |
| HIGH | `@xmldom/xmldom` | XML injection via DocumentType serialization (GHSA-f6ww-3ggp-fr8h) | same |
| HIGH | `@xmldom/xmldom` | XML node injection via processing instruction (GHSA-x6wf-f3px-wcqx) | same |
| HIGH | `@xmldom/xmldom` | XML node injection via comment serialization (GHSA-j759-j44w-7fr8) | same |
| MOD | Next.js | DoS with Server Components (GHSA-q4gf-8mx6-v5v3) | current |
| MOD | postcss | XSS via unescaped `</style>` (GHSA-qx2v-qp2m-jg93) | <8.5.10 |

**Action G1** [Phase 0]: `npm audit fix` — verify đầy đủ. Nếu cần `--force` (Next.js bump), test toàn bộ Playwright suite trước merge.

### G.2 Backend dependency audit (`pip-audit`)
✅ **No known vulnerabilities found** — clean baseline.

### G.3 Backend SAST (`bandit -ll`)
**78 issues**: 1 HIGH, 46 MEDIUM, 31 LOW (severity ≥ medium scanned)

Top concerns:
- **CWE-89 SQL injection** trong `supply_chain/supplier_router.py:53, 112` (f-string trong SQL query). 2 vị trí. **Risk: HIGH if user input reachable.**
- **CWE-377 hardcoded /tmp** trong `supplier_router.py:250, 258` (LibreOffice convert subprocess). Risk medium.

**Action G3** [Phase 0]:
- Audit cả 47 medium+ findings, classify thật/false-positive
- Fix SQL injection trong supplier_router (parameterize query, white-list cond expressions)
- Replace `/tmp/...` bằng `tempfile.mkdtemp()` cho process isolation
- Add `bandit -ll` vào CI gate

### G.4 Secrets scan (`gitleaks`)
**2 leaks found in git history**

| File | Line | Type | Severity |
|---|---|---|---|
| `docker-compose.yml` | 95 | `VAPID_PRIVATE_KEY=...` | **HIGH** — production push notification key |
| `frontend/aminra-web/e2e/25-pwa-push.spec.ts` | 67 | auth string | **MEDIUM** — likely test fixture nhưng phải verify |

**Action G4** [Phase 0 — IMMEDIATE]:
- **Rotate VAPID key** ngay (revoke + regenerate, deploy mới)
- Move VAPID private key sang Vault (đã có `vault-server` running)
- Verify e2e test fixture không phải prod credential
- Add `gitleaks` vào pre-commit + CI
- ⚠ **Note**: Git history vẫn chứa secret cũ — phải revoke key cũ ở mức service (Web Push dashboard) chứ không phải chỉ git filter-branch

### G.5 Container scan
⏸ **Deferred to Phase 0** — chưa chạy trivy. Estimate: 2-3 medium findings on base images (python:3.11-slim, node:20-alpine usually clean).

---

## H. Phase 0 Setup — Action Plan (5–7 days)

Trước khi start Feature #24, hoàn thành:

### Day 1: Critical security fixes (G4 + G1)
- [ ] Rotate VAPID key, move to Vault
- [ ] `npm audit fix` — verify Playwright suite still green
- [ ] Verify e2e fixture is not real cred

### Day 2: SAST cleanup (G3)
- [ ] Fix 2 SQL injection in supplier_router.py
- [ ] Audit 46 medium bandit findings, fix or `# nosec` with justification
- [ ] Replace hardcoded /tmp with tempfile

### Day 3: CI gates (D1, D2)
- [ ] Setup `.pre-commit-config.yaml` (ruff, prettier, gitleaks, mypy fast)
- [ ] Add `security-scan.yml` workflow (bandit, semgrep, gitleaks, pip-audit, npm audit, trivy)
- [ ] Verify branch protection settings

### Day 4: Observability (E1, E2, E3)
- [ ] Add `starlette_prometheus` → `/metrics` endpoint
- [ ] Convert backend to `structlog` + request ID middleware
- [ ] Setup frontend Sentry SDK

### Day 5: Test infra (A1, A2, A3)
- [ ] Install `factory_boy`, `pytest-bdd`, `hypothesis`, `locust`
- [ ] Build 6 persona factories
- [ ] Add axe-core to Playwright suite

### Day 6: Feature flag system (F1)
- [ ] Schema: `tenant_settings.features JSONB` column hoặc new table
- [ ] Backend: `is_feature_enabled(tenant_id, feature_name)` helper + middleware
- [ ] Frontend: `useFeature(name)` hook
- [ ] Test: 50 unit + 20 integration

### Day 7: Final smoke + docs
- [ ] Full regression test: `pytest` + `vitest` + `playwright`
- [ ] Disk usage baseline (test data hygiene baseline)
- [ ] Sign-off doc + present to user

---

## I. Sign-off Checklist

Trước khi start Feature #24:
- [ ] Phase 0 day 1 critical security fixes done (rotated VAPID, npm audit clean)
- [ ] Phase 0 day 2 SAST cleanup done (SQL injection fixed)
- [ ] Phase 0 day 3 CI gates configured (pre-commit + security-scan workflows)
- [ ] Phase 0 day 4 observability instrumented (`/metrics`, structured logs, frontend Sentry)
- [ ] Phase 0 day 5 test infra ready (factories, BDD, axe-core)
- [ ] Phase 0 day 6 feature flag system shipped
- [ ] Phase 0 day 7 full regression green + sign-off

User approval signature: ☐ ____________________ Date: ____________

---

## J. Open Questions for User

1. **Sentry trace sample rate 10% — bump lên 100% cho dev + 50% cho prod?** Cost trade-off vs SLO accuracy.
2. **Feature flag scope: tenant-level hay user-level?** Tenant đơn giản hơn; user cho A/B testing tinh tế hơn.
3. **VAPID key rotation: ai approve emergency rotation?** Cần process documented.
4. **Acceptable test execution time per feature**: 300 tests/feature × 6 features = 1800+ tests. Nếu mỗi test 200ms thì 6 phút CI. OK không?
5. **Phase 0 timeline 5–7 ngày: tăng tốc skip nào không?** Recommend KHÔNG skip nào.
