# AMINRA Module Activation Request Workflow — QA Report

Date: 2026-09-21
Repo: `/home/user/Documents/aminra-docker-system`
Branch: `dev`
Verdict: **GO for local sandbox P1 activation-request workflow**; **PARTIAL for production/customer pilot** until real credentials-backed browser UAT and notification/SLA policy are added.

## Scope / Acceptance Criteria

P1 delivered a safe request-to-review workflow for locked modules:

1. Business user on a locked direct route can submit an activation request.
2. Duplicate pending requests for the same tenant/module are idempotent.
3. Active modules reject activation requests with `MODULE_ALREADY_ACTIVE`.
4. Admin/operator can list pending requests by tenant.
5. Admin/operator can approve or reject a request.
6. Approve moves tenant module to `trial`; reject does not change module entitlement.
7. Backend remains authority; client CTA only creates requests, never bypasses module guards.

## Implementation Summary

### Backend

- Added Alembic migration:
  - `backend/alembic/versions/044_module_activation_req.py`
- Added `module_activation_requests` table with:
  - tenant/module references
  - pending/approved/rejected/cancelled status
  - requester metadata
  - admin review metadata
  - partial unique index for one pending request per tenant/module
- Added service functions:
  - `create_module_activation_request`
  - `list_module_activation_requests`
  - `review_module_activation_request`
- Added API routes:
  - `POST /api/me/module-activation-requests`
  - `GET /auth/admin/module-activation-requests`
  - `PATCH /auth/admin/module-activation-requests/{request_id}`

### Frontend

- `ModuleAccessGate` CTA now submits a real activation request and displays success/error state.
- `AdminModuleManager` can load pending activation requests and approve/reject them from Tenant module console.

## Verification

### Automated tests

PASS:

- Backend focused module tests:
  - `21 passed`
- Phase-gate backend module suite:
  - `32 passed`
- Frontend focused module tests:
  - `16 passed`
- Phase-gate frontend suite:
  - `12 passed`
- Frontend lint:
  - PASS
- Frontend production build:
  - PASS, with pre-existing Sentry/Next warnings
- `git diff --check`:
  - PASS

### Deploy / migration

PASS:

- Immutable deploy gate completed:
  - Evidence: `docs/qa/20260921-014758-module-activation-request-deploy/`
- Migration applied after container recreate:
  - Current revision: `044_module_activation_req (head)`
  - Table exists: `module_activation_requests`

### DB-backed workflow UAT

PASS:

- Created pending activation request for demo tenant/module.
- Listed pending review queue.
- Rejected request to avoid changing demo tenant entitlements.
- Verified pending queue returned to zero.
- Evidence: `docs/qa/20260921-015654-module-activation-request-db-uat/service-db-uat.json`

### Browser UAT

BLOCKED / PARTIAL:

- Playwright multi-project run failed for Firefox/WebKit because browser binaries are not installed locally.
- Chromium-only run skipped because no business demo password is configured in `.env` / vault env for this shell.
- This is an environment credential/browser-runtime gap, not a product-code regression.
- Evidence:
  - `docs/qa/20260921-015433-module-activation-request-live-uat/`
  - `docs/qa/20260921-015613-module-activation-request-live-uat-chromium/`

## Risks / Remaining Gaps

- No email/Slack/Telegram notification to operators when a request is submitted.
- No SLA, ownership, or escalation policy for pending activation requests.
- Admin approve sets module to `trial`; pricing/billing entitlement integration is still future work.
- Browser UAT needs seeded credentials available to CI/sandbox and Playwright browser binaries installed or project-filtered.

## Decision

- **GO**: merge/use in local sandbox for P1 activation-request workflow.
- **PARTIAL**: not yet customer-pilot complete until browser UAT credential gap and operator notification/SLA are resolved.
