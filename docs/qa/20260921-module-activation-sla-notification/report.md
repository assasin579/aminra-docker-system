# AMINRA Module Activation SLA + Operator Notification — QA Report

Date: 2026-09-21
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `dev`
Verdict: **GO for local sandbox operator-visible SLA/notification metadata**; **PARTIAL for customer-pilot** until browser-login UAT credentials and operator notification channel policy are finalized.

## Scope / Acceptance Criteria

P1 objective: make module activation requests operationally actionable for admins/operators.

Accepted behavior:

1. Every new pending module activation request has SLA metadata:
   - `priority`, default `normal`
   - `sla_due_at`, default create time + 24 hours
   - `sla_state`: `open`, `overdue`, or `closed`
   - `hours_until_due`
2. Backend creates platform-operator notifications when a request is created.
   - Current DB projection represents platform admins as active `provider` users.
   - Avoids invalid enum comparisons against `user_role` values not present in Postgres.
3. Admin review queue exposes notification/SLA fields and orders overdue pending requests first.
4. Admin UI shows operator-visible SLA/notification cues:
   - `Quá hạn SLA`
   - notification count
   - priority
5. Existing module guard, activation request, and admin module behavior stays green.

## Implementation Summary

Changed files:

- `backend/alembic/versions/045_module_activation_sla.py`
- `backend/auth/module_service.py`
- `backend/tests/test_module_service.py`
- `frontend/aminra-web/components/AdminModuleManager.tsx`
- `frontend/aminra-web/__tests__/admin-module-manager-contract.test.tsx`

Runtime schema:

- Alembic current: `045_module_activation_sla (head)`
- Added columns on `module_activation_requests`:
  - `priority`
  - `sla_due_at`
  - `first_notified_at`
  - `last_notified_at`
  - `notification_count`

## Evidence

Focused/manual gates:

- Backend focused module regression: `29 passed`
- Frontend focused module regression: `16 passed`
- Frontend lint: PASS
- Frontend production build: PASS

Immutable deploy evidence:

- Final deploy evidence: `docs/qa/20260921-023028-module-activation-sla-final-deploy/`
- Deploy gate backend suite: `34 passed`
- Deploy gate frontend suite: `12 passed`
- Alembic graph smoke: `045_module_activation_sla (head)`
- Local health: PASS
- Public smoke: `aminra.org HTTP 200`, business login HTTP 200
- Stability loop: 6/6 healthy

DB-backed UAT evidence:

- Final DB UAT: `docs/qa/20260921-023315-module-activation-sla-final-db-uat/result.json`

Observed final DB UAT result:

```json
{
  "created_status": "pending",
  "sla_state": "open",
  "has_sla_due_at": true,
  "notification_count_payload": 4,
  "notifications_delta": 4,
  "queue_count": 1,
  "queue_first_sla_state": "open",
  "queue_first_notification_count": 4
}
```

## Risks / Caveats

- Notification is currently in-app DB notification only; no email/Telegram/operator webhook yet.
- Operator audience is active `provider` rows because the local Postgres `user_role` enum only contains `business` and `provider`; platform-admin authority is Keycloak-side, not stored as a Postgres enum value.
- Browser UAT remains blocked by lack of safe demo credentials in current shell/vault context.
- No billing/package SLA policy yet; approval still grants `trial` status.

## Verdict

**GO for local sandbox P1 SLA + in-app operator notification metadata.**

Not yet a production/customer-pilot GO until:

1. Operator notification channel policy is confirmed.
2. Browser E2E credentials are safely seeded.
3. Billing/package entitlement semantics are defined.
