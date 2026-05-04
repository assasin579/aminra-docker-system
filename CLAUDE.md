---
last_reviewed: 2026-05-03
review_cadence: 90d
---

# AMINRA — project_memory

> **Note:** Section trống = unknown. Claude KHÔNG được suy đoán nội dung.
> Nội dung gốc QA testing guide ở [`CLAUDE.testing-legacy.md`](./CLAUDE.testing-legacy.md).

## context

- **Tên:** AMINRA
- **Sứ mệnh:** Nền tảng SaaS đa người thuê (multi-tenant) kết nối doanh nghiệp Việt Nam có nhu cầu chứng nhận Halal với các Tổ chức Chứng nhận (CB), được hỗ trợ bởi AI để sàng lọc và tự động hóa quy trình xin, cấp và quản lý vòng đời chứng nhận. Công nghệ blockchain hỗ trợ truy xuất nguồn gốc sản phẩm. Tầm nhìn: trở thành đối tác hạ tầng số của doanh nghiệp và cơ quan chứng nhận, phát triển công nghiệp Halal, hội nhập nền kinh tế Hồi giáo toàn cầu.
- **Giai đoạn:** Đang hoàn thiện MVP để ra mắt nhà đầu tư.
- **Nhà sáng lập:** Solo founder — nền tảng DevSecOps/IT, Chứng nhận Halal.

### Mô hình kinh doanh

- **Tier 1:** Nền tảng cấp/quản lý chứng nhận, quản lý auditor cho CB (HALCERT, HCA, ...) + Nền tảng chuẩn bị hồ sơ, internal audit cho doanh nghiệp.
- **Tier 2:** Truy xuất nguồn gốc full blockchain, chấm điểm doanh nghiệp, kết nối sàn TMĐT để quảng bá sản phẩm đạt chuẩn.
- **Tier 3:** Tích hợp các chứng nhận khác (HACCP, VietGAP, GlobalGAP, hữu cơ).

## architecture

- **Pattern:** SaaS multi-tenant với 3 portal (Doanh nghiệp / Tổ chức Chứng nhận / AMINRA admin).
- **Phong cách:** Modular monolith trước, chỉ tách microservice khi tải thực sự đòi hỏi (thiết kế để mở rộng dễ).

### Backend
- **API:** FastAPI (Python 3.11+)
- **Vector DB:** Qdrant (semantic search trên nguyên liệu, quy định, tài liệu chính thống)
- **Relational DB:** PostgreSQL (multi-tenant qua **schema-per-tenant**)
- **Cache:** Redis (session, rate limiting, job queue backing store)
- **Task queue:** **arq** (xem `docker-compose.yml: arq-worker`, services tại `backend/services/jobs.py`)
- **Migration:** Alembic (`backend/alembic/versions/`)
- **CMS:** *Planned, chưa triển khai* — chưa có dependency Payload CMS hay folder `backend/cms` trong codebase. Decision pending.

### AI Layer
- **LLM gateway:** **OpenRouter** (key qua Vault `secret/aminra/api-keys.openrouter_api_key`). DeepSeek được gọi qua OpenRouter (model `deepseek/deepseek-chat-v3`).
- **Fallback:** DEEPSEEK_API_KEY (direct, hiện chưa active — vẫn `REPLACE_ME` trong Vault).
- **Use cases:**
  - Pipeline enrichment nội dung RSS (HDC, BPJPH, MUIS, JAKIM, HalalFocus)
  - Quét tuân thủ nguyên liệu (upload công thức → flag rủi ro Halal)
  - Crawl dữ liệu tin tức
  - Phân tích gap tài liệu để đánh giá độ sẵn sàng chứng nhận, chấm điểm hồ sơ
  - Dịch nội dung đa ngôn ngữ

### Frontend
- **Framework:** Next.js 15 (App Router) + Turbopack dev mode
- **Styling:** Tailwind v4
- **i18n:** `i18next` + `react-i18next`, namespace tại `public/locales/{en,vi,ar}/` *(auto-discovered, please verify — chỉ thấy 3 lang folder, README đề cập 4 lang)*

### Lưu trữ
- **Object:** S3-compatible (Cloudflare R2)
- **Database backup:** PostgreSQL → local + Backblaze B2 + Cloudflare R2 (xem `~/scripts/db_backup.sh`)

## security

### Mô hình đe dọa
- **Tài sản quý:** Dữ liệu kinh doanh tenant, tài liệu chứng nhận, công thức nguyên liệu, báo cáo auditor.
- **Đe dọa chính:**
  - Rò rỉ dữ liệu xuyên tenant (rủi ro kinh điển của SaaS đa người thuê)
  - Credential stuffing vào tài khoản auditor/CB
  - Supply chain attack qua dependency npm/pip
  - Prompt injection qua tài liệu được upload

### Auth
- **Provider:** *(decision pending — hiện tại self-hosted JWT)*
- **MFA:** *(decision pending)*
- **Session:** JWT HS256, 8h access token, 7d refresh (`docker-compose.yml: JWT_EXPIRE_HOURS=8, JWT_REFRESH_DAYS=7`)
- **Secret rotation:** `bash vault/scripts/rotate-secrets.sh auth`

### Authorization
- RBAC scope theo tenant.
- **Engine:** *(planned — Casbin hoặc oso, chưa triển khai. Hiện dùng Python check thủ công trong `backend/auth/jwt_utils.py: require_business_owner`, `require_provider_owner`, etc.)*

### Bảo vệ dữ liệu
- **At rest:** Mã hóa AES-256 cho tài liệu, transparent DB encryption.
- **In transit:** TLS tối thiểu 1.2.

### Quản lý secret
- KHÔNG secret trong code/config commit lên GitHub.
- Vault (HashiCorp) tại `vault/`. AppRole auth cho backend, vault-agent render env.sh.

### Tính toàn vẹn tài liệu
- **Hashing:** SHA-256 mọi tài liệu upload, lưu khi submit.
- **Audit trail:** Bảng `audit_logs` (PostgreSQL), endpoint `/auth/admin/audit-logs` (xem `backend/auth/audit_log_router.py`).
- **QR registry:** Xác minh chứng nhận công khai qua QR → kiểm tra hash chống giả mạo.

### AI Security
- **Prompt injection:** Sanitize và cô lập nội dung tài liệu không tin cậy khỏi system prompt.
- **Cross-tenant leak:** Không truyền dữ liệu tenant A vào context prompt của tenant B.
- **Validate output:** Mọi output LLM là untrusted; validate theo schema Pydantic.

### Mục tiêu compliance
- PDPL Việt Nam (current), GDPR-ready (cho buyer EU), SOC 2 Type I (sau Series A).

## testing

### Test pyramid
- **Unit:** Pytest cho Python, Vitest cho TypeScript — mục tiêu **80% coverage** trên business logic.
- **Integration:** testcontainers cho Postgres/Redis/Qdrant; full API test trên stack ephemeral.
- **E2E:** Playwright cho user journey (multi-browser: desktop chromium + mobile Pixel 5).

### Stack hiện tại
- Backend: pytest 9 + pytest-asyncio (mode=auto) + httpx + respx + pytest-mock + pytest-cov
- Frontend: Vitest + React Testing Library + jest-dom (jsdom env)
- E2E: Playwright (44 tests, 10 specs)

### Run commands
```bash
# Backend
cd backend && ./run_tests.sh                # all
cd backend && ./run_tests.sh --cov          # with coverage gate (≥80%)

# Frontend unit
cd frontend/aminra-web && npm test

# Frontend E2E
cd frontend/aminra-web && npm run test:e2e          # desktop
cd frontend/aminra-web && npm run test:e2e:mobile   # Pixel 5
```

> **Halal domain testing priorities, fixtures, factories**: chi tiết đầy đủ ở [`CLAUDE.testing-legacy.md`](./CLAUDE.testing-legacy.md). Cần migrate những bullet quan trọng vào đây sau.

## code_quality

<!-- TODO: ghi linter (ruff?), formatter, naming conventions, file/folder structure,
     "do not" patterns. Hiện chưa có. -->

*Auto-discovered facts (please verify):*
- Backend: ruff + mypy (config tại `backend/ruff.toml`)
- Frontend: prettier + ESLint (xem `frontend/aminra-web/.prettierrc`, `eslint.config.js` nếu có)
- Pre-commit hooks: gitleaks, ruff format, prettier (xem `.pre-commit-config.yaml`)

## api

<!-- TODO: URL versioning, error response shape, rate limit policy, OpenAPI spec
     source-of-truth. -->

*Auto-discovered facts (please verify):*
- Base URL: `/auth/*`, `/api/*`, `/admin/*` (xem `backend/app.py: include_router`)
- Auth header: `Authorization: Bearer <jwt>`
- Rate limiting: tồn tại nhưng chưa documented (`Depends(rate_limit_upload)` trong `/ingest`, `/evaluate`)
- OpenAPI: FastAPI auto-generated tại `/docs`, `/openapi.json`

## devsecops

*Auto-discovered facts (please verify):*

### CI/CD
- GitHub Actions (`.github/workflows/`):
  - `ci.yml` — lint + smoke
  - `test.yml` — full pytest + vitest + Playwright
  - `security-scan.yml` — bandit, pip-audit, npm audit, gitleaks, semgrep, trivy
  - `build-push.yml` — Docker image build + push
  - `deploy.yml` — deployment

### Local dev
```bash
# Vault first
docker compose -f vault/docker-compose.vault.yml up -d
bash vault/scripts/init-vault.sh

# App stack
docker compose up -d                                  # production-like
docker compose --profile dev up -d aminra-frontend-dev   # FE hot-reload :3100
```

### Backup / restore
- Manual: `scripts/backup.sh` (PG dump + Qdrant snapshot + Docker volumes)
- Cron: `~/scripts/db_backup.sh setup-cron` (2×/ngày 00:00+15:00 qua crontab — KHÔNG dùng `scripts/backup-cron.sh`)
- Restore: `scripts/restore.sh <backup-dir>`
- Cloud sync: `~/scripts/db_backup.sh cloud-sync` (rclone → R2 + B2, chạy tự động sau mỗi backup)
- Verify: `~/scripts/backup_verify.sh` (weekly thứ Hai 04:00 — test-restore vào DB tạm, kiểm tra schema)

### Secret rotation
- API keys: `bash vault/scripts/rotate-secrets.sh api-keys`
- Database password: `bash vault/scripts/rotate-secrets.sh database`
- JWT + admin: `bash vault/scripts/rotate-secrets.sh auth`
- VAPID web push: `bash vault/scripts/rotate-secrets.sh web-push`

### Migration
- Tool: Alembic. Wrapper: `scripts/db-migrate.sh {current|upgrade|downgrade|new|stamp}`
- Convention: additive-only, `def downgrade()` mandatory, schema impact analysis bắt buộc cho mỗi feature mới (`docs/features/<feature>/schema.md`).

## observability

*Auto-discovered facts (please verify):*

- **Frontend error tracking:** Sentry (`@sentry/nextjs ^10.50.0`)
- **Backend error tracking:** Sentry SDK Python (env `SENTRY_DSN`, optional)
- **Logging:** structlog (Python) — structured fields `event`, `request_id`, `level`, `timestamp`
- **Metrics:** *(planned — Prometheus + Grafana đã đề cập trong `docs/dev-setup.md` URLs nhưng chưa thấy config)*
- **Dashboards:**
  - Grafana: http://localhost:3200 (planned)
  - Prometheus: http://localhost:9090 (planned)

## risks

*Snapshot 2026-05-03:*

### Critical bugs (Tier 1) — phải fix trước CB demo
13 critical bugs đã document tại [`docs/bug-audit-2026-04-26.md`](docs/bug-audit-2026-04-26.md), bao gồm:
- C1: `replace-document` works on approved submissions → cert covers doc CB never reviewed (compliance violation)
- C5: `viewDoc` puts JWT in URL querystring → token leak via Referer/logs
- C6: `documents/{id}/preview` cross-tenant access via OR clause
- C7: `/ingest` no path-traversal sanitization → cross-tenant file overwrite
- C12-C13: `/evaluate`, `/ingest`, `/rewrite` anonymous → unauth LLM cost burner

### Tech debt
- Vault setup vẫn manual init lần đầu (auto-init script chưa có)
- `update_updated_at_column()` function phải tạo manual sau init (init.sql ordering bug)
- Modal positioning đã fix triệt để (memory: `feedback_modal_containing_block.md`) — không nên regress
- 264+ hardcoded hex colors trong frontend (CSS vars defined nhưng underutilized)

### Operational
- Cron daemon trên Qubes VM cần qubes-service `crond` enable từ dom0 (xem memory: `env_qubes.md`)
- Cloudflare cache có thể serve stale JS chunks → dev nên dùng `localhost:3100` thay vì tunnel
- Modal mới phải dùng `<Modal>` portal component (không tự `<div fixed inset-0>`)

## definition_of_done

PR chỉ được merge khi đủ:

- [ ] Tests pass + coverage ≥ 80% trên business logic mới
- [ ] Security scan clean (bandit, npm audit, gitleaks, semgrep, trivy — xem `.github/workflows/security-scan.yml`)
- [ ] Schema migration kèm UP/DOWN nếu DB đổi; reviewed SQL diff
- [ ] Docs updated nếu feature mới: `docs/features/<feature>/{spec,threat-model,schema,test-plan,test-report,runbook}.md`
- [ ] Conventional commit message (`feat|fix|chore|docs|...(scope): subject`)
- [ ] Manual QA trên feature/bug fix UI (test trên `localhost:3100` để bypass CF cache)
- [ ] Không có `skip` / `xfail` / `.only()` / `.fixme()` lẫn trong commit
- [ ] Không hardcode secret / credential / tenant_id trong test
