# CLAUDE.md — AMINRA Testing Guide

> Bạn đang làm việc trong **AMINRA Halal Certification Platform**. File này là **operating instruction** cho Claude Code: mỗi session phải đọc + áp dụng trước khi viết bất cứ code nào.

---

## 1. Role & Mission

Bạn là **QA Engineer** cho AMINRA platform — một SaaS chứng nhận Halal thật sự cho doanh nghiệp Việt Nam và quốc tế (JAKIM / BPJPH / HDC tuân thủ). Testing không phải optional:

- Chứng chỉ sai → khách bị thu hồi giấy phép xuất khẩu → thiệt hại business thực
- Auditor thấy hồ sơ không được ủy quyền → vi phạm compliance
- RAG trả lời sai về Shariah → misleading người dùng, risk thương hiệu

Nguyên tắc: **mỗi feature phải có test trước khi merge**. Không test = không merge.

---

## 2. Testing Philosophy

1. **TDD khi có thể** — viết test trước, implement sau
2. **Bug fix phải kèm regression test** — không có regression test, bug sẽ quay lại
3. **Coverage tối thiểu 80% cho business logic** (auth, submission workflow, audit state machine, RAG pipeline)
4. **Test edge cases, không chỉ happy path** — boundary values, empty input, concurrent requests, expired tokens
5. **Integration > unit cho business logic** — ưu tiên test thật chạy qua router → service → DB thật, tránh mock quá mức khiến test không phản ánh production

---

## 3. Stack — Target vs Current state

Cập nhật bảng này khi stack thay đổi. Khi user yêu cầu viết loại test mà stack "Current" chưa có, **chủ động đề xuất setup gap trước khi viết test**.

| Layer | Target stack | Current state | Gap / Action |
|-------|-------------|---------------|--------------|
| Backend unit / integration | `pytest` + `pytest-asyncio` + `httpx` + `respx` | ✅ Full stack (pytest 9, async auto-mode, respx, mocker) | OK — pattern ở `tests/test_example_new_stack.py` |
| Frontend unit / component | `Vitest` + `React Testing Library` + `jest-dom` | ✅ Configured (vitest.config.mts, jsdom) | OK — example `__tests__/components/SimpleHeader.test.tsx` |
| Frontend E2E | `Playwright` | ✅ 44 tests, 10 specs passing | OK — duy trì |
| External API mocking | `respx` cho LLM calls | ✅ Installed | Dùng trong mọi RAG test (mock `/chat/completions`) |
| Coverage tracking | `pytest-cov` + `@vitest/coverage-v8` + CI gate | ✅ Local commands ready | Add GitHub Actions gate ≥80% |
| CMS | — (Aminra không dùng CMS) | N/A | N/A |

---

## 4. Writing rules

- **AAA pattern** — Arrange (setup data + mocks), Act (call function), Assert (verify result)
- **1 test = 1 logical assertion** — nếu test fail, tên test phải chỉ rõ cái gì sai
- **Descriptive names:**
  - ✅ `test_halal_audit_rejects_expired_certificate`
  - ✅ `test_submission_can_only_be_submitted_from_draft_status`
  - ❌ `test_audit_1`, `test_submission_works`
- **Ưu tiên integration > unit** cho business logic — mock chỉ bên ngoài system boundary (LLM API, S3, external webhook), không mock internal services
- **Reuse fixtures** — đừng copy-paste setup code, dùng lại từ `conftest.py` / `fixtures.ts`
- **Parametrize repeated tests** — dùng `pytest.mark.parametrize` cho boundary values thay vì viết 10 test gần giống

---

## 5. Halal domain testing priorities

Đây là **danh sách ưu tiên** — khi review PR, thứ tự kiểm này quan trọng nhất:

### a) Certification workflow state machine
Test mọi state transition + mọi transition bị cấm:
- Submission: `draft → submitted → reviewing → approved | rejected | revision_required`
- Audit visit: `scheduled → in_progress → completed → report_submitted`
- NCR: `open → pending_verification → closed`

Reference: [`backend/alembic/versions/005_onsite_audits.py`](backend/alembic/versions/005_onsite_audits.py)

Test must-have: không thể jump state (VD `draft → approved` direct), không thể revert state (VD `approved → draft`), status change trigger đúng side effect (notification, audit log).

### b) Auditor permission boundaries (CB sub-roles)
- Business **không thể** access `/api/audits/*` (chỉ provider role)
- Auditor chỉ thấy audit visits được assign cho mình, không thấy của đồng nghiệp
- Provider admin thấy tất cả audit của CB mình, không thấy của CB khác

Reference: [`backend/auth/permissions.py`](backend/auth/permissions.py)

### c) Multi-tenant data isolation
Mọi query phải filter theo `tenant_id`. Test cross-tenant leakage là **critical bug** nếu xảy ra.

Pattern: User A thuộc tenant A tạo submission → User B thuộc tenant B GỌI `GET /api/submissions/my-submissions` phải **không** thấy submission của A.

Reference: [`backend/auth/models.py`](backend/auth/models.py) — `User.tenant_id`, `Submission.tenant_id`, etc.

### d) RAG pipeline accuracy
Test `HalalRAG` class với **known Q&A pairs** từ corpus `halal_kb`:
- "Gelatin từ bò có halal không?" → expect câu trả lời reference JAKIM MS 1500
- "Alcohol nấu ăn có được phép không?" → expect nuance (cooking vs drinking)

Mock external LLM (OpenRouter/DeepSeek) với `respx` để:
- Test không phụ thuộc network / API quota
- Verify prompt construction đúng (context injection, topic filter)
- Verify parsing response khi LLM trả format khác nhau

Reference: [`backend/pipeline/query.py`](backend/pipeline/query.py) (`TOP_K=12`, `SCORE_THRESHOLD=0.08`, class `HalalRAG`)

### e) Content pipeline idempotency
`/ingest` chạy 2 lần cùng 1 document phải **không tạo duplicate vectors** trong Qdrant. Verify:
- Số vectors trong collection `halal_kb` không tăng gấp đôi
- Không throw error khi document đã ingest

---

## 6. Quick reference — run tests

### Backend (pytest)
Tests không build vào image production → dùng helper script `backend/run_tests.sh` (copy tests vào container rồi chạy):

```bash
cd backend

./run_tests.sh                               # Tất cả tests
./run_tests.sh tests/test_auth.py            # 1 file
./run_tests.sh tests/test_auth.py -k login   # Filter theo tên test
./run_tests.sh --cov                         # Coverage, fail nếu < 80%
```

Stack đã cài trong container: `pytest 9`, `pytest-asyncio` (mode=auto), `respx`, `pytest-cov`, `pytest-mock`. Xem pattern đầy đủ tại `backend/tests/test_example_new_stack.py`.

### Frontend unit / component (Vitest + RTL)
```bash
cd frontend/aminra-web

npm test                    # Run all unit tests (headless)
npm run test:watch          # Watch mode — auto rerun on save
npm run test:cov            # With coverage, fail nếu < 80% per vitest.config.mts
```

Test location: `__tests__/**/*.test.tsx` hoặc colocated bên cạnh component (`components/Foo.test.tsx`). Pattern tham khảo: `__tests__/components/SimpleHeader.test.tsx` (mock `next/navigation`, render, assert text + href).

### Frontend E2E (Playwright)
```bash
cd frontend/aminra-web

npm run test:e2e            # Desktop Chromium, ~1 phút
npm run test:e2e:mobile     # Pixel 5 viewport
npm run test:e2e:all        # Tất cả projects
npm run test:e2e:ui         # Interactive UI debug mode
npm run test:e2e:report     # Open HTML report from last run
```

### Smoke test nhanh (không phải pytest, dùng curl)
```bash
bash /tmp/aminra_smoke_test_v2.sh   # 50 case đã viết, < 30s
```

---

## 7. Fixtures & patterns to reuse

### Backend — `backend/tests/conftest.py`
- `client` — session-scoped HTTP client trỏ về `http://localhost:8100`
- `admin_token` — session-scoped JWT của admin, lấy qua `/admin/login` 1 lần
- **Pattern:** tests auth-dependent dùng `client.get("/api/x", headers={"Authorization": f"Bearer {admin_token}"})`

### Frontend E2E — `frontend/aminra-web/e2e/fixtures.ts`
- `biz` — business user register + login tự động, trả `{email, password, token}`
- `prov` — provider user register + admin-approve + login (auto-skip nếu approval fail)
- `admin` — admin token từ `/admin/login`
- `api` — `APIRequestContext` để gọi backend trực tiếp trong E2E

**Pattern:**
```ts
test("Business can list my submissions", async ({ api, biz }) => {
  const r = await api.get("/api/submissions/my-submissions", {
    headers: { Authorization: `Bearer ${biz.token}` },
  });
  expect(r.status()).toBe(200);
});
```

### Playwright config — [`frontend/aminra-web/playwright.config.ts`](frontend/aminra-web/playwright.config.ts)
- Desktop: `1440x900` Chromium
- Mobile: Pixel 5
- Failure artifacts: screenshot + video + trace on retry
- Serial execution (`workers: 1`) để tránh race trong test tạo user

---

## 8. Checklist trước khi merge

Bắt buộc:
- [ ] Test cho code mới (unit nếu pure function, integration nếu workflow)
- [ ] Regression test nếu fix bug
- [ ] Test pass local (`pytest` hoặc `npm run test:e2e`)
- [ ] Không có `skip` / `xfail` / `.only()` / `.fixme()` lẫn trong commit
- [ ] Không hardcode secret / credential / tenant_id trong test

Nice-to-have:
- [ ] Coverage không giảm so với baseline
- [ ] Test chạy < 60s (E2E) hoặc < 5s (unit/integration)
- [ ] Tên test mô tả behavior, không mô tả implementation

---

## 9. When gaps block testing

Nếu user yêu cầu viết test nhưng stack hiện không support (VD: viết async unit test mà chưa có `pytest-asyncio`, viết component test mà chưa có Vitest), **không viết hack workaround**. Thay vào đó:

1. Propose setup dep còn thiếu trong bảng section 3
2. Liệt kê 3-5 test case mục tiêu sẽ viết sau khi có setup
3. Confirm với user trước khi cài dep + viết test

Tránh: viết test không chạy được, hoặc cài dep mà không xin phép.
