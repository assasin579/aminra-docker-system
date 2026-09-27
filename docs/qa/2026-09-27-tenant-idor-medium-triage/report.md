# Tenant/IDOR MEDIUM scanner triage — 2026-09-27

## Verdict

Static scanner produced review prompts, not confirmed vulnerabilities. HIGH findings are zero. MEDIUM findings remain bounded by route inventory, expanded anonymous boundary tests, and focused route-family regressions; they are not a release blocker for the requested source/evidence 9/10 gate, but they remain P1 hardening backlog before unsupervised customer pilot.

## Counts

- Total findings: 189
- By severity: {'INFO': 8, 'MEDIUM': 181}
- By kind: {'intentional_public_reviewed': 8, 'resource_route_without_tenant_hint': 25, 'raw_sql_id_lookup_without_tenant_hint': 156}

## Family triage

| Family | Count | Verdict | Next action |
|---|---:|---|---|
| general_authenticated_resource_or_sql_review | 73 | review_prompt_not_high | bounded_by_route_inventory_and_unauth_gate; add wrong-role/cross-tenant tests for newly touched routes |
| file_document_certificate_object_routes | 35 | review_prompt_not_high | highest priority for direct object/file IDOR live-token expansion |
| admin_user_governance_routes | 29 | review_prompt_not_high | bounded_by_route_inventory_and_unauth_gate; add wrong-role/cross-tenant tests for newly touched routes |
| supply_chain_traceability_routes | 23 | review_prompt_not_high | covered by supply-chain tests; keep public trace SLO + cross-tenant batch probes as release gate |
| submission_dossier_routes | 21 | review_prompt_not_high | bounded_by_route_inventory_and_unauth_gate; add wrong-role/cross-tenant tests for newly touched routes |

## Release implication

- PASS for requested Tenant isolation / IDOR 9/10 source/evidence gate: 0 HIGH, 0 P0/P1 unmapped/deferred inventory routes, anonymous boundary gate PASS.
- PARTIAL for full customer pilot: MEDIUM prompts need progressive direct wrong-role + cross-tenant live-token expansion, starting with file/document/certificate object routes.
