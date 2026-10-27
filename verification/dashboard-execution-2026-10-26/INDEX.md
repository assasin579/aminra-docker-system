# AMINRA J1/J2 execution evidence index

**Canonical checkpoint:** `J1_J2_CHECKPOINT.md`
**Current acceptance matrix:** `J1_J2_ACCEPTANCE_MATRIX.md`
**Execution result:** `J1_J2_EXECUTION_RESULT.md`
**Task graph:** `J1_J2_TASKS.md`

**Current continuation (2026-10-27):** closeout commit `147f4a87014cc0341f938e11a76b2b216f9e4269` records the API restart, direct file HTTP+hash check, scoped lifecycle/app-role tests, current G1 browser rerun, and evidence logs. Tests ran on identical source precommit; no push. Current acceptance closes J1-A08, J2-A06, X-A01, X-A02 and X-A04 at synthetic/local boundaries; J1-A01 and J1-A03 remain NOT VERIFIED. Alembic heads 053/055 were read from DB as `a02_app`; CLI `alembic current` lacks psycopg in runtime image. Overall PARTIAL.

**Status: J1/J2 PARTIAL, not DONE.** No R1–R12 J1/J2 mapping in the supplied approved source; use as cross-reference only. RLS/Forced-RLS NOT TESTED (0 policies). Runtime/release/customer-pilot remain unauthorized; STOP C and customer-pilot NO-GO remain.

**Scoped code commits before this closeout:** A02 upload binding `8e0e718`, revision history/diff `28bbaf1`, and acceptance closeout `147f4a8` (all local/unpushed). Confirmed task-owned API/DB/proxy/Next/storage resources were stopped/removed after evidence capture; other similarly named older containers and untracked working-tree WIP were left untouched. No original-checkout writes.