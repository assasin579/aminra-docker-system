# AMINRA Module Map

Status: Phase 0 baseline for modular monolith transition
Date: 2026-09-16

## Purpose

AMINRA is moving toward a composable modular monolith: tenants select a business model/industry, and AMINRA provisions the correct module bundle without splitting into microservices.

This map is the source of truth for Phase 1 module registry seed data and later backend `require_module()` guards.

## Module catalog

### Core platform modules

- `notifications`: in-app/web-push/email notification capability.

### Business modules

- `certification_dossier`: dossier, submission, review, revision, certification workflow.
- `document_management`: document upload, template/PDF rendering, document versioning.
- `supplier_management`: suppliers, supplier certificates, certificate risk alerts, supplier portal intake.
- `traceability`: materials, batches, batch steps, sealing, trace data.
- `process_digitization`: production/service process definitions and step workflows.
- `workforce`: business members, provider auditors, internal role assignment, later training/competency.
- `daily_operations`: daily checklists/logs, corrective actions, approvals. New module; not yet fully implemented.
- `audit_compliance`: audit templates, audit visits, findings/evidence, compliance checks.
- `public_trace`: public QR/trace pages from sealed trace snapshots.

## Default bundles by current business model

### `food_manufacturing`

Required/default enabled:

- `certification_dossier`
- `document_management`
- `supplier_management`
- `traceability`
- `process_digitization`
- `audit_compliance`
- `notifications`

Optional/default disabled:

- `daily_operations`
- `workforce`
- `public_trace`

Rationale: food manufacturers need supplier/material/process/batch traceability as part of Halal assurance. Daily operations and workforce training are high-value but can be activated after the certification path is stable.

### `restaurant_hotel`

Required/default enabled:

- `certification_dossier`
- `document_management`
- `supplier_management`
- `daily_operations`
- `workforce`
- `audit_compliance`
- `notifications`

Optional/default disabled:

- `traceability`
- `process_digitization`
- `public_trace`

Rationale: restaurants/hotels need daily kitchen/sanitation/staff/supplier operations more than full production-batch traceability. Traceability can be activated as a lighter or premium capability later.

### `livestock_slaughter`

Required/default enabled:

- `certification_dossier`
- `document_management`
- `supplier_management`
- `traceability`
- `process_digitization`
- `workforce`
- `daily_operations`
- `audit_compliance`
- `notifications`

Optional/default disabled:

- `public_trace`

Rationale: slaughter operations need strict personnel qualification, process evidence, traceability, and daily operational controls. Public trace should wait until sealed snapshot governance is production-ready.

## Dependency map

- `traceability` requires `supplier_management`.
- `public_trace` requires `traceability`.
- `process_digitization` enhances `traceability` but is not a hard prerequisite at DB level.
- `daily_operations` enhances `workforce` for training/assignment workflows, but should not require it yet because restaurant/hotel daily checklist MVP can run with owner-level accounts.

## Current route ownership baseline

### Certification / dossier

Backend:

- `backend/auth/dossier_router.py`
- `backend/auth/submission_router.py`
- `backend/auth/certificate_router.py`

Frontend:

- `frontend/aminra-web/app/dossiers/`
- `frontend/aminra-web/app/submissions/`
- `frontend/aminra-web/app/certificates/`

Future module: `certification_dossier`

### Document management

Backend:

- `backend/auth/document_router.py`
- `backend/auth/pdf_render_router.py`
- `backend/services/document_versioning.py`
- `backend/services/pdf_*`

Frontend:

- `frontend/aminra-web/app/documents/`
- `frontend/aminra-web/app/upload/`
- `frontend/aminra-web/app/create-document/`

Future module: `document_management`

### Supplier / traceability / process

Backend:

- `backend/supply_chain/supplier_router.py`
- `backend/supply_chain/material_router.py`
- `backend/supply_chain/process_router.py`
- `backend/supply_chain/batch_router.py`
- `backend/supply_chain/eligibility_service.py`

Frontend:

- `frontend/aminra-web/app/supply-chain/`
- `frontend/aminra-web/app/trace/`
- `frontend/aminra-web/app/supplier-portal/`

Future modules: `supplier_management`, `traceability`, `process_digitization`, `public_trace`

### Workforce

Backend:

- Member/auditor invite/account flows currently live mostly in `backend/auth/router.py` and admin routes.

Frontend:

- `frontend/aminra-web/app/members/`
- `frontend/aminra-web/app/auditors/`
- `frontend/aminra-web/app/invite/`

Future module: `workforce`

### Audit / compliance

Backend:

- `backend/auth/audit_router.py`
- `backend/auth/audit_log_router.py`

Frontend:

- `frontend/aminra-web/app/audits/`
- `frontend/aminra-web/app/admin/audit-logs/`

Future modules: `audit_compliance`; audit logs remain core platform.

## Guard rollout policy

Phase 1 only adds registry tables and seed data. It must not block existing routes.

Backend `require_module()` enforcement comes later and must be feature-flagged initially.

Do not rely on frontend menu hiding as a security boundary.
