# AMINRA Modular Monolith Transition Plan

Date: 2026-09-16
Owner: Khaled + implementation agent
Scope: Convert AMINRA gradually from feature-sliced monolith into a module-composable modular monolith, without moving to microservices.

---

## 1. Goal

Transform AMINRA into a composable module platform where each tenant/business model receives the right set of enabled capabilities:

- Certification dossier / hồ sơ chứng nhận
- Document management
- Traceability / truy xuất nguồn gốc
- Supplier/material management
- Process digitization
- Workforce / nhân sự, auditor, training
- Daily operations / vận hành hằng ngày
- Audit/compliance
- Public QR trace / buyer trust

The runtime remains a modular monolith:

- One main backend service
- One main frontend service
- Existing Keycloak/Postgres/Redis/Qdrant stack
- No microservices in this phase

Success means AMINRA can support multiple business models without hardcoding per-industry code paths or exposing unauthorized modules.

---

## 2. Current Context / Verified Facts

Existing AMINRA already has some foundations:

- `industry_schemas` introduced by `backend/alembic/versions/028_industry_schemas.py`
  - `food_manufacturing`
  - `restaurant_hotel`
  - `livestock_slaughter`
- `standard_types`, `standard_doc_types`, `industry_standards`, `dossiers` introduced by `backend/alembic/versions/029_standard_types_split.py`
- Business owner onboarding selects industry via:
  - Backend: `backend/auth/industry_schema_router.py`
  - Endpoint: `POST /api/industry-schemas/business-select`
- FE already gates some flows on industry selection:
  - `frontend/aminra-web/app/dossiers/new/page.tsx`
  - `frontend/aminra-web/app/dossiers/page.tsx`
  - `frontend/aminra-web/app/create-document/page.tsx`
  - `frontend/aminra-web/app/settings/company/page.tsx`
- Existing domain surfaces:
  - Dossier/document/submission/certification: `backend/auth/*_router.py`, FE `/dossiers`, `/documents`, `/submissions`
  - Traceability/supply-chain: `backend/supply_chain/`, FE `/supply-chain`, `/trace`, `/supplier-portal`
  - Workforce/account-like management: FE `/members`, `/auditors`, backend invite/member/auditor flows
  - Audit/compliance: `backend/auth/audit_router.py`, FE `/audits`

Known architectural weakness:

- Domain routers live under `backend/auth/`, so namespace is misleading.
- Large files exist and should not be expanded further:
  - `backend/app.py` ~1911 lines
  - `frontend/aminra-web/app/upload/page.tsx` ~2701 lines
  - `frontend/aminra-web/app/submissions/page.tsx` ~2331 lines
  - `backend/auth/submission_router.py` ~1596 lines
  - `backend/supply_chain/batch_router.py` ~1295 lines

---

## 3. Target Architecture

### 3.1 Runtime model

Keep modular monolith runtime:

```text
aminra-frontend
aminra-backend
arq-worker
postgres
keycloak
redis
qdrant
```

Do not split into microservices yet.

### 3.2 Code model

Target backend structure:

```text
backend/
  core/
    auth/
    tenant/
    permissions/
    modules/
    audit_log/
    notifications/
  modules/
    certification/
    document_management/
    traceability/
    workforce/
    daily_operations/
    audit_compliance/
    public_trace/
```

Target frontend structure:

```text
frontend/aminra-web/
  features/
    certification/
    document-management/
    traceability/
    workforce/
    daily-operations/
    audit-compliance/
    public-trace/
  app/
    dossiers/
    submissions/
    supply-chain/
    operations/
    audits/
```

Important: route URLs can remain stable during refactor. Internal module folders can change without breaking user-facing URLs.

### 3.3 Product model

Separate these concepts clearly:

1. Business model / industry profile
   - Example: `food_manufacturing`, `restaurant_hotel`, `livestock_slaughter`
2. Certification standard
   - Example: `ms_1500_2019`, `ms_1480_2007`, `mpphm_2020`
3. Module entitlement
   - Example: `traceability`, `daily_operations`, `audit_compliance`
4. Plan/licensing later
   - Example: `starter`, `operations`, `enterprise`

Do not overload `industry_schemas` with every responsibility.

---

## 4. Proposed Data Model Additions

### 4.1 `modules`

Purpose: catalog of AMINRA product modules.

Fields:

```text
id uuid pk
code varchar unique not null
name_vi varchar not null
name_en varchar
category varchar not null
summary text
maturity_level varchar not null default 'beta'
enabled boolean not null default true
display_order int not null default 0
created_at timestamptz not null default now()
updated_at timestamptz not null default now()
```

Initial module codes:

```text
certification_dossier
document_management
supplier_management
traceability
process_digitization
workforce
daily_operations
audit_compliance
public_trace
notifications
```

### 4.2 `business_model_modules`

Purpose: default bundle per business model/industry.

```text
industry_schema_id uuid fk industry_schemas(id)
module_id uuid fk modules(id)
required boolean not null default false
default_enabled boolean not null default true
display_order int not null default 0
config_schema jsonb not null default '{}'
primary key (industry_schema_id, module_id)
```

### 4.3 `tenant_modules`

Purpose: actual enabled modules for each tenant.

```text
tenant_id uuid not null
module_id uuid fk modules(id)
status varchar not null check in ('enabled','disabled','trial','locked')
source varchar not null check in ('business_model_default','admin_override','migration','plan')
config jsonb not null default '{}'
enabled_at timestamptz
disabled_at timestamptz
updated_by uuid references users(id) null
updated_at timestamptz not null default now()
primary key (tenant_id, module_id)
```

### 4.4 `module_dependencies`

Purpose: enforce safe dependency graph.

```text
module_id uuid fk modules(id)
depends_on_module_id uuid fk modules(id)
dependency_type varchar not null check in ('required','optional','enhances')
primary key (module_id, depends_on_module_id)
```

Examples:

```text
public_trace requires traceability
process_digitization enhances traceability
traceability requires supplier_management
```

### 4.5 `module_templates` later

Do not build this in Phase 1 unless needed.

Purpose: workflow/checklist/document templates by module + business model.

```text
module_id uuid
industry_schema_id uuid
template_type varchar -- workflow/checklist/document_set/form_schema
payload jsonb
version int
active boolean
```

---

## 5. Incremental Implementation Plan

## Phase 0 — Baseline and Safety Net

Objective: freeze current behavior with tests before adding module logic.

### Steps

1. Capture current route inventory.
   - Backend routers:
     - `backend/app.py`
     - `backend/auth/*_router.py`
     - `backend/supply_chain/*_router.py`
   - Frontend routes:
     - `frontend/aminra-web/app/*`
2. Identify which routes belong to which future module.
3. Add/verify tests for existing onboarding:
   - Industry list loads.
   - Business owner can select industry once.
   - Non-owner cannot select industry.
   - Existing dossier creation still redirects to industry onboarding when missing.
4. Add a static map document in repo docs:
   - `docs/architecture/module-map.md`

### Files likely to change

```text
docs/architecture/module-map.md
backend/tests/test_industry_onboarding.py
frontend/aminra-web/**/__tests__/*industry* or existing relevant tests
```

### Exit criteria

- Current onboarding tests pass.
- Route-to-module map reviewed.
- No behavior change in production runtime.

---

## Phase 1 — Module Registry DB + Seed Data

Objective: introduce module catalog and default bundles without enforcing access yet.

### Steps

1. Create Alembic migration:
   - `modules`
   - `business_model_modules`
   - `tenant_modules`
   - `module_dependencies`
2. Seed modules.
3. Seed default bundles.

Recommended defaults:

#### `food_manufacturing`

Required/default enabled:

```text
certification_dossier
document_management
supplier_management
traceability
process_digitization
audit_compliance
```

Optional/default disabled or trial:

```text
daily_operations
workforce
public_trace
```

#### `restaurant_hotel`

Required/default enabled:

```text
certification_dossier
document_management
supplier_management
daily_operations
workforce
audit_compliance
```

Optional/default disabled:

```text
traceability
process_digitization
public_trace
```

#### `livestock_slaughter`

Required/default enabled:

```text
certification_dossier
document_management
supplier_management
traceability
process_digitization
workforce
daily_operations
audit_compliance
```

Optional/default disabled initially:

```text
public_trace
```

4. Add data backfill for existing tenants/users with `industry_schema_id`.
5. Backfill `tenant_modules` based on existing selected industry.

### Files likely to change

```text
backend/alembic/versions/0xx_module_registry.py
backend/tests/test_module_registry_migration.py
```

### Exit criteria

- Migration upgrades and downgrades cleanly in test DB.
- Existing tenants get expected `tenant_modules` rows.
- No API behavior change yet.

---

## Phase 2 — Backend Module Service + Read APIs

Objective: expose module state safely to frontend/admin, still without blocking existing flows.

### Steps

1. Add backend module service.

Candidate files:

```text
backend/core/modules/service.py
backend/core/modules/schemas.py
backend/core/modules/router.py
```

If `backend/core/` does not exist yet, create it with small scope only.

2. Add APIs:

```text
GET /api/me/modules
GET /api/modules/catalog
GET /auth/admin/tenants/{tenant_id}/modules
POST /auth/admin/tenants/{tenant_id}/modules/{module_code}/enable
POST /auth/admin/tenants/{tenant_id}/modules/{module_code}/disable
```

3. Add dependency validation before enabling a module.
4. Add audit logs for admin override.

### API contract: `GET /api/me/modules`

Example:

```json
{
  "industry_schema": {
    "code": "food_manufacturing",
    "name_vi": "Cơ sở sản xuất thực phẩm"
  },
  "modules": [
    {
      "code": "certification_dossier",
      "status": "enabled",
      "required": true,
      "source": "business_model_default"
    },
    {
      "code": "traceability",
      "status": "enabled",
      "required": true,
      "source": "business_model_default"
    }
  ]
}
```

### Files likely to change

```text
backend/app.py
backend/core/modules/service.py
backend/core/modules/router.py
backend/core/modules/schemas.py
backend/tests/test_modules_api.py
```

### Exit criteria

- FE can fetch enabled modules for current tenant.
- Admin can enable/disable optional modules with audit log.
- Required modules cannot be disabled.
- Dependencies are enforced at admin API level.

---

## Phase 3 — Onboarding Integration

Objective: when a business selects business model/industry, automatically provision module bundle.

### Steps

1. Update `backend/auth/industry_schema_router.py::select_industry`.
2. After assigning `users.industry_schema_id`, call module service:

```text
provision_default_modules_for_tenant(tenant_id, industry_schema_id)
```

3. Ensure idempotency:
   - If `tenant_modules` already exists, do not duplicate.
   - Do not override admin overrides unless explicitly instructed.
4. Add audit log:
   - `tenant_modules_provisioned`
   - include industry code + enabled modules

### Files likely to change

```text
backend/auth/industry_schema_router.py
backend/core/modules/service.py
backend/tests/test_industry_module_provisioning.py
```

### Exit criteria

- New business owner selecting industry gets expected default modules.
- Existing users still work.
- Duplicate onboarding calls fail/409 as before, without duplicating modules.

---

## Phase 4 — Frontend Module Awareness, No Hard Blocking Yet

Objective: make UI adapt to enabled modules while preserving existing route access until backend guards are ready.

### Steps

1. Add client API:

```text
frontend/aminra-web/lib/modules.ts
```

2. Add hook/provider:

```text
frontend/aminra-web/components/modules/ModuleProvider.tsx
frontend/aminra-web/components/modules/useModules.ts
```

3. Update sidebar/dashboard navigation to use module state.
4. Add locked/upsell placeholder component:

```text
ModuleLockedState
```

5. Map routes to modules:

```text
/dossiers           -> certification_dossier
/documents          -> document_management
/submissions        -> certification_dossier
/supply-chain/*     -> traceability/process_digitization/supplier_management
/members            -> workforce
/auditors           -> workforce/audit_compliance
/audits             -> audit_compliance
/trace              -> public_trace
```

6. For direct navigation to disabled module route, display locked state rather than silent crash.

### Files likely to change

```text
frontend/aminra-web/lib/modules.ts
frontend/aminra-web/components/modules/*
frontend/aminra-web/components/layout/sidebar or equivalent
frontend/aminra-web/app/dashboard/*
frontend/aminra-web/app/supply-chain/*
frontend/aminra-web/app/dossiers/*
```

### Exit criteria

- Sidebar changes by module bundle.
- Direct route to disabled module shows clear locked state.
- No backend enforcement yet, so this phase must not be sold as security complete.

---

## Phase 5 — Backend `require_module()` Guards

Objective: enforce module entitlement server-side.

### Steps

1. Implement backend dependency:

```text
backend/core/modules/dependencies.py
```

Suggested contract:

```python
def require_module(module_code: str):
    ...
```

It must:

- Resolve canonical AMINRA user id/tenant id safely.
- Check `tenant_modules.status in ('enabled','trial')`.
- Fail closed with structured error:

```json
{
  "detail": {
    "code": "MODULE_NOT_ENABLED",
    "module": "traceability"
  }
}
```

2. Add guards route group by route group, not randomly.

Recommended first pass:

```text
backend/supply_chain/*_router.py -> require_module('traceability') or more specific module
backend/auth/dossier_router.py -> require_module('certification_dossier')
backend/auth/document_router.py -> require_module('document_management')
backend/auth/submission_router.py -> require_module('certification_dossier')
backend/auth/audit_router.py -> require_module('audit_compliance')
```

3. Do not guard auth/core endpoints:

```text
/auth/me
/auth/login/SSO callback equivalents
/api/me/modules
industry selection endpoints
notifications maybe core
```

### Files likely to change

```text
backend/core/modules/dependencies.py
backend/supply_chain/supplier_router.py
backend/supply_chain/material_router.py
backend/supply_chain/process_router.py
backend/supply_chain/batch_router.py
backend/auth/dossier_router.py
backend/auth/document_router.py
backend/auth/submission_router.py
backend/auth/audit_router.py
backend/tests/test_module_entitlements.py
```

### Exit criteria

- Disabled module APIs return 403.
- Enabled module APIs still pass existing tests.
- No auth/bootstrap endpoint accidentally blocked.

---

## Phase 6 — Internal Code Refactor: Traceability First

Objective: start real module code organization with the cleanest domain surface.

Traceability is first because it already has a natural folder:

```text
backend/supply_chain/
frontend/aminra-web/app/supply-chain/
frontend/aminra-web/app/trace/
frontend/aminra-web/app/supplier-portal/
```

### Steps

1. Create target backend module:

```text
backend/modules/traceability/
  __init__.py
  router.py
  schemas.py
  supplier_service.py
  material_service.py
  process_service.py
  batch_service.py
  eligibility_service.py
  repository.py
  permissions.py
```

2. Move code gradually:
   - Start by moving shared models/schemas from `backend/supply_chain/models.py`.
   - Then services such as eligibility.
   - Then routers one at a time.
3. Keep existing URL prefix stable:

```text
/api/supply-chain/*
```

4. Keep import compatibility or make small controlled changes.
5. Avoid changing business logic during move.

### Files likely to change

```text
backend/supply_chain/*
backend/modules/traceability/*
backend/app.py
backend/tests/*supply*/*trace*/*batch*
```

### Exit criteria

- No API URL changes.
- Existing traceability tests pass.
- Module guard still works.
- `backend/supply_chain/` either becomes thin compatibility layer or is fully removed after all imports updated.

---

## Phase 7 — Certification/Dossier Module Refactor

Objective: move domain routers out of misleading `auth/` namespace.

### Steps

Move gradually:

```text
backend/auth/dossier_router.py       -> backend/modules/certification/dossier_router.py
backend/auth/submission_router.py    -> backend/modules/certification/submission_router.py
backend/auth/certificate_router.py   -> backend/modules/certification/certificate_router.py
backend/auth/document_router.py      -> backend/modules/document_management/document_router.py
backend/auth/pdf_render_router.py    -> backend/modules/document_management/pdf_render_router.py
```

Keep compatibility:

- API paths unchanged.
- Imports adjusted in `backend/app.py`.
- Avoid changing SQL/business rules during file move.

### Exit criteria

- Domain routers no longer live under `auth/` except true identity/access concerns.
- Certification/document tests pass.
- No public API route changed.

---

## Phase 8 — Build Daily Operations MVP

Objective: add new module that creates daily retention value.

### MVP scope

Backend tables:

```text
daily_operation_templates
daily_operation_runs
daily_operation_tasks
operation_evidence_files
corrective_actions
operation_approvals
```

Backend routes:

```text
GET  /api/operations/today
POST /api/operations/runs
PATCH /api/operations/tasks/{id}
POST /api/operations/tasks/{id}/evidence
POST /api/operations/runs/{id}/submit
POST /api/operations/runs/{id}/approve
```

Frontend routes:

```text
/operations/today
/operations/checklists
/operations/logs
/operations/non-conformances
```

Default templates by business model:

Food manufacturing:

```text
Raw material receiving log
Production batch checklist
Cleaning/sanitation log
Storage temperature log
```

Restaurant/hotel:

```text
Kitchen opening checklist
Supplier delivery check
Staff hygiene checklist
Cleaning/sanitation checklist
```

Livestock/slaughter:

```text
Animal intake checklist
Slaughterman verification
Slaughter process evidence
Cold-chain/storage checklist
```

### Exit criteria

- Module is disabled unless tenant has `daily_operations` enabled.
- Business-model-specific default templates are seeded.
- Evidence + approval is audit logged.
- No impact to certification/traceability core.

---

## 6. Risk Controls

### P0: Do not break existing demo/customer flows

Mitigation:

- Do not change public route URLs in early phases.
- Add module registry read-only before enforcement.
- Introduce guards one route group at a time.
- Maintain rollback path by making guards feature-flagged initially:

```text
MODULE_GUARDS_ENABLED=false/true
```

### P0: Do not rely on frontend-only hiding

Mitigation:

- FE can hide menu for UX.
- BE must enforce `require_module()` before declaring security complete.

### P1: Avoid big-bang refactor

Mitigation:

- Data model first.
- Read APIs second.
- FE awareness third.
- BE enforcement fourth.
- Code movement only after behavior is protected by tests.

### P1: Avoid overfitting every industry

Mitigation:

- Business model controls default modules and templates.
- Shared module code handles common capability.
- Per-industry differences live in config/templates/rules, not separate apps.

### P1: Tenant ID resolution bugs

AMINRA has known Keycloak-sub vs AMINRA-user-id pitfalls.

Mitigation:

- Module service must use existing canonical identity helper patterns.
- Never use Keycloak `sub` directly as AMINRA `users.id`.
- Tests must use live/current auth patterns where possible.

---

## 7. Test Plan

### Backend tests

Add focused tests:

```text
backend/tests/test_module_registry_migration.py
backend/tests/test_modules_api.py
backend/tests/test_industry_module_provisioning.py
backend/tests/test_module_entitlements.py
backend/tests/test_module_dependency_validation.py
```

Required scenarios:

1. Existing tenant backfill gets default modules.
2. New business selecting industry gets module bundle.
3. Required module cannot be disabled.
4. Optional module can be disabled/enabled by admin.
5. Dependency violations are rejected.
6. Disabled module endpoint returns 403.
7. Enabled module endpoint works.
8. Non-owner cannot select industry/module.
9. Audit log records module changes.
10. Existing dossier/submission/traceability flows still pass.

### Frontend tests

Add/extend tests:

```text
frontend/aminra-web/**/modules*.test.tsx
frontend/aminra-web/**/sidebar*.test.tsx
frontend/aminra-web/**/module-locked*.test.tsx
```

Required scenarios:

1. Sidebar shows only enabled modules.
2. Required modules are displayed as active/locked-on.
3. Disabled route shows locked state.
4. Loading/error states are clear.
5. Onboarding redirects still work when industry missing.

### E2E smoke

Minimum browser flows:

1. New business login → select industry → dashboard shows correct modules.
2. Food manufacturing tenant sees traceability.
3. Restaurant/hotel tenant sees daily operations but not slaughter controls.
4. Tenant without public trace cannot access public trace admin controls.
5. Admin enables optional module → user sees it after refresh.

---

## 8. Rollback Strategy

Each phase should be reversible independently.

### DB migration rollback

- Migrations must support downgrade in dev/test.
- Production rollback can disable guards while keeping tables.

### Feature flag rollback

Introduce env/config flag:

```text
MODULE_REGISTRY_ENABLED=true
MODULE_GUARDS_ENABLED=false initially
```

If route guard causes unexpected production issue:

```text
MODULE_GUARDS_ENABLED=false
recreate backend
```

### UI rollback

Keep old static navigation behind fallback until module API is stable.

---

## 9. Suggested Milestones

### Milestone 1 — Planning + registry foundation

Deliverables:

- `docs/architecture/module-map.md`
- Module registry migration
- Seed default bundles
- Backfill existing tenants
- Tests green

### Milestone 2 — Module APIs + onboarding provisioning

Deliverables:

- `GET /api/me/modules`
- Admin enable/disable module APIs
- Industry selection provisions modules
- Audit logs

### Milestone 3 — FE module-aware UX

Deliverables:

- Sidebar/dashboard from module state
- Locked module state
- Route-to-module UX mapping

### Milestone 4 — BE enforcement

Deliverables:

- `require_module()` dependency
- Route group guards
- Entitlement tests
- Feature-flag controlled rollout

### Milestone 5 — Traceability module refactor

Deliverables:

- `backend/modules/traceability/*`
- Stable URLs
- Existing traceability tests pass

### Milestone 6 — Daily Operations MVP

Deliverables:

- Daily ops DB schema
- Daily ops API
- Business-model templates
- FE `/operations/today`

---

## 10. Explicit Non-Goals

Do not do these during this transition:

- Do not split into microservices.
- Do not create separate app per business model.
- Do not change public API URLs unless separately planned.
- Do not bulk move all routers at once.
- Do not enforce module access only in frontend.
- Do not build billing/licensing until module entitlement works.

---

## 11. Final Recommendation

Start with module registry + tenant module entitlement, not file refactor.

Correct order:

```text
1. Define module map
2. Add module tables
3. Provision modules from business model selection
4. Expose /api/me/modules
5. Make FE module-aware
6. Enforce backend require_module()
7. Refactor Traceability code organization
8. Build Daily Operations module
```

This path is careful because it preserves the existing product while creating the foundation for AMINRA to become a composable Halal Operating System.
