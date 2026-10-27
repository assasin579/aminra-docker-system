# AMINRA J1/J2 execution result

**As of:** 2026-10-26 (latest verification run; exact wall-clock not recorded)
**Workspace:** `/home/user/.cache/aminra-dashboard-integrated`
**Branch/base:** `dashboard/execution-2026-10-26` at `4d1ae677598301e62ff6b06208d5c5832c7290f9`
**Scope:** isolated source + task-owned synthetic DB/storage only. No original-checkout writes, push, merge, deploy, shared/runtime DB, or customer-pilot UAT. STOP C and customer-pilot NO-GO remain.

## Overall result

**J1: PARTIAL. J2: PARTIAL. Integrated implementation is not DONE.** Route/service and DB-backed evidence covers substantial slices, but J1-A02 is not accepted: the real upload UI creates a document but does not associate it with the Dossier or exact requirements version. R12's broader browser journey is integrated but most workflow actions are browser-side API calls, not rendered UI interactions. No RLS, runtime/release, or pilot claim.

## Evidence completed in this continuation

- Exercised rendered `/documents` upload UI as synthetic Business A: clicked `Upload tài liệu`, selected `Halal Policy`, selected a synthetic TXT file, and observed the proxied multipart request return HTTP 200 with a document ID and no browser page errors. Follow-up query against the task-owned DB found the row with `dossier_id=NULL`. The page ignores `?dossier=`; this is standalone upload, not Dossier attach or exact-version selection. J1-A02 remains FAIL/PARTIAL.
- Restored only generated `frontend/aminra-web/next-env.d.ts` from the exact branch baseline; `git diff --quiet -- frontend/aminra-web/next-env.d.ts` is clean. SHA-256: `1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b`.
- Current app-role PostgreSQL targeted acceptance: `tests/test_submission_j1_j2_disposable.py` + `tests/test_revision_history_access_contract.py`: **24 passed** (21 + 3), executed inside the task-owned backend container against the task-owned disposable DB. It exercises request/resubmit/history and app-role paths; it is not RLS evidence.
- Related backend regression suite: `tests/test_submission_revisions_unit.py`, `tests/test_submission_state_machine.py`, `tests/test_audit_log_coverage.py`, `tests/test_certificate_pdf_integration.py`, `tests/test_submission_document_lock.py`, `tests/test_cb_performance_90d.py`: **46 passed**.
- Frontend component/SW contract: `npx vitest run __tests__/business-readiness-profiles.test.tsx __tests__/service-worker-dashboard-cache.test.ts --reporter=dot`: **2 files, 9 tests passed**.
- G1 synthetic API-mocked Playwright: `e2e/business-readiness-g1-synthetic.spec.ts`: **2 passed** on `127.0.0.1:31882`. This remains mock acceptance, not backend E2E.
- Synthetic standalone upload browser action: **1 attempted; HTTP 200**, but Dossier association assertion **failed** (`dossier_id=NULL`). Do not count as J1-A02 PASS.
- `npx tsc --noEmit`: PASS (exit 0). Targeted ESLint with `--max-warnings=0`: PASS (exit 0). `git diff --check`: PASS before latest documentation-only edits; rerun as part of handoff.

## Acceptance status and limits

- Requirements publication/version binding, readiness/history snapshots, and route-level authorization have dedicated source/DB evidence recorded in `J1_J2_ACCEPTANCE_MATRIX.md` and canonical checkpoint.
- J1-A02 exact-version Dossier attach/reuse and wrong-tenant denial through the actual upload path remains unmet. DB-fixture SQL attachment is not substitute evidence. D-B's reuse-by-reference decision must be preserved; do not bolt on a single-Dossier FK assumption that blocks reuse.
- J1 submit idempotency/stale/concurrent semantics are not all proven. Request-revision and resubmit idempotency have focused evidence in the checkpoint; do not generalize that to every submit/retry path or the whole J1/J2 acceptance.
- J2 has request/resubmit/round-diff/history and historical file-byte evidence, but overall journey remains PARTIAL pending full acceptance matrix, full-stack UI interactions, and exact access/logging cases where marked not tested.
- R12 local integrated browser run used synthetic bearer/token-enrichment stubs. Requirements setup and Dossier creation plus J1/J2 workflow operations were browser-side `fetch` calls; documents were fixture-seeded/DB-attached. Historical file response was HTTP 200 / 91 bytes with SHA-256 matching the fixture. This is not production OIDC, a full UI journey, or customer UAT.
- Disposable app DB role was non-superuser/no-BYPASSRLS; there were **0 RLS policies**. RLS/Forced-RLS remains NOT TESTED. Runtime/release/pilot remains NOT AUTHORIZED.

## Current verification commands/results

- `docker exec aminra-r12-20261026-api sh -lc 'cd /workspace && pytest tests/test_submission_j1_j2_disposable.py tests/test_revision_history_access_contract.py -q -ra'` — **24 passed**.
- Same container, six related backend test files listed above — **46 passed**.
- `npx vitest run __tests__/business-readiness-profiles.test.tsx __tests__/service-worker-dashboard-cache.test.ts --reporter=dot` — **9 passed**.
- `PW_BASE_URL=http://127.0.0.1:31882 npx playwright test e2e/business-readiness-g1-synthetic.spec.ts --project=desktop-chromium --reporter=line` — **2 passed**.
- `npx tsc --noEmit` — PASS; targeted ESLint — PASS; generated `next-env.d.ts` clean.

## Handoff/lifecycle

- No commit or refreshed baseline-applicable patch yet. Existing `J1_J2_CORRECTIVE_FIXES.patch` is not yet proven current/forward-applicable; do not hand it off as verified.
- Workspace contains unrelated/uncertain dirty entries including `backend/docs/669a5d6a-bb61-4286-bdb0-f2d6c30dac4b/`; do not include or alter it without scope evidence. Checkout original remains untouched.
- Task-owned API container, PostgreSQL container/network, Next dev process and env file still require ownership-verified cleanup after all checks. Do not print or copy credential values.
- Canonical resume point: `J1_J2_CHECKPOINT.md`; matrix: `J1_J2_ACCEPTANCE_MATRIX.md`. Continue with scoped diff review, artifact refresh, local commit or forward-verified patch, then cleanup. No deploy/push/pilot.