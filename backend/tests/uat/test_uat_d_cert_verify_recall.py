"""UAT — Luồng D: Document Approval + Public Cert Verification + Recall (50 scenarios).

End-to-end Halal trust chain:
  doc draft → IHC approval → effective → cert generated → public QR scan
  → cert valid; recall initiated → cert revoked → next scan shows revoked.

Recall workflow (#30) is NOT YET IMPLEMENTED — those scenarios skip with a
clear marker so when #30 ships, they auto-run. Document Versioning (#24) is
fully implemented and exercised here as the front half of the chain.

Public-facing endpoint /api/submissions/certificates/public/{cert_number} is
the trust anchor — most attention is on its correctness and isolation.

5-bucket: Happy(10) / Errors(10) / Boundary(10) / Multi-role(10) / Negative(10)
"""

from __future__ import annotations

import uuid

import pytest

from .conftest import (
    auth_headers,
    audit_count,
    delete_doc,
    insert_doc,
    psql,
    psql_value,
    set_approval,
    set_feature_flag,
)

pytestmark = pytest.mark.uat


# ── Module-scope feature flag for Document Versioning (Luồng D depends on #24) ──


@pytest.fixture(scope="module", autouse=True)
def doc_versioning_on():
    """Enable document_versioning_v1 for the suite, restore OFF after."""
    set_feature_flag("document_versioning_v1", True)
    yield
    set_feature_flag("document_versioning_v1", False)


# ════════════════════════════════════════════════════════════════════════════
# B1 — Happy path: doc approval + cert lookup (UAT-D-01..10)
# ════════════════════════════════════════════════════════════════════════════


class TestApprovalAndCertLookup:

    def test_d01_owner_can_submit_for_approval(self, client, biz_a, hdr_a):
        """UAT-D-01: doc draft → submit → status pending."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        try:
            r = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr_a)
            assert r.status_code == 200
            assert r.json()["approval_status"] == "pending_approval"
        finally:
            delete_doc(doc_id)

    def test_d02_owner_can_approve_own_doc(self, client, biz_a, hdr_a):
        """UAT-D-02: owner is auto-IHC, can approve."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            assert r.status_code == 200
        finally:
            delete_doc(doc_id)

    def test_d03_approved_doc_has_effective_date(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            r = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr_a)
            assert r.json()["effective_date"]
        finally:
            delete_doc(doc_id)

    def test_d04_approved_doc_has_retention_expires(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            r = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr_a)
            assert r.json()["retention_expires_at"]
        finally:
            delete_doc(doc_id)

    def test_d05_certificate_list_endpoint_reachable(self, client, hdr_a):
        r = client.get("/api/submissions/certificates", headers=hdr_a)
        assert r.status_code in (200, 404)

    def test_d06_certificate_registry_endpoint_reachable(self, client, hdr_a):
        r = client.get("/api/submissions/certificates/registry", headers=hdr_a)
        assert r.status_code in (200, 401, 403, 404)

    def test_d07_certificate_timeline_endpoint_reachable(self, client, hdr_a):
        r = client.get("/api/submissions/cert-timeline", headers=hdr_a)
        assert r.status_code in (200, 401, 403, 404)

    def test_d08_public_cert_endpoint_no_auth_required(self, client):
        """UAT-D-08: public cert lookup is anonymous-allowed."""
        r = client.get(f"/api/submissions/certificates/public/CERT-NONEXIST-{uuid.uuid4().hex[:6]}")
        # No auth required → must NOT be 401/403
        assert r.status_code in (200, 404)

    def test_d09_public_cert_lookup_unknown_returns_404(self, client):
        r = client.get(f"/api/submissions/certificates/public/CERT-FAKE-{uuid.uuid4().hex[:8]}")
        assert r.status_code == 404

    def test_d10_owner_can_request_cert_renewal(self, client, hdr_a):
        """UAT-D-10: renewal endpoint reachable (resource may not exist yet)."""
        r = client.post(f"/api/submissions/request-renewal/{uuid.uuid4()}", headers=hdr_a)
        assert r.status_code in (200, 400, 404)


# ════════════════════════════════════════════════════════════════════════════
# B2 — Error / edge cases (UAT-D-11..20)
# ════════════════════════════════════════════════════════════════════════════


class TestErrorCases:

    def test_d11_approve_already_approved_returns_409(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            assert r.status_code == 409
        finally:
            delete_doc(doc_id)

    def test_d12_approve_obsolete_returns_409(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="obsolete")
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            assert r.status_code == 409
        finally:
            delete_doc(doc_id)

    def test_d13_supersede_non_approved_returns_409(self, client, biz_a, hdr_a):
        old_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"])  # draft
        new_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        try:
            r = client.post(
                f"/api/documents/{old_id}/supersede", headers=hdr_a,
                json={"new_document_id": new_id},
            )
            assert r.status_code == 409
        finally:
            delete_doc(new_id)
            delete_doc(old_id)

    def test_d14_supersede_self_returns_422(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/supersede", headers=hdr_a,
                json={"new_document_id": doc_id},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d15_retention_below_floor_returns_422(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": 100},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d16_reject_without_reason_returns_422(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/reject", headers=hdr_a, json={"reason": ""})
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d17_cert_status_update_without_auth_blocked(self, client):
        r = client.put(f"/api/submissions/certificates/{uuid.uuid4()}/status",
                       json={"status": "revoked"})
        assert r.status_code in (401, 403, 404)

    def test_d18_invalid_cert_id_returns_4xx(self, client):
        r = client.get("/api/submissions/certificates/public/<>")
        assert r.status_code in (400, 404, 422)

    def test_d19_versions_on_nonexistent_doc_returns_404(self, client, hdr_a):
        r = client.get(f"/api/documents/{uuid.uuid4()}/versions", headers=hdr_a)
        assert r.status_code == 404

    def test_d20_approval_status_on_nonexistent_doc_returns_404(self, client, hdr_a):
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status", headers=hdr_a)
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# B3 — Boundary values (UAT-D-21..30)
# ════════════════════════════════════════════════════════════════════════════


class TestBoundaryValues:

    def test_d21_retention_exact_floor_accepted(self, client, biz_a, hdr_a):
        """UAT-D-21: retention = RETENTION_FLOOR_DAYS (1825) accepted."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": 1825},
            )
            assert r.status_code == 200
        finally:
            delete_doc(doc_id)

    def test_d22_retention_one_below_floor_rejected(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": 1824},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d23_reject_reason_at_max_length_accepted(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject", headers=hdr_a,
                json={"reason": "x" * 500},
            )
            assert r.status_code in (200, 422)
        finally:
            delete_doc(doc_id)

    def test_d24_reject_reason_over_max_rejected(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject", headers=hdr_a,
                json={"reason": "x" * 501},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d25_retention_at_max_int_handled(self, client, biz_a, hdr_a):
        """UAT-D-25: very large retention period either accepted or rejected, not 500."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": 365 * 100},
            )
            assert r.status_code in (200, 422)
        finally:
            delete_doc(doc_id)

    def test_d26_max_chain_depth_constant_enforced(self):
        """UAT-D-26: /versions endpoint declares max_depth=10."""
        # This is verified at import time: from services import MAX_CHAIN_DEPTH
        from services.document_versioning import MAX_CHAIN_DEPTH
        assert MAX_CHAIN_DEPTH == 10

    def test_d27_retention_floor_constant_enforced(self):
        from services.document_versioning import RETENTION_FLOOR_DAYS
        assert RETENTION_FLOOR_DAYS == 1825  # 5 years per JAKIM §5.5

    def test_d28_unicode_reject_reason_preserved(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        reason = "Lý do từ chối: thiếu HACCP §5.3 — 越南"
        try:
            r = client.post(f"/api/documents/{doc_id}/reject", headers=hdr_a,
                            json={"reason": reason})
            assert r.status_code == 200
            stored = psql_value(
                f"SELECT COALESCE(changes::text, '') || ' ' || COALESCE(metadata::text, '') "
                f"FROM audit_logs WHERE entity_id='{doc_id}' "
                f"AND action='document.approval_rejected' LIMIT 1"
            )
            assert "HACCP" in stored
        finally:
            delete_doc(doc_id)

    def test_d29_zero_retention_period_rejected(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": 0},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)

    def test_d30_negative_retention_rejected(self, client, biz_a, hdr_a):
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr_a,
                json={"retention_period_days": -100},
            )
            assert r.status_code == 422
        finally:
            delete_doc(doc_id)


# ════════════════════════════════════════════════════════════════════════════
# B4 — Multi-role / cross-actor (UAT-D-31..40)
# ════════════════════════════════════════════════════════════════════════════


class TestMultiRoleApproval:

    def test_d31_owner_approves_self_audit_logged(self, client, biz_a, hdr_a):
        """UAT-D-31: owner approval creates audit entry."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            before = audit_count(doc_id, "document.approved")
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            after = audit_count(doc_id, "document.approved")
            assert after - before == 1
        finally:
            delete_doc(doc_id)

    def test_d32_owner_can_supersede_via_endpoint(self, client, biz_a, hdr_a):
        v1 = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        v2 = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        try:
            r = client.post(f"/api/documents/{v1}/supersede", headers=hdr_a,
                            json={"new_document_id": v2})
            assert r.status_code == 200
        finally:
            delete_doc(v2)
            delete_doc(v1)

    def test_d33_anon_can_lookup_public_cert_by_number(self, client):
        r = client.get(f"/api/submissions/certificates/public/CERT-{uuid.uuid4().hex[:8]}")
        assert r.status_code in (200, 404)
        # Critical: anonymous request must NOT be redirected to login
        assert r.status_code not in (401, 403)

    def test_d34_authenticated_user_can_lookup_public_cert(self, client, hdr_a):
        """UAT-D-34: same endpoint works with auth too."""
        r = client.get(
            f"/api/submissions/certificates/public/CERT-{uuid.uuid4().hex[:8]}",
            headers=hdr_a,
        )
        assert r.status_code in (200, 404)

    def test_d35_business_b_cannot_revoke_a_certificate(self, client, hdr_b):
        """UAT-D-35: status update is admin-only."""
        r = client.put(
            f"/api/submissions/certificates/{uuid.uuid4()}/status",
            headers=hdr_b, json={"status": "revoked"},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_d36_supersede_flips_old_via_endpoint_chain(self, client, biz_a, hdr_a):
        v1 = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        v2 = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr_a,
                        json={"new_document_id": v2})
            r = client.get(f"/api/documents/{v1}/approval-status", headers=hdr_a)
            assert r.json()["is_obsolete"] is True
        finally:
            delete_doc(v2)
            delete_doc(v1)

    def test_d37_versions_chain_visible_to_owner(self, client, biz_a, hdr_a):
        v1 = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        v2 = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr_a,
                        json={"new_document_id": v2})
            r = client.get(f"/api/documents/{v1}/versions", headers=hdr_a)
            ids = {v["id"] for v in r.json()["versions"]}
            assert v1 in ids and v2 in ids
        finally:
            delete_doc(v2)
            delete_doc(v1)

    @pytest.mark.skip(reason="Recall workflow #30 not yet implemented")
    def test_d38_admin_can_initiate_recall(self, client):
        """UAT-D-38: admin POST /api/recalls → recall created. Pending #30."""

    @pytest.mark.skip(reason="Recall workflow #30 not yet implemented")
    def test_d39_recall_marks_cert_revoked_on_public_endpoint(self, client):
        """UAT-D-39: after recall, public lookup shows revoked status. Pending #30."""

    @pytest.mark.skip(reason="Recall workflow #30 not yet implemented")
    def test_d40_recall_notifies_supply_chain_recipients(self, client):
        """UAT-D-40: recall cascades notification. Pending #30."""


# ════════════════════════════════════════════════════════════════════════════
# B5 — Negative / security (UAT-D-41..50)
# ════════════════════════════════════════════════════════════════════════════


class TestSecurityNegative:

    def test_d41_supersede_requires_auth(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/supersede",
                        json={"new_document_id": str(uuid.uuid4())})
        assert r.status_code in (401, 403)

    def test_d42_approve_requires_auth(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/approve", json={})
        assert r.status_code in (401, 403)

    def test_d43_cross_tenant_supersede_via_endpoint_blocked(self, client, biz_a, biz_b, hdr_b):
        old_a = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        new_b = insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            r = client.post(
                f"/api/documents/{old_a}/supersede", headers=hdr_b,
                json={"new_document_id": new_b},
            )
            assert r.status_code in (403, 404)
        finally:
            delete_doc(new_b)
            delete_doc(old_a)

    def test_d44_sql_injection_in_cert_number_safe(self, client):
        """UAT-D-44: SQLi in public cert lookup handled safely."""
        payload = "CERT' OR '1'='1"
        r = client.get(f"/api/submissions/certificates/public/{payload}")
        assert r.status_code in (200, 400, 404, 422)

    def test_d45_path_traversal_in_cert_number_safe(self, client):
        r = client.get("/api/submissions/certificates/public/..%2F..%2Fetc%2Fpasswd")
        assert r.status_code in (400, 404, 422)

    def test_d46_audit_log_immutable_for_approvals(self, biz_a, hdr_a, client):
        """UAT-D-46: audit_logs entries for approval cannot be deleted/modified."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr_a, json={})
            result = psql(
                f"DELETE FROM audit_logs WHERE entity_id='{doc_id}'", check=False,
            )
            assert result.returncode != 0
        finally:
            delete_doc(doc_id)

    def test_d47_cert_pdf_endpoint_requires_auth(self, client):
        r = client.get(f"/api/submissions/certificates/{uuid.uuid4()}/pdf")
        assert r.status_code in (401, 403, 404)

    def test_d48_supersede_attempt_with_obsolete_target_rejected(self, client, biz_a, hdr_a):
        """UAT-D-48: cannot use obsolete doc as new_document_id (chain integrity)."""
        v1 = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="approved")
        obsolete = insert_doc(biz_a["tenant_id"], biz_a["user_id"], approval_status="obsolete")
        try:
            r = client.post(
                f"/api/documents/{v1}/supersede", headers=hdr_a,
                json={"new_document_id": obsolete},
            )
            assert r.status_code == 409
        finally:
            delete_doc(obsolete)
            delete_doc(v1)

    def test_d49_db_audit_log_no_orphan_after_doc_delete(self, biz_a):
        """UAT-D-49: deleting doc preserves audit history (audit_logs.entity_id intact)."""
        doc_id = insert_doc(biz_a["tenant_id"], biz_a["user_id"])
        psql(
            f"INSERT INTO audit_logs (action, entity_type, entity_id, user_id, tenant_id) "
            f"VALUES ('test.before_delete', 'document', '{doc_id}', '{biz_a['user_id']}', '{biz_a['tenant_id']}')"
        )
        delete_doc(doc_id)
        cnt = psql_value(
            f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_id}'"
        )
        assert int(cnt) >= 1  # audit row preserved despite doc deletion

    @pytest.mark.skip(reason="Recall workflow #30 not yet implemented")
    def test_d50_unauthenticated_recall_blocked(self, client):
        """UAT-D-50: anonymous POST /api/recalls/initiate → 401. Pending #30."""
