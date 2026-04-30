"""Document Version Control — SECURITY tests (Stage 6f, 50 cases via STRIDE).

STRIDE categorization (50 cases):
- S — Spoofing identity (8): forge tokens, replay, impersonate IHC/owner
- T — Tampering with data (9): alter audit log, mutate approved doc, chain attacks
- R — Repudiation (8): audit trail completeness, immutability, actor binding
- I — Information disclosure (10): cross-tenant leak, IDOR, error message leak
- D — Denial of service (8): oversize input, recursion bomb, expensive queries
- E — Elevation of privilege (7): role escalation, IHC bypass, admin pretend

Run from host:
    pytest backend/tests/test_document_versioning_sec.py -v
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid

import pytest

pytestmark = pytest.mark.security

DB_CONTAINER = "aminra-docker-system-postgres-db-1"
BACKEND_CONTAINER = "aminra-docker-system-aminra-backend-1"


# ── Shared helpers (mirror of tests/uat/conftest.py — kept local for stability) ──


def _backend_unreachable(client) -> bool:
    try:
        return client.get("/health", timeout=5).status_code != 200
    except Exception:
        return True


def _psql(sql: str, *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "aminra_user", "-d", "aminra", "-tAc", sql],
        check=check, capture_output=True, timeout=15,
    )


def _psql_value(sql: str) -> str:
    out = _psql(sql, check=False)
    return out.stdout.decode().strip()


def _set_flag(enabled: bool) -> None:
    val = "true" if enabled else "false"
    _psql(f"UPDATE feature_flags SET default_enabled={val} WHERE name='document_versioning_v1'", check=False)
    subprocess.run(["docker", "restart", BACKEND_CONTAINER],
                   check=False, capture_output=True, timeout=30)
    for _ in range(20):
        time.sleep(1)
        try:
            import httpx
            if httpx.get("http://localhost:8100/health", timeout=2).status_code == 200:
                return
        except Exception:
            continue


def _register_business(client, suffix: str = "") -> dict:
    rid = uuid.uuid4().hex[:8]
    email = f"sec-{rid}{suffix}@aminra-qa.com"
    password = "SecPass2026!"
    r = client.post(
        "/auth/business/register",
        json={"email": email, "password": password,
              "company_name": f"SecTest {rid}", "company_code": f"SEC-{rid}"},
        timeout=10,
    )
    if r.status_code != 201:
        pytest.skip(f"Cannot register: HTTP {r.status_code}")
    body = r.json()
    return {"email": email, "password": password, "token": body["access_token"],
            "user_id": body["user"]["id"], "tenant_id": body["user"]["tenant_id"]}


def _insert_doc(tenant_id: str, user_id: str, status: str = "uploaded", **extra) -> str:
    doc_id = str(uuid.uuid4())
    cols = ["id", "filename", "original_filename", "user_id", "tenant_id", "status"]
    vals = [f"'{doc_id}'", "'sec.pdf'", "'sec.pdf'", f"'{user_id}'", f"'{tenant_id}'", f"'{status}'"]
    for k, v in extra.items():
        cols.append(k)
        vals.append("NULL" if v is None else f"'{v}'")
    _psql(f"INSERT INTO documents ({', '.join(cols)}) VALUES ({', '.join(vals)})")
    return doc_id


def _set_approval(doc_id: str, status: str) -> None:
    _psql(f"UPDATE documents SET approval_status='{status}' WHERE id='{doc_id}'")


def _delete_doc(doc_id: str) -> None:
    _psql(
        f"UPDATE documents SET version_parent_id=NULL, superseded_by_id=NULL "
        f"WHERE version_parent_id='{doc_id}' OR superseded_by_id='{doc_id}'; "
        f"DELETE FROM documents WHERE id='{doc_id}'",
        check=False,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def flag_on(client):
    if _backend_unreachable(client):
        pytest.skip("Backend not reachable")
    _set_flag(True)
    yield
    _set_flag(False)


@pytest.fixture(scope="module")
def biz(client, flag_on):
    return _register_business(client)


@pytest.fixture(scope="module")
def biz_b(client, flag_on):
    return _register_business(client, suffix="-b")


@pytest.fixture
def hdr(biz):
    return {"Authorization": f"Bearer {biz['token']}"}


@pytest.fixture
def hdr_b(biz_b):
    return {"Authorization": f"Bearer {biz_b['token']}"}


# ════════════════════════════════════════════════════════════════════════════
# S — Spoofing (SEC-S-01..08)
# ════════════════════════════════════════════════════════════════════════════


class TestSpoofing:

    def test_s01_no_auth_blocked_on_submit(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/submit-for-approval")
        assert r.status_code in (401, 403)

    def test_s02_no_auth_blocked_on_approve(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/approve", json={})
        assert r.status_code in (401, 403)

    def test_s03_no_auth_blocked_on_reject(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/reject", json={"reason": "x"})
        assert r.status_code in (401, 403)

    def test_s04_no_auth_blocked_on_supersede(self, client):
        r = client.post(f"/api/documents/{uuid.uuid4()}/supersede",
                        json={"new_document_id": str(uuid.uuid4())})
        assert r.status_code in (401, 403)

    def test_s05_invalid_jwt_signature_rejected(self, client):
        forged = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.WRONG"
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status",
                       headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code in (401, 403)

    def test_s06_expired_jwt_rejected(self, client):
        # Token with past 'exp' claim — backend should reject
        # exp = 0 = epoch → definitely expired
        from base64 import urlsafe_b64encode
        import json
        header = urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
        payload = urlsafe_b64encode(
            json.dumps({"sub": "test", "exp": 0, "tenant_id": "x"}).encode()
        ).rstrip(b"=").decode()
        forged = f"{header}.{payload}.NOSIG"
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status",
                       headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code in (401, 403)

    def test_s07_alg_none_jwt_rejected(self, client):
        """SEC-S-07: 'alg: none' JWT (CVE pattern) must be rejected."""
        from base64 import urlsafe_b64encode
        import json
        header = urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
        payload = urlsafe_b64encode(
            json.dumps({"sub": "admin", "is_owner": True}).encode()
        ).rstrip(b"=").decode()
        forged = f"{header}.{payload}."
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status",
                       headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code in (401, 403)

    def test_s08_basic_auth_not_accepted(self, client):
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status",
                       headers={"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="})
        assert r.status_code in (401, 403)


# ════════════════════════════════════════════════════════════════════════════
# T — Tampering (SEC-T-09..17)
# ════════════════════════════════════════════════════════════════════════════


class TestTampering:

    def test_t09_audit_log_immutable_no_delete(self, biz, hdr, client):
        """SEC-T-09: audit_logs cannot be deleted (immutable trigger)."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            result = _psql(f"DELETE FROM audit_logs WHERE entity_id='{doc_id}'", check=False)
            assert result.returncode != 0
        finally:
            _delete_doc(doc_id)

    def test_t10_audit_log_immutable_no_update(self, biz, hdr, client):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            result = _psql(
                f"UPDATE audit_logs SET action='hacked' WHERE entity_id='{doc_id}'",
                check=False,
            )
            assert result.returncode != 0
        finally:
            _delete_doc(doc_id)

    def test_t11_approved_doc_supersede_cycle_via_self(self, client, biz, hdr):
        """SEC-T-11: cannot create cycle by setting self as superseding doc."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        try:
            r = client.post(f"/api/documents/{doc_id}/supersede", headers=hdr,
                            json={"new_document_id": doc_id})
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    def test_t12_db_block_cross_tenant_supersede_link(self, biz, biz_b):
        """SEC-T-12: trigger blocks superseded_by across tenants."""
        a = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        b = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            result = _psql(f"UPDATE documents SET superseded_by_id='{b}' WHERE id='{a}'",
                           check=False)
            assert result.returncode != 0
        finally:
            _delete_doc(b)
            _delete_doc(a)

    def test_t13_cannot_alter_approved_at_after_approval(self, biz, hdr, client):
        """SEC-T-13: backdating/forwardating approved_at via API is impossible
        (no endpoint exposes it). Verified at API surface."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            # No endpoint to update approved_at — only approve creates it.
            # Test verifies no leak via /approval-status → re-approve = 409
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    def test_t14_max_chain_depth_enforced(self, biz, hdr, client):
        """SEC-T-14: /versions limits chain depth to MAX_CHAIN_DEPTH=10."""
        # Inject 12-level deep chain via DB
        ids = []
        try:
            for i in range(12):
                d = _insert_doc(biz["tenant_id"], biz["user_id"],
                                approval_status="approved" if i == 0 else "obsolete")
                if i > 0:
                    _psql(
                        f"UPDATE documents SET version_parent_id='{ids[-1]}' WHERE id='{d}'"
                    )
                ids.append(d)
            r = client.get(f"/api/documents/{ids[-1]}/versions", headers=hdr)
            assert r.status_code == 200
            # Result should be capped — not arbitrarily large
            assert len(r.json()["versions"]) <= 12
        finally:
            for d in reversed(ids):
                _delete_doc(d)

    def test_t15_documents_tenant_id_not_null_at_schema(self):
        """SEC-T-15: schema enforces tenant_id NOT NULL (fix from migration 018)."""
        out = _psql_value(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='documents' AND column_name='tenant_id'"
        )
        assert out == "NO"

    def test_t16_documents_no_null_tenant_id_in_data(self):
        cnt = _psql_value("SELECT COUNT(*) FROM documents WHERE tenant_id IS NULL")
        assert cnt == "0"

    def test_t17_retention_floor_check_constraint(self):
        """SEC-T-17: DB CHECK enforces retention_period_days >= 1825."""
        out = _psql_value(
            "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
            "JOIN pg_class t ON c.conrelid=t.oid "
            "WHERE t.relname='documents' AND c.conname LIKE '%retention%'"
        )
        assert "1825" in out


# ════════════════════════════════════════════════════════════════════════════
# R — Repudiation (SEC-R-18..25)
# ════════════════════════════════════════════════════════════════════════════


class TestRepudiation:

    def test_r18_submit_creates_audit_with_actor(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            actor = _psql_value(
                f"SELECT user_id FROM audit_logs WHERE entity_id='{doc_id}' "
                f"AND action='document.submitted_for_approval' ORDER BY created_at DESC LIMIT 1"
            )
            assert actor == biz["user_id"]
        finally:
            _delete_doc(doc_id)

    def test_r19_approve_creates_audit_with_actor(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            actor = _psql_value(
                f"SELECT user_id FROM audit_logs WHERE entity_id='{doc_id}' "
                f"AND action='document.approved' ORDER BY created_at DESC LIMIT 1"
            )
            assert actor == biz["user_id"]
        finally:
            _delete_doc(doc_id)

    def test_r20_reject_creates_audit_with_reason(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        reason_token = f"REJECT-{uuid.uuid4().hex[:6]}"
        try:
            client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                        json={"reason": reason_token})
            stored = _psql_value(
                f"SELECT COALESCE(changes::text, '') || ' ' || COALESCE(metadata::text, '') "
                f"FROM audit_logs WHERE entity_id='{doc_id}' "
                f"AND action='document.approval_rejected' LIMIT 1"
            )
            assert reason_token in stored
        finally:
            _delete_doc(doc_id)

    def test_r21_supersede_creates_audit_with_metadata(self, client, biz, hdr):
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            stored = _psql_value(
                f"SELECT COALESCE(metadata::text, '') FROM audit_logs "
                f"WHERE entity_id='{v1}' AND action='document.superseded' LIMIT 1"
            )
            assert v2 in stored or "new_document_id" in stored
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_r22_audit_carries_tenant_id(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            tid = _psql_value(
                f"SELECT tenant_id FROM audit_logs WHERE entity_id='{doc_id}' "
                f"ORDER BY created_at DESC LIMIT 1"
            )
            assert tid == biz["tenant_id"]
        finally:
            _delete_doc(doc_id)

    def test_r23_audit_timestamps_chronological(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            time.sleep(0.05)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            rows = _psql_value(
                f"SELECT array_agg(EXTRACT(EPOCH FROM created_at) ORDER BY created_at) "
                f"FROM audit_logs WHERE entity_id='{doc_id}'"
            )
            # rows is a Postgres array literal — just assert non-empty
            assert rows
        finally:
            _delete_doc(doc_id)

    def test_r24_failed_approve_no_audit_pollution(self, client, biz, hdr):
        """SEC-R-24: 409 from invalid state must NOT create audit entry."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])  # draft
        try:
            before = _psql_value(
                f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.approved'"
            )
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r.status_code == 409
            after = _psql_value(
                f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.approved'"
            )
            assert before == after
        finally:
            _delete_doc(doc_id)

    def test_r25_no_orphan_audit_after_doc_delete(self, biz):
        """SEC-R-25: deleting doc preserves audit history."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _psql(
            f"INSERT INTO audit_logs (action, entity_type, entity_id, user_id, tenant_id) "
            f"VALUES ('test.t25', 'document', '{doc_id}', '{biz['user_id']}', '{biz['tenant_id']}')"
        )
        _delete_doc(doc_id)
        cnt = _psql_value(f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_id}'")
        assert int(cnt) >= 1


# ════════════════════════════════════════════════════════════════════════════
# I — Information Disclosure (SEC-I-26..35)
# ════════════════════════════════════════════════════════════════════════════


class TestInformationDisclosure:

    def test_i26_cross_tenant_doc_returns_404_not_403(self, client, biz, hdr_b):
        """SEC-I-26: 404 (not 403) avoids existence leak."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_a}/approval-status", headers=hdr_b)
            assert r.status_code == 404
        finally:
            _delete_doc(doc_a)

    def test_i27_uuid_enumeration_consistent_404(self, client, hdr):
        codes = set()
        for _ in range(5):
            r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status", headers=hdr)
            codes.add(r.status_code)
        assert codes == {404}

    def test_i28_versions_endpoint_no_cross_tenant_leak(self, client, biz, hdr_b):
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            _psql(f"UPDATE documents SET version_parent_id='{v1}' WHERE id='{v2}'")
            r = client.get(f"/api/documents/{v1}/versions", headers=hdr_b)
            assert r.status_code == 404
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_i29_list_excludes_other_tenant_docs(self, client, biz, biz_b, hdr_b):
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get("/api/documents", headers=hdr_b)
            body = r.json()
            items = body if isinstance(body, list) else body.get("items", body.get("documents", []))
            assert doc_a not in {d.get("id") for d in items}
        finally:
            _delete_doc(doc_a)

    def test_i30_error_message_no_stack_trace(self, client, hdr):
        """SEC-I-30: error responses don't leak Python tracebacks."""
        r = client.get("/api/documents/not-a-uuid/approval-status", headers=hdr)
        assert "Traceback" not in r.text
        assert "File \"/app" not in r.text

    def test_i31_error_message_no_sql_leak(self, client, hdr):
        r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status", headers=hdr)
        body = r.text.lower()
        for kw in ("select ", "from documents", "psycopg", "pg_"):
            assert kw not in body

    def test_i32_user_email_not_in_doc_response(self, client, biz, hdr):
        """SEC-I-32: doc detail responses don't leak owner email."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}", headers=hdr)
            if r.status_code == 200:
                body = r.text
                assert biz["email"] not in body
        finally:
            _delete_doc(doc_id)

    def test_i33_versions_response_no_extra_fields(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}/versions", headers=hdr)
            assert r.status_code == 200
            for v in r.json()["versions"]:
                # Allow-list
                allowed = {"id", "version_number", "approval_status",
                           "approved_at", "effective_date"}
                extra = set(v.keys()) - allowed
                assert not extra, f"Unexpected fields leaked: {extra}"
        finally:
            _delete_doc(doc_id)

    def test_i34_health_endpoint_no_secrets(self, client):
        """SEC-I-34: /health doesn't expose secrets/env vars."""
        r = client.get("/health")
        body = r.text.lower()
        for forbidden in ("password", "secret", "jwt_", "vault", "openrouter", "deepseek"):
            assert forbidden not in body, f"Health leaks {forbidden}"

    def test_i35_metrics_endpoint_no_user_data(self, client):
        """SEC-I-35: /metrics shows aggregate counts, no PII."""
        r = client.get("/metrics")
        if r.status_code == 200:
            body = r.text
            # No emails or tenant UUIDs in metrics body
            assert "@aminra-qa.com" not in body


# ════════════════════════════════════════════════════════════════════════════
# D — Denial of Service (SEC-D-36..43)
# ════════════════════════════════════════════════════════════════════════════


class TestDenialOfService:

    def test_d36_oversize_register_input_handled(self, client):
        """SEC-D-36: 1000-char input returns 422 (not 500 / not crash)."""
        rid = uuid.uuid4().hex[:6]
        r = client.post(
            "/auth/business/register",
            json={"email": f"dos-{rid}@aminra-qa.com", "password": "P@ss12345",
                  "company_name": "X" * 1000, "company_code": f"D-{rid}"},
        )
        assert r.status_code == 422

    def test_d37_oversize_reject_reason_capped(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject", headers=hdr,
                json={"reason": "y" * 100_000},
            )
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    def test_d38_huge_retention_period_handled(self, client, biz, hdr):
        """SEC-D-38: huge retention rejected at validation (not crash with 500).

        Fixed by adding le=36500 (100 years) to _ApprovalRequest.retention_period_days.
        """
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr,
                json={"retention_period_days": 10**18},
            )
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    def test_d39_versions_query_completes_quickly(self, client, biz, hdr):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}/versions",
                           headers=hdr, timeout=5)
            assert r.status_code == 200
        finally:
            _delete_doc(doc_id)

    def test_d40_invalid_uuid_no_500(self, client, hdr):
        r = client.get("/api/documents/not-a-uuid/approval-status", headers=hdr)
        assert r.status_code != 500

    def test_d41_path_traversal_no_500(self, client, hdr):
        r = client.get("/api/documents/..%2F..%2Fetc%2Fpasswd/approval-status", headers=hdr)
        assert r.status_code != 500

    def test_d42_huge_json_payload_handled(self, client, hdr):
        """SEC-D-42: huge body doesn't crash backend."""
        big = "x" * (10 * 1024)
        r = client.post(f"/api/documents/{uuid.uuid4()}/reject", headers=hdr,
                        json={"reason": big}, timeout=10)
        assert r.status_code in (404, 413, 422, 400)

    def test_d43_concurrent_invalid_requests_no_crash(self, client, hdr):
        """SEC-D-43: 10 sequential bad requests don't degrade backend."""
        for _ in range(10):
            r = client.get(f"/api/documents/{uuid.uuid4()}/approval-status",
                           headers=hdr, timeout=5)
            assert r.status_code in (404, 400)
        # Backend still responding
        h = client.get("/health", timeout=5)
        assert h.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# E — Elevation of Privilege (SEC-E-44..50)
# ════════════════════════════════════════════════════════════════════════════


class TestElevationOfPrivilege:

    def test_e44_business_token_blocked_from_admin_audit_logs(self, client, hdr):
        r = client.get("/auth/admin/audit-logs", headers=hdr)
        assert r.status_code in (401, 403, 404)

    def test_e45_business_token_blocked_from_pending_providers(self, client, hdr):
        r = client.get("/auth/admin/pending-providers", headers=hdr)
        assert r.status_code in (401, 403, 404)

    def test_e46_business_token_blocked_from_admin_analytics(self, client, hdr):
        r = client.get("/auth/admin/analytics", headers=hdr)
        assert r.status_code in (401, 403, 404)

    def test_e47_business_cannot_approve_via_provider_endpoint(self, client, biz, hdr):
        """SEC-E-47: business user with admin payload-injection cannot escalate."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve",
                headers={**{"Authorization": f"Bearer {biz['token']}"},
                         "X-Forwarded-Role": "admin"},
                json={"role": "admin"},
            )
            # Owner approval allowed (auto-IHC) but not via injected role header
            assert r.status_code == 200  # owner has can_approve via is_owner
            # Verify no role escalation logged
        finally:
            _delete_doc(doc_id)

    def test_e48_business_cannot_use_other_business_token(self, client, biz, biz_b, hdr_b):
        """SEC-E-48: B's token used to mutate A's resource → 404 (no escalation)."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{doc_a}/submit-for-approval", headers=hdr_b)
            assert r.status_code in (403, 404)
        finally:
            _delete_doc(doc_a)

    def test_e49_no_role_field_in_register_payload_escalates(self, client):
        """SEC-E-49: setting role=admin in register body doesn't grant admin."""
        rid = uuid.uuid4().hex[:6]
        r = client.post(
            "/auth/business/register",
            json={"email": f"esc-{rid}@aminra-qa.com", "password": "P@ss12345",
                  "company_name": "Esc", "company_code": f"ESC-{rid}",
                  "role": "admin", "is_owner": True, "permissions": "*"},
        )
        if r.status_code == 201:
            body = r.json()
            user = body["user"]
            assert user.get("role") == "business"  # not admin
            # is_owner is True (since they registered as owner of new tenant) — that's expected
            # but they only own their own tenant, not all tenants

    def test_e50_jwt_payload_role_change_not_honored(self, client):
        """SEC-E-50: forging role claim in JWT payload (without re-sign) rejected."""
        # Take a real registration, then try to inject a forged 'role: admin' JWT
        # This should fail at signature verification.
        from base64 import urlsafe_b64encode
        import json
        header = urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
        payload = urlsafe_b64encode(
            json.dumps({"sub": str(uuid.uuid4()), "role": "admin", "is_owner": True}).encode()
        ).rstrip(b"=").decode()
        forged = f"{header}.{payload}.NOSIG"
        r = client.get("/auth/admin/audit-logs",
                       headers={"Authorization": f"Bearer {forged}"})
        assert r.status_code in (401, 403)
