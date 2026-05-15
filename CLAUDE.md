---
project: aminra
codebase_root: /home/user/Documents/aminra-docker-system/
brain: /home/user/Documents/all-docs/02-Projects/aminra/README.md
last_updated: 2026-05-09
review_cadence_days: 90
---

# CLAUDE.md — AMINRA codebase

> **Đọc brain trước.** Mọi context động (status, ACTIVE_TASKS, INCIDENTS, RECENT_DECISIONS) ở vault, KHÔNG ở đây.

@/home/user/Documents/all-docs/02-Projects/aminra/README.md

---

## 1. Stack (verified 2026-05-09)

| Layer | Tech | Note |
|---|---|---|
| Backend API | FastAPI (Python 3.11+) + uvicorn/gunicorn | `backend/main.py` entry. OpenAPI auto `/docs` |
| Async jobs | **arq** (KHÔNG Celery, KHÔNG APScheduler) — ADR-003 | `backend/services/jobs.py` def, `backend/worker.py` register |
| Migrations | **Alembic** (KHÔNG Prisma) | `backend/alembic/versions/` — UP+DOWN bắt buộc |
| RDBMS | PostgreSQL **schema-per-tenant** — ADR-001 | Mỗi tenant = 1 schema, KHÔNG row-level |
| Vector | Qdrant | Embedding tài liệu + quy định Halal |
| Cache/queue | Redis | Session, arq queue |
| LLM | OpenRouter → DeepSeek primary — ADR-004 | KHÔNG hardcode provider; key qua Vault |
| Secret | HashiCorp Vault (AppRole) | `secret/aminra/*`. Rotation: `vault/scripts/rotate-secrets.sh` |
| Frontend | Next.js 16 (App Router) + Tailwind v4 + i18next (en/vi/ar) | `frontend/aminra-web/` |
| FE test | Vitest (unit) + Playwright (e2e) | `npm test` / `npm run test:e2e` |
| BE test | pytest (1132 collected) | In-container; HOST_CI=1 unlocks host-only |
| Blockchain | Polygon (cert anchoring) | `backend/services/certificate_pdf.py` invariance — KHÔNG đụng |
| CMS | **CHƯA QUYẾT** (TASK #6, P2) | Đừng commit code/doc nhắc Payload/Strapi cho đến khi ADR ra |
| Auth | **JWT manual → Keycloak migration** — ADR-005 | TASK #1 in_progress (chưa code; decided 2026-05-09) |

---

## 2. Codebase layout

```
aminra-docker-system/
├── backend/         FastAPI + arq + Alembic + tests/ + services/
│   ├── main.py
│   ├── auth/        JWT + manual RBAC (sẽ thay)
│   ├── services/    pdf_renderer, llm/, certificate_pdf (no-touch), jobs.py
│   ├── alembic/     migrations
│   ├── tests/       unit/integration/uat (1132 collected)
│   └── templates_html/  PDF Jinja templates (4-layer governance)
├── frontend/aminra-web/   Next.js 16
│   ├── app/         3 portal route (DN/CB/Admin)
│   └── __tests__/
├── nginx/           reverse proxy
├── monitoring/      Prometheus + alert rules
├── docs/            per-feature spec/threat-model/test-plan/test-report
├── docker-compose.yml      dev stack (12+ service)
└── Makefile         shortcuts (preview, lint-templates, visual-test, sync-templates)
```

**KHÔNG đụng:**
- `backend/services/certificate_pdf.py` — reportlab cert PDF, hash invariance live trên blockchain
- `backend/alembic/versions/` đã merge — chỉ thêm migration mới, không sửa cũ

---

## 3. Conventions

### Code
- **Python:** ruff + black; type hint bắt buộc cho function public; Pydantic schema cho mọi I/O
- **TypeScript:** strict mode; no `any`; component test cho Server Component qua Playwright (không Vitest)
- **Migrations:** mỗi Alembic file có `upgrade()` + `downgrade()`. Test trên schema rỗng trước khi merge
- **Tenant boundary:** mọi query MUST scope qua `current_tenant.schema`. Cross-tenant integration test ở `tests/test_cross_tenant_*`
- **Permission:** hiện dùng manual `require_*` (tech debt — đợi RBAC engine TASK #2). KHI thêm route mới → check brain RISK "Manual RBAC check rải rác"

### Testing discipline (per global persona)
- KHÔNG test cho đủ số lượng. Test edge case + failure mode thực sự
- Integration test với DB thật (auto-detect via `DATABASE_URL` probe)
- UAT scenarios cần `HOST_CI=1` — chạy từ host CI runner
- Visual regression cho PDF: `pytest tests/visual` — baseline trong `tests/visual/baselines/`

### PDF render service (đã ship 13 doc_type, Phase 1-5 done)
- **3-stage pipeline:** `PDFDataAggregator` → `FilterPipeline` (6 filter) → `PDFRenderer`
- **Real data ALWAYS wins**, placeholder fill empty/None gaps. `PROTECTED_KEYS` (business_name, *_date, tenant_id) NEVER replaced
- **Schema-aware Jinja:** `services/schema_aware_data.py::SchemaAwareData` — KHÔNG dùng `s.field` trực tiếp với optional, dùng `s.get('field')` hoặc wrap qua `SchemaAwareData`

### Commit
- Format: `<type>(<scope>): <subject>` — type: feat/fix/test/docs/refactor/perf/build/ops
- 1 commit = 1 logical change. Test phải pass trước commit
- Chữ ký Claude bắt buộc khi co-author: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

---

## 4. Quick commands

```bash
# Stack
docker compose up -d                     # Start full stack
docker compose ps                         # Verify all healthy
make help                                 # Makefile targets

# Backend test (in-container)
docker compose exec aminra-backend pytest -x

# Backend test với DB auto-detect
docker compose exec aminra-backend pytest tests/integration

# Frontend — convention post-2026-05-14 (U19, eliminate Turbopack mem leak):
#   DEFAULT = prod build (`make fe-prod`). Only run dev when actively editing FE.
make fe-prod                              # Prod build, no HMR, no leak
make fe-dev                               # Dev + HMR — only when editing FE this session
make fe-status                            # Which FE is running + memory %
make fe-stop                              # Stop both
cd frontend/aminra-web && npm test        # Vitest (host, fast)
cd frontend/aminra-web && npm run test:e2e  # Playwright

# PDF preview
make preview doc=halal_policy

# Lint templates
make lint-templates

# Visual regression
make visual-test
make visual-baseline                      # Re-record after intentional design change

# Vault unseal
docker compose exec vault-server vault operator unseal
```

Backend dev URL: `http://localhost:8100/docs` (Swagger UI auto)
Frontend dev URL: `http://localhost:3100`

---

## 5. Trước khi action — checklist

1. **Đọc brain Section 1** (CURRENT STATUS) + **Section 2** (ACTIVE_TASKS) — đừng đụng task in_progress của người khác
2. **Verify file/path/flag** trong brain còn tồn tại trước khi recommend
3. **Cross-tenant test** nếu đụng query layer — `pytest tests/test_cross_tenant_*`
4. **PDF cert hash invariance** — KHÔNG đổi cert PDF render path
5. **Secret KHÔNG commit** — `.env.example` template, real value qua Vault
6. **Brain update cuối session** quan trọng — theo `05-Protocols/session-end.md`

---

## 6. Liên kết quan trọng

| Resource | Path |
|---|---|
| Brain (canonical state) | `@/home/user/Documents/all-docs/02-Projects/aminra/README.md` |
| Glossary | `vault/aminra/GLOSSARY.md` |
| ADR (7 decisions) | `vault/aminra/architecture/adr/ADR-00{1..7}*.md` |
| Threat Model | `vault/aminra/security/threat-model.md` |
| Per-feature docs | `docs/features/<feature>/{spec,threat-model,schema,test-plan,test-report}.md` |
| Runbook deploy | `vault/aminra/operations/runbook-deploy.md` |
| Incident playbook | `vault/aminra/operations/runbook-incident-security.md` |
