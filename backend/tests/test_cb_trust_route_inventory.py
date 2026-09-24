from __future__ import annotations


def test_inventory_contains_critical_cb_routes_and_actions():
    from scripts.cb_trust_route_inventory import build_inventory

    inventory = build_inventory()
    by_route = {(item["method"], item["path"]): item for item in inventory}

    assert by_route[("POST", "/api/submissions/issue-certificate/{business_tenant_id}")]["action"] == "certificate.issue"
    assert by_route[("POST", "/api/certification-decisions")]["action"] == "certification_decision.create"
    assert by_route[("GET", "/api/certification-decisions/submission/{submission_id}")]["action"] == "submission.read"
    assert by_route[("POST", "/api/certification-decisions/{decision_id}/approve")]["action"] == "certification_decision.approve"
    assert by_route[("GET", "/api/submissions/received")]["action"] == "submission.read"
    assert by_route[("PUT", "/api/submissions/received/{submission_id}/status")]["action"] == "submission.review"
    assert by_route[("PUT", "/api/audits/{vid}/assign")]["action"] == "audit.assign"
    assert by_route[("PUT", "/api/audits/{vid}/status")]["action"] == "audit.perform"


def test_inventory_uses_only_known_policy_actions():
    from auth.policy_service import SUPPORTED_ACTIONS
    from scripts.cb_trust_route_inventory import build_inventory

    actions = {item["action"] for item in build_inventory()}
    assert "certificate.issue" in actions
    assert "certification_decision.approve" in actions
    assert actions <= SUPPORTED_ACTIONS
