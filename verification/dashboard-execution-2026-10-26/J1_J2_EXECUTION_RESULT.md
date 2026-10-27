# AMINRA J1/J2 execution result

**As of:** 2026-10-27 post-restart lifecycle and acceptance rerun.
**Workspace:** `/home/user/.cache/aminra-dashboard-integrated`
**Branch/HEAD before closeout commit:** `dashboard/execution-2026-10-26`, code HEAD `28bbaf11cc6c03bc3995a4598f404224cb4c226b`; current working tree has reviewed pending changes in document download lifecycle, one direct-file HTTP assertion, test fixture exception type, matrix/checkpoint/evidence. Fresh status/diff review still required before commit.
**Scope:** isolated source + task-owned synthetic DB/storage only. No original-checkout writes, push, merge, deploy, shared/runtime DB, or customer-pilot UAT. STOP C and customer-pilot NO-GO remain.

## Latest result

**VERDICT: PARTIAL.** Current evidence closes J1-A08, J2-A06, X-A01, X-A02 and X-A04 at scoped synthetic boundaries. J1-A01 and J1-A03 remain NOT VERIFIED; see exact matrix gaps. The integrated Playwright journey passed 1/1 after API restart and now includes direct `/documents/{id}/file` HTTP 200 + browser-read SHA-256 match; API-mocked G1 Playwright passed 2/2. App-role disposable DB suite passed 26/26, frontend Vitest 24/24, TypeScript, scoped ESLint and diff checks passed. X-A02 uses legacy UNKNOWN/no-backfill, current Alembic heads read from DB, and prior guarded non-destructive downgrade rehearsal; no evidence was deleted and guard was not bypassed. `alembic current` CLI in this runtime image failed because `psycopg` is absent, but direct app-role DB query confirmed heads `053_audit_report_acceptance` and `055_dossier_document_attachments`. Exact rerun commands and logs are documented below and in `J1_J2_CHECKPOINT.md` / `J1_J2_ACCEPTANCE_MATRIX.md`. R1–R12 remains cross-reference-only; no mapping in reviewed approved source. No RLS, OIDC, release or pilot claim.

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

- Scoped local commit `91fe318aafca38ab31a556f1b457680aeca43d31` is an exact child of baseline `4d1ae677598301e62ff6b06208d5c5832c7290f9`; it includes 46 reviewed files and was not pushed. Existing `J1_J2_CORRECTIVE_FIXES.patch` is unverified and superseded.
- Remaining untracked entries include the confirmed UI-upload synthetic file (remove during cleanup), `frontend/aminra-web/e2e/cb-dashboard-synthetic.spec.ts`, and the old patch; those were excluded as unreviewed/out-of-scope. Checkout original remains untouched.
- Task-owned API container, PostgreSQL container/network, Next dev process, env file and synthetic upload file still require cleanup/absence verification. Never print or copy credential values.

## 2026-10-27 acceptance closeout evidence (supersedes interim statuses above)
- Final DB command: `docker exec aminra-a02-provider-20261027 sh -lc 'cd /app && J1J2_APP_ROLE=a02_app pytest -vv -s tests/test_submission_j1_j2_disposable.py'` — **26 passed**, PostgreSQL disposable DB, current_user `a02_app` (non-superuser/no BYPASSRLS). Log `evidence/2026-10-27-a02-app-role-final.log`, SHA-256 `a847fd18b99d9fbea4217cc38ff1b96fbf3ab35d9b631bd793980e07b9a8ab95`.
- API restart: `docker restart aminra-a02-provider-20261027`; then `curl http://127.0.0.1:18100/health` returned status `ok`, database `connected`. Only task-owned synthetic API restarted.
- Full journey after restart: `PW_BASE_URL=http://127.0.0.1:18201 npx playwright test e2e/a02-full-j1-j2-journey.spec.ts --project=desktop-chromium --reporter=line`; **1 passed**, run `31e413a7-f20e-4969-a098-7c6bf994f340`. Added direct `/api/api/documents/{id}/file` GET: HTTP 200, browser-read bytes SHA-256 equal uploaded fixture; no client-disk/persistence claim. Log `evidence/2026-10-27-j1j2-direct-file-http.log`, SHA-256 `5636bfd3ad334f308e6a85937fada5eb9582f0e67a742dd1e2a48faa6da7e5d4`.
- Current G1: `PW_BASE_URL=http://127.0.0.1:18201 npx playwright test e2e/business-readiness-g1-synthetic.spec.ts --project=desktop-chromium --reporter=line`; **2 passed**, API-mocked UI only. Log `evidence/2026-10-27-g1-browser-final.log`, SHA-256 `bf1d5242c437db836a4ebc13e5d15343dce93737460b94dbeea3f6b1635c64cf`.
- Frontend: `npx tsc --noEmit --pretty false`; `npx eslint e2e/a02-full-j1-j2-journey.spec.ts e2e/business-readiness-g1-synthetic.spec.ts --max-warnings=0`; `npx vitest run __tests__/business-readiness-profiles.test.tsx __tests__/service-worker-dashboard-cache.test.ts __tests__/revision-panel.test.tsx --reporter=dot` (**24 passed**); `git diff --check` — all pass.
- X-A02 exact evidence: legacy fixture stays `requirements_binding_status=unknown`, no version, readiness UNKNOWN/reason `requirements_version_unknown_no_backfill`; current `alembic_version` queried as `a02_app` returned `053_audit_report_acceptance` and `055_dossier_document_attachments`; prior downgrade with durable evidence was safely refused, heads unchanged. `alembic current` CLI failed only because this runtime image lacks `psycopg`; no downgrade bypass or evidence deletion.
- X-A04 exact test `test_requirements_publication_authority_snapshot_immutability_and_rollback` passed: unauthorized publication 403; authorized versions 2/3; first version/slots immutable; triggers reject mutation; invalid actor FK rolls back version/current pointer/audit. Test exception is `asyncpg.exceptions.RaiseError`.
- Current source SHA-256: `backend/auth/document_router.py` `d65d6659e89f0b347d189932d90de25fa2238d35b2bdd90b43b38ad7cc7375b3`; `backend/tests/test_submission_j1_j2_disposable.py` `1d78190f0010daba66d4064f404deffd53d760822738cc39bdb431c6e18a3611`; `frontend/aminra-web/e2e/a02-full-j1-j2-journey.spec.ts` `02c668e4816a142902ed96f825c77d0185d7ccca7ab9a3f96d2d06da5fba44de`.
- Current matrix closes J1-A08/J2-A06/X-A01/X-A02/X-A04 scoped PASS. Overall PARTIAL due J1-A01 and J1-A03 NOT VERIFIED; no inferred R1–R12 gate. Closeout source/docs/evidence remain to be scoped-committed and task-owned resources verified/cleaned.
- Canonical resume point: `J1_J2_CHECKPOINT.md`; matrix: `J1_J2_ACCEPTANCE_MATRIX.md`. Immediate closeout: cleanup verified task-owned resources, record their absence, and keep J1-A02/J1/J2 PARTIAL until missing acceptance has genuine evidence. No deploy/push/pilot.