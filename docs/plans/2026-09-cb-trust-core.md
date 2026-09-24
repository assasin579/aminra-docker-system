# AMINRA CB Trust Core — Backend Foundation Plan (2026-09)

## Non-negotiable invariants

- Certification bodies must use canonical AMINRA identifiers for authorization and persistence. Do not use JWT `sub` as a database foreign key when a canonical user or tenant id is required.
- Certificate issuance is gated by an approved certification decision for the relevant submission and provider.
- The auditor assigned to a submission or audit visit must not be the decision maker for the certification decision.
- Rejected certification decisions block certificate issuance until superseded by a valid non-cancelled approved case.
- RBAC is default-deny. Unknown actions, unknown roles, missing canonical ids, and missing resource scope deny access.
- Business users must not access provider decision queues or provider-only certification-decision actions.
- Audit logging is required for certification decision creation and final decisions.
- Existing certificate PDF rendering/hash invariance remains untouched.

## Week 1 scope — backend foundation

- Document trust-core invariants and phased scope.
- Add a critical route inventory mapping certificate, submission, audit, and decision endpoints to policy actions.
- Add a lightweight policy service and FastAPI dependency helper with canonical-id based decisions.
- Add a certification decision migration contract for `certification_decisions` plus optional event log table.
- Add service functions to create, read, approve, reject, and gate certificate issuance by certification decisions.
- Add certification-decision routes and wire them into the FastAPI app.
- Gate existing certificate issuance with `assert_certificate_issue_allowed`.
- Cover all of the above with focused tests; do not apply migrations to live DB during Week 1 implementation.

## Week 2 scope summary

- Expand integration coverage against a real test database/schema.
- Add route-level policy dependencies to existing submission/audit/certificate routers where safe.
- Add operational audit views/reporting for certification-decision events.
- Validate end-to-end CB owner/auditor/business workflows in test fixtures.

## Week 3 scope summary

- Harden policy decisions with fuller resource loaders and cross-tenant regression tests.
- Add complaint and appeal workflows to the same policy/action model.
- Add UAT scenarios and UI integration for decision queues.
- Prepare migration rollout notes and production deployment checklist.
