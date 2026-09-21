# 2026-09-21 — Module Activation Operator Escalation

## Scope

Add operator-triggered escalation for pending module activation requests that have breached SLA.

## Success criteria

- Backend policy finds pending overdue activation requests without approving entitlements.
- Escalation marks requests `urgent`, increments `escalation_count`, sets `last_escalated_at`, assigns the first active provider/operator when available, and creates in-app operator notifications.
- Admin API exposes `POST /api/auth/admin/module-activation-requests/escalate-overdue` through the existing admin router.
- Admin Tenant module console can trigger escalation for the current tenant, updates the queue from the response, and surfaces visible success/state feedback.
- Migration adds escalation metadata safely and preserves rollback.

## Changed files

- `backend/alembic/versions/046_module_activation_operator_escalation.py`
- `backend/auth/module_service.py`
- `backend/auth/module_router.py`
- `backend/tests/test_module_service.py`
- `frontend/aminra-web/components/AdminModuleManager.tsx`
- `frontend/aminra-web/__tests__/admin-module-manager-contract.test.tsx`

## Verification

- Backend focused service regression:
  - Command: `uv run --with asyncpg --with pytest-asyncio --with fastapi --with httpx pytest backend/tests/test_module_service.py -q`
  - Result: `19 passed`
  - Note: pytest cache write warning due local `.pytest_cache` permission; test result passed.
- Frontend focused contract:
  - Command: `npm test -- --run __tests__/admin-module-manager-contract.test.tsx`
  - Result: `5 passed`
- Frontend lint:
  - Command: `npm run lint -- --quiet`
  - Result: PASS
- Backend lint:
  - Command: `uv run --with ruff ruff check backend/auth/module_service.py backend/auth/module_router.py backend/alembic/versions/046_module_activation_operator_escalation.py backend/tests/test_module_service.py`
  - Result: PASS
- Frontend production build:
  - Command: `npm run build`
  - Result: PASS; existing Sentry/Next deprecation warnings only.
- Diff hygiene:
  - Command: `git diff --check`
  - Result: PASS

## Verdict

- Source/build verification: PASS for focused operator escalation slice.
- Runtime/DB migration/UAT deploy: NOT RUN in this turn.
- Production/customer-pilot: still PARTIAL until migration is applied to the running sandbox, admin-token runtime smoke confirms the route end-to-end, and real operator channel policy is chosen if escalation must leave the in-app notification table.
