# AMINRA J1/J2 execution evidence index

**Canonical checkpoint (resume source):** `/home/user/.cache/aminra-dashboard-integrated/verification/dashboard-execution-2026-10-26/J1_J2_CHECKPOINT.md`

**Current status refreshed 2026-10-26 19:11 -04:00.** Two J2 defects are repaired and evidenced by disposable app-role RED/GREEN tests: pinned requirements fields in `resubmit()`; historical submitted-document retrieval via immutable round snapshot in the actual `FileResponse` route. Current app-role DB + revision-history test run: **8 passed**. Browser mock: **2 passed**; component race/SW: **9 passed**. TypeScript, targeted ESLint and `git diff --check` PASS.

**Acceptance remains PARTIAL/BLOCKED, not DONE:** idempotency/stale/concurrent semantics required by spec have no J1/J2 `Idempotency-Key` implementation and are not tested; local FE→backend→DB/storage browser journey is not run; OIDC/download logging/RLS/runtime/pilot are not evidenced. STOP C and customer-pilot NO-GO remain.

Artifacts: `J1_J2_CHECKPOINT.md` (canonical), `J1_J2_ACCEPTANCE_MATRIX.md`, `J1_J2_EXECUTION_RESULT.md`, `J1_J2_CORRECTIVE_FIXES.patch`. The corrective patch reverse-checks against current source. Workspace contains unrelated dirty/untracked entries; no commit/staging/push/deploy.

DB test run `20261026-848feaea` is cleaned after its final **8 passed** app-role test run. Exact container/network and mode-0600 env files were removed; task-owned Next PIDs stopped and port closure verified. `e04_full`, its unrelated DB container/volume, and any unowned process were untouched.
