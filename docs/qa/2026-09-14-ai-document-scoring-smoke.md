# AMINRA AI Document Scoring Smoke Check — 2026-09-14

## Verdict

**BLOCKED for end-to-end UI/API production-like use.**

The internal scoring pipeline can extract text, build prompt context, call a mocked LLM, parse `criteria_scores`, and recalculate `compliance_score`. However the production-like `/api/documents/upload` → `/api/documents/{id}/evaluate` flow is currently blocked by DB/user identity mismatch and missing runtime LLM provider configuration.

## Scope

Checked function: AI document scoring for AMINRA document upload/evaluation.

Key code paths:

- Backend evaluator: `backend/pipeline/evaluate.py`
- Legacy direct API: `POST /evaluate` in `backend/app.py`
- Documents UI/API flow: `backend/auth/document_router.py`
  - `POST /api/documents/upload`
  - `POST /api/documents/{doc_id}/evaluate`
- Frontend entry point: `frontend/aminra-web/app/documents/page.tsx`

## Evidence

### 1. Runtime health

- `GET http://127.0.0.1:8100/health`: PASS
  - service ok
  - database connected
  - qdrant connected

### 2. LLM provider config

Inside `aminra-backend` container:

- `OPENROUTER_API_KEY`: missing or placeholder
- `DEEPSEEK_API_KEY`: missing or placeholder
- `LLM_BASE_URL`: missing or placeholder
- `OPENROUTER_MODEL`: missing or placeholder

Impact: real AI evaluation cannot complete reliably; `evaluate_document()` raises `ValueError("LLM evaluation failed: ...")` if OpenRouter and DeepSeek both fail.

### 3. Internal evaluator smoke — mocked LLM

Command: in-container Python smoke with monkeypatched `pipeline.evaluate.call_llm_json`.

Result: PASS

Observed:

- text extraction succeeded
- forced `doc_type=halal_policy` preserved
- prompt includes scoring instructions and criteria
- `criteria_scores` parsed
- intentionally wrong LLM `compliance_score=12` was recalculated to `90`
- `signature_detection` key present

Key output:

```json
{
  "status": "PASS",
  "checks": {
    "filename": "halal_policy_test.txt",
    "doc_type": "halal_policy",
    "word_count": 51,
    "standards_found": 0,
    "compliance_score": 90,
    "overall_status": "compliant",
    "criteria_count": 5,
    "has_extracted_text": true,
    "has_signature_detection": true
  }
}
```

### 4. Legacy `/evaluate` route smoke — mocked evaluator

Used `fastapi.testclient` with mocked auth/evaluator.

Result: PASS with caveat.

Observed:

- endpoint accepts upload and `doc_type=halal_policy`
- `previous_context` sanitization strips hostile delimiters (`===`, `[SYSTEM]`, `<|`)
- returns expected scoring shape

Caveat:

- container's `/app/admin_templates/halal_policy.json` has **empty** `mandatory_criteria`, unlike host repo file under `/home/user/Documents/aminra-docker-system/backend/admin_templates/halal_policy.json`, which has 5 criteria. This indicates runtime/admin template drift.

### 5. Documents UI/API flow — live upload smoke

Attempted business-user login via Keycloak with forwarded issuer headers.

- token grant: PASS
- `POST /api/documents/upload`: FAIL 500

Backend log root cause:

```text
asyncpg.exceptions.ForeignKeyViolationError:
insert or update on table "documents" violates foreign key constraint "documents_user_id_fkey"
DETAIL: Key (user_id)=(70772b1a-c8db-4f13-9e0e-69c87571f7eb) is not present in table "users".
```

DB inspection shows `biz-demo-1@demo.aminra.vn` has:

- `users.id` prefix: `6eb82c5e`
- `users.keycloak_sub` prefix: `70772b1a`

The upload route inserts `user["sub"]` into `documents.user_id`, but FK references `users.id`. This blocks the user-facing document scoring flow before scoring starts.

### 6. Upload validation tests

Command: `docker compose exec -T aminra-backend pytest -q tests/test_upload_validation.py`

Result: PASS/WARN

- `1 passed`
- `1 skipped`

## Findings

### PASS

- Core `evaluate_document()` algorithmic path works under mocked LLM.
- Score recalculation from `criteria_scores` works and prevents LLM from fabricating total score.
- Basic upload validation tests pass.
- Health endpoint shows backend, DB, and Qdrant connected.
- Legacy direct `/evaluate` route sanitizes `previous_context` and can return scoring-shaped output under mock.

### WARN

- Runtime template drift: container `/app/admin_templates/halal_policy.json` has empty `mandatory_criteria`, while host repo file has 5 criteria. Scoring quality will be weak/undefined if runtime template is authoritative.
- `halal_policy` template reference file exists in runtime under `admin_templates/files/halal_policy/halal_policy_vi.docx`, but legacy `/evaluate` strict lang lookup expects `files/halal_policy/vi/*`; current layout may result in `template_files_content_len=0` for that route.
- Direct `/evaluate` route appears legacy; frontend Documents page uses `/api/documents/upload` and `/api/documents/{id}/evaluate`.

### BLOCKED

- Real AI call unavailable: no provider API key/base/model configured in backend runtime.
- User-facing upload/evaluate flow blocked by FK identity mismatch: `documents.user_id` receives Keycloak `sub` instead of canonical `users.id`.

## Recommended fixes

### P0 — unblock user-facing scoring

1. Fix documents upload identity mapping:
   - In `backend/auth/document_router.py`, `upload_document()` should persist canonical DB user id, not raw Keycloak `sub`.
   - Use existing identity resolver or DB lookup by `keycloak_sub`.
   - Apply same audit to any other insert into FK `documents.user_id`.

2. Configure LLM runtime provider:
   - set valid `OPENROUTER_API_KEY` + `OPENROUTER_MODEL`, or valid DeepSeek fallback config.
   - do not commit secrets.
   - verify container env after restart.

3. Sync/admin-template runtime data:
   - ensure runtime `admin_templates/halal_policy.json` contains intended criteria or use persisted/admin-managed template source of truth.
   - normalize reference file layout to strict `files/<doc_type>/<lang>/...` where relevant.

### P1 — harden tests

1. Add regression test for `documents.user_id` canonical mapping:
   - user token `sub != users.id`
   - upload succeeds
   - DB `documents.user_id == users.id`

2. Add evaluator no-provider test:
   - missing OpenRouter/DeepSeek returns controlled error/status, not silent partial state.

3. Add integration test for `/api/documents/upload` → `/api/documents/{id}/evaluate` with mocked LLM and real DB.

## Final status

- Internal scoring pipeline: **PASS under mocked LLM**
- User-facing API/UI flow: **BLOCKED**
- Real AI scoring: **BLOCKED by missing provider config**
- Production readiness: **NO-GO**
