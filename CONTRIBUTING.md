# Contributing to AMINRA

> Solo-founder phase — convention chính thức hoá trước khi onboard contractor.

## Trước khi commit

1. **Đọc `CLAUDE.md`** — convention codebase, stack thật, no-touch zone
2. **Đọc brain** `../all-docs/02-Projects/aminra/README.md` Section 2 (ACTIVE_TASKS) — đừng đụng task in_progress
3. **Test pass:** `pytest -x` (BE) + `npm test` (FE)
4. **Lint pass:** `ruff check backend/` + `npm run lint`

## Branch & commit

- Branch: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `test/<topic>`, `ops/<topic>`
- Commit format: `<type>(<scope>): <subject>` (Conventional Commits)
- 1 commit = 1 logical change; test phải xanh trước commit
- Co-author Claude khi pair: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`

## PR checklist

- [ ] CHANGELOG entry (nếu user-visible)
- [ ] Test coverage cho path mới (unit + integration tối thiểu)
- [ ] ADR mới nếu đụng decision kiến trúc
- [ ] Brain update nếu đụng status/task/decision (Section 1, 2, 5)
- [ ] Threat-model review nếu đụng auth, RBAC, tenant boundary, secret
- [ ] Cross-tenant test pass nếu đụng query layer
- [ ] Migration UP+DOWN test nếu thêm Alembic version

## Security

- KHÔNG commit secret. `.env.example` template, real value qua Vault
- KHÔNG bypass `--no-verify` pre-commit hook
- KHÔNG đụng `backend/services/certificate_pdf.py` (cert hash invariance)
- Báo cáo lỗ hổng: privately tới founder, KHÔNG public issue

## Code review tự kiểm

Theo persona DevSecOps trong CLAUDE.md global:
1. Có giả định nào ngầm? Đã làm rõ chưa?
2. Edge case + failure mode đã được test?
3. Có chỗ nào miss permission check không?
4. Có rò rỉ tenant boundary không?
5. Test có hời hợt (chỉ happy path) không?

Nếu trả lời "không chắc" cho bất kỳ câu nào → KHÔNG merge.
