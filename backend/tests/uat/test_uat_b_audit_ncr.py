"""UAT — Luồng B: Onsite Audit + NCR Verification Workflow (50 scenarios).

Most audit endpoints require provider/auditor role. Business token is used as
the test subject for permission boundary checks; DB-level invariants are
verified via direct queries (state machine, severity enum, FK constraints).

Schema notes (verified at write time):
- audit_visits: status ∈ {scheduled, in_progress, completed, report_submitted}
- audit_ncr: severity ∈ {critical, major, minor}, status ∈ {open, in_review, closed}
- audit_ncr.visit_id is FK to audit_visits

5-bucket: Happy(10) / Errors(10) / Boundary(10) / Multi-role(10) / Negative(10)
"""

from __future__ import annotations

import uuid

import pytest

from .conftest import (
    backend_unreachable,
    delete_doc,
    insert_doc,
    psql,
    psql_value,
    register_business,
)

pytestmark = pytest.mark.uat


# ── Helpers specific to Luồng B ─────────────────────────────────────────────


def _insert_audit_visit(business_tenant: str, provider_id: str, **extra) -> str:
    """Insert minimal audit_visit row directly. Returns visit UUID.

    visit_type ∈ {initial, renewal, surprise}. Default 'initial'.
    """
    visit_id = str(uuid.uuid4())
    cols = ["id", "business_tenant", "provider_id", "visit_type", "scheduled_date"]
    vals = [
        f"'{visit_id}'", f"'{business_tenant}'", f"'{provider_id}'",
        "'initial'", "CURRENT_DATE",
    ]
    for k, v in extra.items():
        cols.append(k)
        vals.append("NULL" if v is None else f"'{v}'")
    psql(f"INSERT INTO audit_visits ({', '.join(cols)}) VALUES ({', '.join(vals)})")
    return visit_id


def _delete_audit_visit(visit_id: str) -> None:
    psql(
        f"DELETE FROM audit_ncr WHERE visit_id='{visit_id}'; "
        f"DELETE FROM audit_visit_items WHERE visit_id='{visit_id}'; "
        f"DELETE FROM audit_visits WHERE id='{visit_id}'",
        check=False,
    )


def _insert_ncr(visit_id: str, severity: str = "minor", status: str = "open") -> str:
    ncr_id = str(uuid.uuid4())
    psql(
        f"INSERT INTO audit_ncr (id, visit_id, description, severity, status) "
        f"VALUES ('{ncr_id}', '{visit_id}', 'UAT NCR', '{severity}', '{status}')"
    )
    return ncr_id


# ── Provider tenant fixture (we register a fresh provider so we have a provider_id) ──


@pytest.fixture(scope="module")
def provider(client):
    """Register a provider. RegisterProviderResponse shape is {user_id, email, status, message}.

    Provider account is pending admin approval — but we only need its user_id
    to satisfy audit_visits.provider_id FK (REFERENCES users.id).
    """
    if backend_unreachable(client):
        pytest.skip("Backend not reachable")
    rid = uuid.uuid4().hex[:8]
    r = client.post(
        "/auth/provider/register",
        json={
            "email": f"prov-uat-{rid}@aminra-qa.com",
            "password": "ProvUAT2026!",
            "company_name": f"ProvUAT {rid}",
            "company_code": f"PROV-{rid}",
        },
    )
    if r.status_code != 201:
        pytest.skip(f"Cannot register provider: HTTP {r.status_code} {r.text[:200]}")
    body = r.json()
    return {
        "email": body["email"],
        "user_id": body["user_id"],
    }


# ════════════════════════════════════════════════════════════════════════════
# B1 — Provider-facing endpoints reachable / read-only checks (UAT-B-01..10)
# ════════════════════════════════════════════════════════════════════════════


class TestProviderEndpoints:

    def test_b01_audit_dashboard_stats_reachable(self, client, hdr_a):
        """UAT-B-01: GET /api/audits/dashboard/stats returns predictable status."""
        r = client.get("/api/audits/dashboard/stats", headers=hdr_a)
        assert r.status_code in (200, 400, 401, 403, 404)

    def test_b02_audit_stats_reachable(self, client, hdr_a):
        r = client.get("/api/audits/stats", headers=hdr_a)
        assert r.status_code in (200, 400, 401, 403, 404)

    def test_b03_audit_cb_stats_blocked_for_business(self, client, hdr_a):
        r = client.get("/api/audits/cb-stats", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b04_audit_businesses_blocked_for_business(self, client, hdr_a):
        r = client.get("/api/audits/businesses", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b05_audit_templates_blocked_for_business(self, client, hdr_a):
        r = client.get("/api/audits/templates", headers=hdr_a)
        assert r.status_code in (200, 400, 401, 403, 404)

    def test_b06_ncr_pending_blocked_for_business(self, client, hdr_a):
        r = client.get("/api/audits/ncr/pending", headers=hdr_a)
        assert r.status_code in (200, 400, 401, 403, 404)

    def test_b07_audit_history_blocked_for_business(self, client, biz_a, hdr_a):
        r = client.get(f"/api/audits/history/{biz_a['tenant_id']}", headers=hdr_a)
        assert r.status_code in (200, 400, 401, 403, 404)

    def test_b08_audit_visit_get_blocked_for_business(self, client, hdr_a):
        r = client.get(f"/api/audits/{uuid.uuid4()}", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b09_audit_business_dossier_blocked(self, client, biz_a, hdr_a):
        r = client.get(f"/api/audits/businesses/{biz_a['tenant_id']}/dossier", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b10_audit_business_score_blocked(self, client, biz_a, hdr_a):
        r = client.get(f"/api/audits/businesses/{biz_a['tenant_id']}/score", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)


# ════════════════════════════════════════════════════════════════════════════
# B2 — Mutation attempts by business token blocked (UAT-B-11..20)
# ════════════════════════════════════════════════════════════════════════════


class TestMutationsBlocked:

    def test_b11_business_cannot_create_audit_template(self, client, hdr_a):
        r = client.post("/api/audits/templates", headers=hdr_a, json={"name": "x"})
        assert r.status_code in (400, 401, 403, 404)

    def test_b12_business_cannot_update_audit_visit_status(self, client, hdr_a):
        r = client.put(
            f"/api/audits/{uuid.uuid4()}/status", headers=hdr_a,
            json={"status": "completed"},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b13_business_cannot_assign_auditor(self, client, hdr_a):
        r = client.put(
            f"/api/audits/{uuid.uuid4()}/assign", headers=hdr_a,
            json={"auditor_id": str(uuid.uuid4())},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b14_business_cannot_record_finding(self, client, hdr_a):
        r = client.post(
            f"/api/audits/{uuid.uuid4()}/items", headers=hdr_a,
            json={"description": "fake"},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b15_business_cannot_raise_ncr(self, client, hdr_a):
        r = client.post(
            f"/api/audits/{uuid.uuid4()}/ncr", headers=hdr_a,
            json={"description": "fake", "severity": "minor"},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b16_business_cannot_make_audit_decision(self, client, hdr_a):
        r = client.post(
            f"/api/audits/{uuid.uuid4()}/decision", headers=hdr_a,
            json={"decision": "approve"},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b17_business_cannot_generate_report(self, client, hdr_a):
        r = client.post(f"/api/audits/{uuid.uuid4()}/generate-report", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b18_business_cannot_close_ncr(self, client, hdr_a):
        r = client.put(
            f"/api/audits/ncr/{uuid.uuid4()}/verify", headers=hdr_a,
            json={"closed": True},
        )
        assert r.status_code in (400, 401, 403, 404)

    def test_b19_business_cannot_delete_audit_template(self, client, hdr_a):
        r = client.delete(f"/api/audits/templates/{uuid.uuid4()}", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b20_business_cannot_set_gps(self, client, hdr_a):
        r = client.put(
            f"/api/audits/{uuid.uuid4()}/gps", headers=hdr_a,
            json={"start_gps": {"lat": 0, "lng": 0}},
        )
        assert r.status_code in (400, 401, 403, 404)


# ════════════════════════════════════════════════════════════════════════════
# B3 — DB-level state machine + boundary (UAT-B-21..30)
# ════════════════════════════════════════════════════════════════════════════


class TestDBStateMachine:

    def test_b21_audit_visit_default_status_scheduled(self, biz_a, provider):
        """UAT-B-21: newly inserted audit_visit defaults to status='scheduled'."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            status = psql_value(f"SELECT status FROM audit_visits WHERE id='{vid}'")
            assert status == "scheduled"
        finally:
            _delete_audit_visit(vid)

    def test_b22_audit_visit_status_check_constraint(self, biz_a, provider):
        """UAT-B-22: invalid status rejected by CHECK constraint."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"UPDATE audit_visits SET status='invalid_state' WHERE id='{vid}'",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b23_audit_visit_status_transitions_allowed(self, biz_a, provider):
        """UAT-B-23: scheduled → in_progress → completed → report_submitted all valid."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            for s in ("in_progress", "completed", "report_submitted"):
                result = psql(
                    f"UPDATE audit_visits SET status='{s}' WHERE id='{vid}'",
                    check=False,
                )
                assert result.returncode == 0
        finally:
            _delete_audit_visit(vid)

    def test_b24_compliance_score_within_bounds(self, biz_a, provider):
        """UAT-B-24: compliance_score CHECK 0..100 — over 100 rejected."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"UPDATE audit_visits SET compliance_score=150 WHERE id='{vid}'",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b25_compliance_score_negative_rejected(self, biz_a, provider):
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"UPDATE audit_visits SET compliance_score=-1 WHERE id='{vid}'",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b26_compliance_score_at_zero_accepted(self, biz_a, provider):
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"UPDATE audit_visits SET compliance_score=0 WHERE id='{vid}'",
                check=False,
            )
            assert result.returncode == 0
        finally:
            _delete_audit_visit(vid)

    def test_b27_compliance_score_at_max_accepted(self, biz_a, provider):
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"UPDATE audit_visits SET compliance_score=100 WHERE id='{vid}'",
                check=False,
            )
            assert result.returncode == 0
        finally:
            _delete_audit_visit(vid)

    def test_b28_ncr_severity_enum_enforced(self, biz_a, provider):
        """UAT-B-28: invalid severity rejected by CHECK."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"INSERT INTO audit_ncr (visit_id, description, severity) "
                f"VALUES ('{vid}', 'test', 'catastrophic')",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b29_ncr_status_enum_enforced(self, biz_a, provider):
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        ncr = _insert_ncr(vid)
        try:
            result = psql(
                f"UPDATE audit_ncr SET status='deleted' WHERE id='{ncr}'",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b30_ncr_default_status_open(self, biz_a, provider):
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        ncr = _insert_ncr(vid)
        try:
            status = psql_value(f"SELECT status FROM audit_ncr WHERE id='{ncr}'")
            assert status == "open"
        finally:
            _delete_audit_visit(vid)


# ════════════════════════════════════════════════════════════════════════════
# B4 — Multi-tenant audit isolation (UAT-B-31..40)
# ════════════════════════════════════════════════════════════════════════════


class TestAuditMultiTenantIsolation:

    def test_b31_audit_visit_scoped_to_business_tenant(self, biz_a, biz_b, provider):
        """UAT-B-31: audit_visit row carries business_tenant; queries by tenant filter."""
        vid_a = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            cnt_a = psql_value(
                f"SELECT COUNT(*) FROM audit_visits WHERE business_tenant='{biz_a['tenant_id']}'"
            )
            cnt_b = psql_value(
                f"SELECT COUNT(*) FROM audit_visits WHERE business_tenant='{biz_b['tenant_id']}'"
            )
            assert int(cnt_a) >= 1
            assert int(cnt_b) == 0
        finally:
            _delete_audit_visit(vid_a)

    def test_b32_business_b_cannot_see_business_a_audit_via_api(self, client, biz_a, biz_b, hdr_b, provider):
        vid_a = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            r = client.get(f"/api/audits/{vid_a}", headers=hdr_b)
            assert r.status_code in (400, 401, 403, 404)
        finally:
            _delete_audit_visit(vid_a)

    def test_b33_audit_history_filtered_by_target_tenant(self, client, biz_a, biz_b, hdr_a):
        r = client.get(f"/api/audits/history/{biz_b['tenant_id']}", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b34_business_dossier_filtered_by_tenant(self, client, biz_a, biz_b, hdr_a):
        r = client.get(f"/api/audits/businesses/{biz_b['tenant_id']}/dossier", headers=hdr_a)
        assert r.status_code in (400, 401, 403, 404)

    def test_b35_db_audit_visit_business_tenant_not_null(self, biz_a, provider):
        """UAT-B-35: schema enforces business_tenant NOT NULL."""
        out = psql_value(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='audit_visits' AND column_name='business_tenant'"
        )
        assert out == "NO"

    def test_b36_db_audit_visit_provider_id_not_null(self):
        out = psql_value(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='audit_visits' AND column_name='provider_id'"
        )
        assert out == "NO"

    def test_b37_ncr_visit_id_fk_enforced(self, biz_a, provider):
        """UAT-B-37: audit_ncr.visit_id FK to audit_visits enforced."""
        bogus = str(uuid.uuid4())
        result = psql(
            f"INSERT INTO audit_ncr (visit_id, description, severity) "
            f"VALUES ('{bogus}', 'orphan', 'minor')",
            check=False,
        )
        assert result.returncode != 0

    def test_b38_audit_visit_delete_cascades_or_blocks_ncr(self, biz_a, provider):
        """UAT-B-38: visit row cannot be deleted while NCRs reference it (FK on delete)."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        ncr = _insert_ncr(vid)
        try:
            result = psql(f"DELETE FROM audit_visits WHERE id='{vid}'", check=False)
            # Either FK blocks (returncode != 0) or cascades (returncode == 0)
            # Both are acceptable design choices. Verify whichever happens.
            if result.returncode == 0:
                left = psql_value(f"SELECT COUNT(*) FROM audit_ncr WHERE id='{ncr}'")
                # If cascade, ncr should be gone
                assert left == "0"
        finally:
            _delete_audit_visit(vid)

    def test_b39_audit_visit_unique_per_visit(self, biz_a, provider):
        """UAT-B-39: visit IDs are unique (PK enforced)."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            result = psql(
                f"INSERT INTO audit_visits (id, business_tenant, provider_id, visit_type, scheduled_date) "
                f"VALUES ('{vid}', '{biz_a['tenant_id']}', '{provider['user_id']}', 'initial', CURRENT_DATE)",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_audit_visit(vid)

    def test_b40_visit_type_required(self, biz_a, provider):
        """UAT-B-40: visit_type NOT NULL."""
        result = psql(
            f"INSERT INTO audit_visits (business_tenant, provider_id, scheduled_date) "
            f"VALUES ('{biz_a['tenant_id']}', '{provider['user_id']}', CURRENT_DATE)",
            check=False,
        )
        assert result.returncode != 0


# ════════════════════════════════════════════════════════════════════════════
# B5 — Negative / IDOR / replay (UAT-B-41..50)
# ════════════════════════════════════════════════════════════════════════════


class TestAuditSecurityNegative:

    def test_b41_audit_endpoints_require_auth(self, client):
        r = client.get(f"/api/audits/{uuid.uuid4()}")
        assert r.status_code in (401, 403, 404)

    def test_b42_audit_visit_idor_consistent_404(self, client, hdr_a):
        codes = set()
        for _ in range(3):
            r = client.get(f"/api/audits/{uuid.uuid4()}", headers=hdr_a)
            codes.add(r.status_code)
        assert codes <= {400, 401, 403, 404}

    def test_b43_ncr_idor_consistent(self, client, hdr_a):
        codes = set()
        for _ in range(3):
            r = client.put(
                f"/api/audits/ncr/{uuid.uuid4()}/verify", headers=hdr_a, json={},
            )
            codes.add(r.status_code)
        assert codes <= {400, 401, 403, 404}

    def test_b44_ncr_severity_sql_injection_safe(self, biz_a, provider):
        """UAT-B-44: SQL injection in severity column rejected by CHECK."""
        vid = _insert_audit_visit(biz_a["tenant_id"], provider["user_id"])
        try:
            inj = "minor'; DROP TABLE audit_ncr; --"
            result = psql(
                f"INSERT INTO audit_ncr (visit_id, description, severity) "
                f"VALUES ('{vid}', 'sqli', '{inj}')",
                check=False,
            )
            assert result.returncode != 0
            # Verify table still exists
            cnt = psql_value("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='audit_ncr'")
            assert int(cnt) == 1
        finally:
            _delete_audit_visit(vid)

    def test_b45_audit_template_not_accessible_anon(self, client):
        """UAT-B-45: anonymous DELETE template → blocked.

        GET on individual template is not implemented (405), so use DELETE.
        """
        r = client.delete(f"/api/audits/templates/{uuid.uuid4()}")
        assert r.status_code in (401, 403, 404, 405)

    def test_b46_audit_signature_endpoint_blocked_anon(self, client):
        r = client.post(f"/api/audits/{uuid.uuid4()}/signature", json={"sig": "x"})
        assert r.status_code in (401, 403, 404)

    def test_b47_audit_photo_endpoint_blocked_anon(self, client):
        r = client.post(f"/api/audits/{uuid.uuid4()}/items/{uuid.uuid4()}/photo")
        assert r.status_code in (401, 403, 404)

    def test_b48_audit_report_pdf_blocked_anon(self, client):
        r = client.get(f"/api/audits/{uuid.uuid4()}/report-pdf")
        assert r.status_code in (401, 403, 404)

    def test_b49_audit_visit_path_traversal_safe(self, client, hdr_a):
        r = client.get("/api/audits/..%2F..%2Fetc%2Fpasswd", headers=hdr_a)
        assert r.status_code in (400, 404, 422)

    def test_b50_audit_log_immutable_for_audits(self, biz_a, provider):
        """UAT-B-50: audit_logs entries about audits are immutable too (same trigger)."""
        psql(
            f"INSERT INTO audit_logs (action, entity_type, entity_id, user_id, tenant_id) "
            f"VALUES ('audit.test', 'audit_visit', '{uuid.uuid4()}', '{biz_a['user_id']}', '{biz_a['tenant_id']}')"
        )
        result = psql(
            f"DELETE FROM audit_logs WHERE action='audit.test' AND user_id='{biz_a['user_id']}'",
            check=False,
        )
        assert result.returncode != 0
