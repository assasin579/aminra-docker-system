"""P0 anonymous-boundary smoke tests for high-risk AMINRA routes.

These tests intentionally exercise representative protected surfaces without an
Authorization header. They do not prove tenant/RBAC correctness, but they catch
regressions where compliance/admin/business/provider endpoints become public.
"""

import pytest


PROTECTED_GET_ROUTES = [
    # Admin / governance
    "/auth/admin/audit-logs",
    "/auth/admin/analytics",
    "/auth/admin/pending-providers",
    # Business / documents / dossiers / submissions
    "/dossiers",
    "/api/documents",
    "/api/dashboard/stats",
    "/api/submissions/my-submissions",
    "/api/submissions/received",
    "/api/submissions/certificates",
    "/api/notifications/",
    # Data rights
    "/api/users/me/export-data",
    # Audit operations
    "/api/audits/stats",
    "/api/audits/templates",
    # Supply-chain tenant data
    "/api/supply-chain/suppliers",
    "/api/supply-chain/materials",
    "/api/supply-chain/processes",
    "/api/supply-chain/batches",
]


PROTECTED_POST_ROUTES = [
    ("/api/users/me/request-deletion", {}),
    ("/api/submissions/submit", {}),
    ("/api/supply-chain/suppliers", {"name": "SHOULD-NOT-CREATE"}),
    ("/api/supply-chain/materials", {"name": "SHOULD-NOT-CREATE"}),
    ("/api/supply-chain/processes", {"name": "SHOULD-NOT-CREATE", "flowchart": {"nodes": [], "edges": []}}),
    ("/api/supply-chain/batches", {"batch_code": "SHOULD-NOT-CREATE", "product_name": "Blocked"}),
]


PUBLIC_ROUTES = [
    "/health",
    "/api/submissions/certificates/public/HALAL-2026-DEMO",
    "/api/supply-chain/batches/trace/LOT-2026-DEMO-TRACE",
]


@pytest.mark.parametrize("path", PROTECTED_GET_ROUTES)
def test_high_risk_get_routes_reject_anonymous(client, path):
    resp = client.get(path)
    assert resp.status_code in (401, 403), f"{path} returned {resp.status_code}: {resp.text[:300]}"


@pytest.mark.parametrize("path,payload", PROTECTED_POST_ROUTES)
def test_high_risk_post_routes_reject_anonymous_before_mutation(client, path, payload):
    resp = client.post(path, json=payload)
    assert resp.status_code in (401, 403), f"{path} returned {resp.status_code}: {resp.text[:300]}"


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_intended_public_routes_remain_reachable(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text[:300]}"
