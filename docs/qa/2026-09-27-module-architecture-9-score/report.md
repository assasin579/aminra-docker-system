# Module architecture readiness 9-score evidence

Date: 2026-09-27
Branch: feat/cb-trust-core-rbac-decisions
Scope: multiple module architecture, module guards, module activation, admin/operator module operations.

## Executive verdict

Readiness moved closer to 9/10 for the covered module-architecture lane.

Covered capabilities now have source/test evidence for:
- End-user module overview (`/api/me/modules`, `/modules`, sidebar contract evidence from existing tests/UAT).
- Locked direct-route UX (`ModuleAccessGate` and live UAT evidence from 2026-09-21).
- Backend fail-closed authority for guarded supply-chain modules (`require_module`, route contracts, negative guard tests).
- Admin/operator module management (`/auth/admin/tenants/{tenant_id}/modules`, dependency-safe status changes).
- Activation request workflow (`POST /api/me/module-activation-requests`, admin list/review endpoints).
- SLA/escalation visibility (`sla_state`, notifications, `escalate-overdue` operator action).
- Rollout/runtime safety (`MODULE_GUARDS_ENABLED` plus `MODULE_GUARD_ROLLOUT`; no broad enablement in this task).
- Negative route coverage for guarded route boundaries via backend module guard/route-contract tests.

New gap closed in this pass:
- Admin status changes now maintain the `tenant_modules` timestamp/check-constraint invariant when moving between active (`enabled`/`trial`) and inactive (`disabled`/`locked`) states. This reduces runtime risk for admin activation approvals and manual toggles, especially for disabled/locked rows that previously could be updated to an active state without setting `enabled_at`.

## Exact score gaps found before this pass

1. Admin/runtime configuration safety gap: `set_tenant_module_status()` updated `status` but not `enabled_at`/`disabled_at`, while migration `041_module_registry` requires active rows to have `enabled_at` and inactive rows to have `disabled_at`.
   - Impact: backend admin toggle or activation approval could fail at DB constraint time or leave inconsistent lifecycle timestamps if constraints differ in older sandboxes.
   - Fix: update the management-plane SQL to set/clear lifecycle timestamps atomically with the status change.

2. Remaining production caveats preventing an unconditional 9+/10:
   - Billing/package semantics are still not implemented as authoritative product logic; current entitlements are admin/business-model/module-status primitives.
   - Operator external channel policy remains partial; current notification/escalation is in-app/operator-pool oriented, not external ticketing/SMS/email with owner and retry policy.
   - Broad production rollout of module guards still needs explicit per-route rollout plan, persisted env/config decision, rollback criteria, and live token/browser UAT for each newly enforced module group.
   - SMTP/customer onboarding, edge/CDN SLO, and dependency/security backlog remain project-wide production blockers outside this lane.

## Source changes made

- `backend/auth/module_service.py`
  - Hardened `set_tenant_module_status()` so admin overrides preserve the `tenant_modules` lifecycle invariant:
    - Active statuses (`enabled`, `trial`) set `enabled_at = COALESCE(existing, NOW())` and clear `disabled_at`.
    - Inactive statuses (`disabled`, `locked`) set `disabled_at = COALESCE(existing, NOW())` and clear `enabled_at`.

- `backend/tests/test_module_service.py`
  - Extended the admin override contract to assert timestamp maintenance in the status-update SQL.
  - Added explicit inactive-state regression for `locked` to assert inactive timestamp handling and active timestamp clearing.

## Commands run

1. `pytest backend/tests/test_module_service.py -q`
   - Result: FAIL to execute on host, because `pytest` is not installed in the host shell (`pytest: command not found`). No source failure.

2. `docker compose exec -T aminra-backend pytest tests/test_module_service.py -q`
   - Result: PASS, `19 passed`.
   - Note: existing running container did not include the newly added host test file; used only as baseline/runtime-image signal.

3. `docker compose run --rm -T --no-deps -v /home/user/Documents/aminra-docker-system/backend:/app aminra-backend pytest tests/test_module_service.py -q`
   - Result: PASS, `20 passed`.
   - This mounted the current host backend source into the backend test image and verified the new focused module-service regression.

4. `docker compose run --rm -T --no-deps -v /home/user/Documents/aminra-docker-system/backend:/app aminra-backend pytest tests/test_module_guard.py tests/test_module_route_contract.py tests/test_supply_chain_module_guards.py tests/test_module_registry_migration.py tests/test_module_activation_browser_uat_runner_contract.py -q`
   - Result: FAIL/PARTIAL: `17 passed`, `3 failed`.
   - Failure cause: backend-only bind mount omitted repo-level `scripts/`, so runner-contract tests could not discover the repository root. Not a product/source failure.

5. `docker compose run --rm -T --no-deps -v /home/user/Documents/aminra-docker-system:/repo -w /repo/backend aminra-backend pytest tests/test_module_guard.py tests/test_module_route_contract.py tests/test_supply_chain_module_guards.py tests/test_module_registry_migration.py tests/test_module_activation_browser_uat_runner_contract.py -q`
   - Result: PASS, `20 passed`.
   - This is the valid focused lane gate because the full repository was mounted and runner-contract tests could inspect `scripts/qa/run-module-activation-browser-uat.sh`.

## Pass/fail evidence

PASS:
- Focused module service: `20 passed` with current host source mounted.
- Focused module architecture/guard/route/activation runner contracts: `20 passed` with full repo mounted.
- No deploy, push, broad package upgrade, destructive cleanup, or chaos action was performed.

Expected/benign failure:
- Host shell has no `pytest` binary.
- Backend-only bind mount is unsuitable for tests that must read repo-level `scripts/`; rerun with full repo mount passed.

## Residual risks

- Production scoring should remain caveated unless billing/package semantics are made explicit and authoritative.
- External operator escalation channel is not production-grade yet; in-app notification/escalation evidence is strong for sandbox/local operator workflow only.
- Frontend locked-route wrappers are UX only; backend `require_module` remains the security boundary.
- Broadly enabling all module guards without `MODULE_GUARD_ROLLOUT`, live-token UAT, and rollback criteria remains unsafe.
- Existing working tree contains unrelated changes from other lanes; this task intentionally changed only module-service source/tests plus this QA report.

## Exact next step

Run a DB-backed admin activation smoke in the sandbox after rebuild/recreate: start with a disabled module row, call admin `PATCH /auth/admin/tenants/{tenant_id}/modules/{module_code}` to `trial`, then back to `locked`, and assert `tenant_modules.enabled_at/disabled_at` transitions satisfy the migration check constraint. Do this only under approved backend deploy/runtime validation lane.

## Safety-blocked items

- No production deploy or broad `MODULE_GUARDS_ENABLED=true` rollout was attempted.
- No billing/package model implementation was attempted because product semantics are unresolved.
- No external operator channel integration was attempted because provider/channel policy is unresolved.
- No destructive cleanup, chaos, package audit fix, commit, push, or deploy was performed.
