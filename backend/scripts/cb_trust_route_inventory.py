"""CB trust-core critical route inventory.

Static source-of-truth for Week 1 so tests can pin every certificate,
submission, audit, and certification-decision route to one policy action.
"""
from __future__ import annotations

from auth.policy_service import SUPPORTED_ACTIONS


def build_inventory() -> list[dict[str, str]]:
    inventory = [
        {"method": "GET", "path": "/api/submissions/received", "action": "submission.read", "module": "submission"},
        {"method": "GET", "path": "/api/submissions/received/{submission_id}/documents", "action": "submission.read", "module": "submission"},
        {"method": "PUT", "path": "/api/submissions/received/{submission_id}/status", "action": "submission.review", "module": "submission"},
        {"method": "POST", "path": "/api/submissions/received/{submission_id}/approve-final", "action": "submission.review", "module": "submission"},
        {"method": "POST", "path": "/api/submissions/issue-certificate/{business_tenant_id}", "action": "certificate.issue", "module": "certificate"},
        {"method": "POST", "path": "/api/submissions/received/{submission_id}/issue-certificate", "action": "certificate.issue", "module": "certificate"},
        {"method": "PUT", "path": "/api/audits/{vid}/assign", "action": "audit.assign", "module": "audit"},
        {"method": "PUT", "path": "/api/audits/{vid}/status", "action": "audit.perform", "module": "audit"},
        {"method": "POST", "path": "/api/audits/{vid}/decision", "action": "audit.perform", "module": "audit"},
        {"method": "POST", "path": "/api/certification-decisions", "action": "certification_decision.create", "module": "certification_decision"},
        {"method": "GET", "path": "/api/certification-decisions/submission/{submission_id}", "action": "submission.read", "module": "certification_decision"},
        {"method": "POST", "path": "/api/certification-decisions/{decision_id}/approve", "action": "certification_decision.approve", "module": "certification_decision"},
        {"method": "POST", "path": "/api/certification-decisions/{decision_id}/reject", "action": "certification_decision.approve", "module": "certification_decision"},
    ]
    unknown = {item["action"] for item in inventory} - SUPPORTED_ACTIONS
    if unknown:
        raise ValueError(f"Inventory references unsupported actions: {sorted(unknown)}")
    return inventory


if __name__ == "__main__":
    import json

    print(json.dumps(build_inventory(), indent=2, sort_keys=True))
