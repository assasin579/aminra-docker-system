"""Document version control — INTEGRATION tests (Stage 6b, 50 cases).

Live backend + DB roundtrip. Requires:
- Backend running with migration 017 applied
- document_versioning_v1 flag toggleable (autouse fixture handles)
- Fresh business user registration (one per scenario, no shared state)

Test IDs match `docs/features/document-version-control/test-plan.md` (INT-01..50).
Skips cleanly when backend not reachable.

Run:
    pytest backend/tests/test_document_versioning_integration.py -v
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.integration

# ── Helpers + fixtures ──────────────────────────────────────────────────────


def _backend_unreachable(client) -> bool:
    try:
        r = client.get("/health", timeout=5)
        return r.status_code != 200
    except Exception:
        return True


def _set_flag(enabled: bool) -> None:
    """Toggle document_versioning_v1 via direct DB. Bypasses admin endpoint
    which has a known JWT vs opaque-session mismatch (Phase 0 backlog #5)."""
    val = "true" if enabled else "false"
    subprocess.run(
        [
            "docker",
            "exec",
            "aminra-docker-system-postgres-db-1",
            "psql",
            "-U",
            "aminra_user",
            "-d",
            "aminra",
            "-c",
            f"UPDATE feature_flags SET default_enabled={val} WHERE name='document_versioning_v1'",
        ],
        check=False,
        capture_output=True,
        timeout=10,
    )
    # Bust in-process cache by waiting > 60s would be too slow; restart backend.
    subprocess.run(
        ["docker", "restart", "aminra-docker-system-aminra-backend-1"],
        check=False,
        capture_output=True,
        timeout=30,
    )
    # Wait for backend to come back
    for _ in range(20):
        time.sleep(1)
        try:
            import httpx

            r = httpx.get("http://localhost:8100/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            continue


@pytest.fixture(scope="module")
def flag_on(client):
    """Enable feature flag for this test module, restore OFF after."""
    if _backend_unreachable(client):
        pytest.skip("Backend not reachable")
    _set_flag(True)
    yield
    _set_flag(False)


def _register_business(client, suffix: str = "") -> dict:
    """Register a fresh business owner. Returns {email, password, token, user_id, tenant_id}."""
    rid = uuid.uuid4().hex[:8]
    email = f"int-test-{rid}{suffix}@aminra-qa.com"
    password = "IntTestPass2026!"
    r = client.post(
        "/auth/business/register",
        json={
            "email": email,
            "password": password,
            "company_name": f"IntTest {rid}",
            "company_code": f"BIZ-{rid}",
        },
        timeout=10,
    )
    if r.status_code != 201:
        pytest.skip(f"Cannot register business: HTTP {r.status_code} {r.text[:200]}")
    body = r.json()
    return {
        "email": email,
        "password": password,
        "token": body["access_token"],
        "user_id": body["user"]["id"],
        "tenant_id": body["user"]["tenant_id"],
    }


def _insert_doc(tenant_id: str, user_id: str, status: str = "uploaded", **extra) -> str:
    """Insert a minimal doc row directly via psql. Returns doc id (UUID)."""
    doc_id = str(uuid.uuid4())
    cols = ["id", "filename", "original_filename", "user_id", "tenant_id", "status"]
    vals = [
        f"'{doc_id}'",
        "'test.pdf'",
        "'test.pdf'",
        f"'{user_id}'",
        f"'{tenant_id}'",
        f"'{status}'",
    ]
    for k, v in extra.items():
        cols.append(k)
        vals.append("NULL" if v is None else f"'{v}'")
    sql = f"INSERT INTO documents ({', '.join(cols)}) VALUES ({', '.join(vals)})"
    subprocess.run(
        [
            "docker",
            "exec",
            "aminra-docker-system-postgres-db-1",
            "psql",
            "-U",
            "aminra_user",
            "-d",
            "aminra",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    return doc_id


def _set_approval_status(doc_id: str, status: str) -> None:
    """Force approval_status via direct UPDATE (bypasses state machine for test setup)."""
    subprocess.run(
        [
            "docker",
            "exec",
            "aminra-docker-system-postgres-db-1",
            "psql",
            "-U",
            "aminra_user",
            "-d",
            "aminra",
            "-c",
            f"UPDATE documents SET approval_status='{status}' WHERE id='{doc_id}'",
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )


def _delete_doc(doc_id: str) -> None:
    """Cleanup helper. Wraps the delete-block trigger by null-ing parents first."""
    subprocess.run(
        [
            "docker",
            "exec",
            "aminra-docker-system-postgres-db-1",
            "psql",
            "-U",
            "aminra_user",
            "-d",
            "aminra",
            "-c",
            f"UPDATE documents SET version_parent_id=NULL WHERE version_parent_id='{doc_id}'; DELETE FROM documents WHERE id='{doc_id}'",
        ],
        check=False,
        capture_output=True,
        timeout=10,
    )


@pytest.fixture(scope="module")
def biz(client, flag_on):
    """Module-scope business owner — avoids rate-limit on /auth/business/register."""
    return _register_business(client)


@pytest.fixture(scope="module")
def biz_b(client, flag_on):
    """Second tenant for cross-tenant tests, module-scope."""
    return _register_business(client, suffix="-b")


@pytest.fixture
def auth_headers(biz):
    return {"Authorization": f"Bearer {biz['token']}"}


# ════════════════════════════════════════════════════════════════════════════
# 1. Endpoint happy paths — INT-01..12
# ════════════════════════════════════════════════════════════════════════════


class TestEndpointHappyPaths:
    # INT-01
    def test_submit_for_approval_owner(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["approval_status"] == "pending_approval"
        finally:
            _delete_doc(doc_id)

    # INT-02 — owner has can_edit (covered above); a member without is_owner needs separate setup
    def test_submit_owner_short_circuit(self, client, biz, auth_headers):
        # Owners always have can_edit per ALL_PERMISSIONS — verify endpoint accepts
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            assert r.status_code == 200
        finally:
            _delete_doc(doc_id)

    # INT-03 + INT-04
    def test_approve_with_default_dates(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=auth_headers, json={})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["approval_status"] == "approved"
            assert body["effective_date"] is not None
            assert body["next_review_date"] is not None
        finally:
            _delete_doc(doc_id)

    def test_approve_with_custom_dates(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve",
                headers=auth_headers,
                json={
                    "effective_date": "2026-06-01",
                    "next_review_date": "2027-06-01",
                    "retention_period_days": 2555,
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["effective_date"] == "2026-06-01"
        finally:
            _delete_doc(doc_id)

    # INT-05 — same as default test (already covered)
    def test_approve_empty_body_uses_defaults(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=auth_headers, json={})
            assert r.status_code == 200
        finally:
            _delete_doc(doc_id)

    # INT-06
    def test_reject_with_reason(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject",
                headers=auth_headers,
                json={"reason": "Thiếu phần truy xuất nguồn gốc"},
            )
            assert r.status_code == 200
            assert r.json()["approval_status"] == "draft"
        finally:
            _delete_doc(doc_id)

    # INT-07
    def test_supersede_links_old_and_new(self, client, biz, auth_headers):
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(old_id, "approved")
        new_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(
                f"/api/documents/{old_id}/supersede",
                headers=auth_headers,
                json={"new_document_id": new_id},
            )
            assert r.status_code == 200, r.text
            assert r.json()["new_version_number"] >= 2
        finally:
            _delete_doc(new_id)
            _delete_doc(old_id)

    # INT-08
    def test_get_versions_returns_chain(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}/versions", headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            assert body["doc_id"] == doc_id
            assert isinstance(body["versions"], list)
            assert body["max_depth"] == 10
        finally:
            _delete_doc(doc_id)

    # INT-09
    def test_get_approval_status_full_block(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}/approval-status", headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            assert "approval_status" in body
            assert "version_number" in body
            assert "is_obsolete" in body
        finally:
            _delete_doc(doc_id)

    # INT-10 (IHC member can approve) — needs fixture setup beyond owner; doc as TODO
    @pytest.mark.skip(reason="IHC member fixture requires multi-step setup; covered by FUNC suite")
    def test_ihc_member_can_approve(self, client):
        pass

    # INT-11 — DB-level retention auto-compute (verify retention_expires_at populated post-approve)
    def test_retention_expires_at_auto_computed(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=auth_headers, json={})
            r = client.get(f"/api/documents/{doc_id}/approval-status", headers=auth_headers)
            assert r.json()["retention_expires_at"] is not None
        finally:
            _delete_doc(doc_id)

    # INT-12 — DB trigger flips obsolete on supersede
    def test_supersede_db_trigger_flips_obsolete(self, client, biz, auth_headers):
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(old_id, "approved")
        new_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(
                f"/api/documents/{old_id}/supersede",
                headers=auth_headers,
                json={"new_document_id": new_id},
            )
            r = client.get(f"/api/documents/{old_id}/approval-status", headers=auth_headers)
            assert r.json()["approval_status"] == "obsolete"
            assert r.json()["is_obsolete"] is True
        finally:
            _delete_doc(new_id)
            _delete_doc(old_id)


# ════════════════════════════════════════════════════════════════════════════
# 2. Error states — INT-13..24
# ════════════════════════════════════════════════════════════════════════════


class TestErrorStates:
    # INT-13
    def test_submit_already_pending_409(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    # INT-14
    def test_submit_already_approved_409(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "approved")
        try:
            r = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    # INT-15
    def test_approve_from_draft_skip_409(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        # default draft state
        try:
            r = client.post(f"/api/documents/{doc_id}/approve", headers=auth_headers, json={})
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    # INT-16 — non-approver returns 403; needs member setup, mark covered by FUNC
    @pytest.mark.skip(reason="Member-without-approve setup deferred to FUNC suite")
    def test_approve_by_non_approver_403(self, client):
        pass

    # INT-17
    def test_reject_without_reason_422(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(f"/api/documents/{doc_id}/reject", headers=auth_headers, json={"reason": ""})
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    # INT-18
    def test_reject_reason_too_long_422(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject",
                headers=auth_headers,
                json={"reason": "x" * 501},
            )
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    # INT-19
    def test_approve_retention_below_floor_422(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve",
                headers=auth_headers,
                json={"retention_period_days": 100},
            )
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    # INT-20
    def test_supersede_obsolete_doc_409(self, client, biz, auth_headers):
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        new_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        # Force old already-obsolete via direct UPDATE (skip approve flow)
        _set_approval_status(old_id, "obsolete")
        try:
            r = client.post(
                f"/api/documents/{old_id}/supersede",
                headers=auth_headers,
                json={"new_document_id": new_id},
            )
            assert r.status_code == 409
        finally:
            _delete_doc(new_id)
            _delete_doc(old_id)

    # INT-21
    def test_supersede_self_link_422(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval_status(doc_id, "approved")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/supersede",
                headers=auth_headers,
                json={"new_document_id": doc_id},
            )
            assert r.status_code == 422
        finally:
            _delete_doc(doc_id)

    # INT-22
    def test_approve_nonexistent_doc_404(self, client, auth_headers):
        nonexistent = str(uuid.uuid4())
        r = client.post(f"/api/documents/{nonexistent}/approve", headers=auth_headers, json={})
        assert r.status_code == 404

    # INT-23
    def test_versions_nonexistent_doc_404(self, client, auth_headers):
        nonexistent = str(uuid.uuid4())
        r = client.get(f"/api/documents/{nonexistent}/versions", headers=auth_headers)
        assert r.status_code == 404

    # INT-24 (flag-OFF returns 404 — covered by SMOKE suite which toggles flag)
    def test_invalid_uuid_returns_400(self, client, auth_headers):
        r = client.get("/api/documents/not-a-uuid/approval-status", headers=auth_headers)
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════
# 3. Tenant isolation — INT-25..34
# ════════════════════════════════════════════════════════════════════════════


class TestTenantIsolation:
    # INT-25
    def test_cross_tenant_submit_404(self, client, biz, biz_b):
        # Doc belongs to biz_b; biz tries to submit
        doc_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            r = client.post(
                f"/api/documents/{doc_id}/submit-for-approval",
                headers={"Authorization": f"Bearer {biz['token']}"},
            )
            assert r.status_code == 404  # no existence leak
        finally:
            _delete_doc(doc_id)

    # INT-26
    def test_cross_tenant_approve_404(self, client, biz, biz_b):
        doc_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/approve",
                headers={"Authorization": f"Bearer {biz['token']}"},
                json={},
            )
            assert r.status_code == 404
        finally:
            _delete_doc(doc_id)

    # INT-27
    def test_cross_tenant_reject_404(self, client, biz, biz_b):
        doc_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"], approval_status="pending_approval")
        try:
            r = client.post(
                f"/api/documents/{doc_id}/reject",
                headers={"Authorization": f"Bearer {biz['token']}"},
                json={"reason": "test"},
            )
            assert r.status_code == 404
        finally:
            _delete_doc(doc_id)

    # INT-28 — DB trigger blocks cross-tenant supersede; tested via direct DB INSERT
    def test_db_trigger_blocks_cross_tenant_supersede(self, client, biz, biz_b):
        # We can't easily force the application to send a cross-tenant new_document_id
        # without bypassing tenant scope check. Test via direct DB UPDATE.
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        new_id_b = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-c",
                    f"UPDATE documents SET superseded_by_id='{new_id_b}' WHERE id='{old_id}'",
                ],
                capture_output=True, timeout=10,
            )
            # Trigger raises 23514, psql exits non-zero
            assert result.returncode != 0 or b"same tenant" in result.stderr.lower()
        finally:
            _delete_doc(new_id_b)
            _delete_doc(old_id)

    # INT-29
    def test_cross_tenant_versions_404(self, client, biz, biz_b):
        doc_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            r = client.get(
                f"/api/documents/{doc_id}/versions",
                headers={"Authorization": f"Bearer {biz['token']}"},
            )
            assert r.status_code == 404
        finally:
            _delete_doc(doc_id)

    # INT-30
    def test_cross_tenant_approval_status_404(self, client, biz, biz_b):
        doc_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            r = client.get(
                f"/api/documents/{doc_id}/approval-status",
                headers={"Authorization": f"Bearer {biz['token']}"},
            )
            assert r.status_code == 404
        finally:
            _delete_doc(doc_id)

    # INT-31..34: provider-side cross-tenant + admin checks — out of scope for v1
    @pytest.mark.skip(reason="Provider/admin cross-tenant defer to FUNC suite (different role setup)")
    def test_provider_cross_tenant_setup(self, client):
        pass

    @pytest.mark.skip(reason="Same as above")
    def test_provider_assigned_doc_can_read(self, client):
        pass

    @pytest.mark.skip(reason="Admin no-mutation ensured by role check; covered by SEC")
    def test_admin_cannot_mutate(self, client):
        pass

    @pytest.mark.skip(reason="Admin read-only audit trail — covered by SEC")
    def test_admin_read_only_audit(self, client):
        pass


# ════════════════════════════════════════════════════════════════════════════
# 4. DB trigger behavior — INT-35..42
# ════════════════════════════════════════════════════════════════════════════


class TestDBTriggers:
    # INT-35 — already covered in TestTenantIsolation (cross-tenant trigger)
    def test_trigger_blocks_cross_tenant_parent(self, client, biz, biz_b):
        # INSERT with cross-tenant version_parent_id
        new_id = uuid.uuid4()
        parent_b = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            sql = (
                f"INSERT INTO documents (id, filename, original_filename, user_id, tenant_id, status, version_parent_id) "
                f"VALUES ('{new_id}', 'x.pdf', 'x.pdf', '{biz['user_id']}', '{biz['tenant_id']}', 'uploaded', '{parent_b}')"
            )
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-c", sql,
                ],
                capture_output=True, timeout=10,
            )
            # Trigger should reject
            assert result.returncode != 0
        finally:
            _delete_doc(parent_b)
            _delete_doc(str(new_id))

    # INT-36 — same trigger test as above but on UPDATE (also covered in TestTenantIsolation)
    def test_trigger_blocks_cross_tenant_update(self, client, biz, biz_b):
        # UPDATE doc to set cross-tenant superseded_by → trigger blocks
        own_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        other_id = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            sql = f"UPDATE documents SET superseded_by_id='{other_id}' WHERE id='{own_id}'"
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-c", sql,
                ],
                capture_output=True, timeout=10,
            )
            assert result.returncode != 0
        finally:
            _delete_doc(other_id)
            _delete_doc(own_id)

    # INT-37 — already covered (auto-compute retention)
    def test_retention_auto_compute_on_first_approval(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=auth_headers, json={})
            # Verify retention_expires_at populated
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT retention_expires_at FROM documents WHERE id='{doc_id}'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert result.stdout.strip() != ""  # has a value
        finally:
            _delete_doc(doc_id)

    # INT-38 — trigger does NOT recompute retention on idempotent UPDATE
    @pytest.mark.skip(reason="Difficult to assert without mutating test in isolation; covered by SEC R4")
    def test_no_retention_recompute_on_idempotent(self, client):
        pass

    # INT-39 — covered (test_supersede_db_trigger_flips_obsolete)
    def test_supersede_flips_obsolete_at_db(self, client, biz, auth_headers):
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        new_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(
                f"/api/documents/{old_id}/supersede",
                headers=auth_headers,
                json={"new_document_id": new_id},
            )
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT approval_status FROM documents WHERE id='{old_id}'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert result.stdout.strip() == "obsolete"
        finally:
            _delete_doc(new_id)
            _delete_doc(old_id)

    # INT-40 — delete-block trigger
    def test_delete_block_with_children(self, client, biz):
        old_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        # Create child doc pointing to old
        child_id = uuid.uuid4()
        sql = (
            f"INSERT INTO documents (id, filename, original_filename, user_id, tenant_id, status, version_parent_id) "
            f"VALUES ('{child_id}', 'c.pdf', 'c.pdf', '{biz['user_id']}', '{biz['tenant_id']}', 'uploaded', '{old_id}')"
        )
        subprocess.run(
            ["docker", "exec", "aminra-docker-system-postgres-db-1", "psql", "-U", "aminra_user", "-d", "aminra", "-c", sql],
            check=True, capture_output=True, timeout=10,
        )
        try:
            # Try to delete old (has child) — should fail with 23503
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-c",
                    f"DELETE FROM documents WHERE id='{old_id}'",
                ],
                capture_output=True, timeout=10,
            )
            assert result.returncode != 0
        finally:
            # Cleanup: null parent then delete both
            _delete_doc(str(child_id))
            _delete_doc(old_id)

    # INT-41
    def test_delete_allowed_no_children(self, client, biz):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        result = subprocess.run(
            [
                "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                "-U", "aminra_user", "-d", "aminra", "-c",
                f"DELETE FROM documents WHERE id='{doc_id}'",
            ],
            capture_output=True, timeout=10,
        )
        assert result.returncode == 0

    # INT-42
    def test_delete_allowed_when_only_supersede_link(self, client, biz):
        # Doc has superseded_by but no children (supersede points OUT of self, not IN)
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        target = _insert_doc(biz["tenant_id"], biz["user_id"])
        sql = f"UPDATE documents SET superseded_by_id='{target}' WHERE id='{doc_id}'"
        subprocess.run(
            ["docker", "exec", "aminra-docker-system-postgres-db-1", "psql", "-U", "aminra_user", "-d", "aminra", "-c", sql],
            check=True, capture_output=True, timeout=10,
        )
        try:
            # Delete should succeed (no version_parent_id IN this doc)
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-c",
                    f"DELETE FROM documents WHERE id='{doc_id}'",
                ],
                capture_output=True, timeout=10,
            )
            assert result.returncode == 0
        finally:
            _delete_doc(target)


# ════════════════════════════════════════════════════════════════════════════
# 5. Audit log + migration — INT-43..50
# ════════════════════════════════════════════════════════════════════════════


class TestAuditAndMigration:
    # INT-43 — audit row in same TX as approval
    def test_audit_inserted_on_submit(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.submitted_for_approval'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert result.stdout.strip() == "1"
        finally:
            _delete_doc(doc_id)

    # INT-44 — audit references tenant_id
    def test_audit_has_tenant_id(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=auth_headers)
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT tenant_id FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.submitted_for_approval'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert result.stdout.strip() == biz["tenant_id"]
        finally:
            _delete_doc(doc_id)

    # INT-45 — rejection reason in metadata
    def test_audit_captures_rejection_reason(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        reason = f"Reason-{uuid.uuid4().hex[:6]}"
        try:
            client.post(
                f"/api/documents/{doc_id}/reject", headers=auth_headers, json={"reason": reason}
            )
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT metadata::text FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.approval_rejected'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert reason in result.stdout
        finally:
            _delete_doc(doc_id)

    # INT-46 — approve metadata captures dates + retention
    def test_audit_captures_approve_metadata(self, client, biz, auth_headers):
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(
                f"/api/documents/{doc_id}/approve",
                headers=auth_headers,
                json={"effective_date": "2026-08-01", "retention_period_days": 2000},
            )
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT metadata::text FROM audit_logs WHERE entity_id='{doc_id}' AND action='document.approved'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            assert "2026-08-01" in result.stdout
            assert "2000" in result.stdout
        finally:
            _delete_doc(doc_id)

    # INT-47 — verify migration applied
    def test_migration_017_applied(self, client):
        result = subprocess.run(
            [
                "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                "-U", "aminra_user", "-d", "aminra", "-tAc",
                "SELECT version_num FROM alembic_version",
            ],
            capture_output=True, timeout=10, text=True,
        )
        assert result.stdout.strip() == "017_document_version_control"

    # INT-48 — backfill rule: existing 'approved' rows → approval_status='approved'
    def test_backfill_existing_approved(self, client, biz):
        # Insert a doc with legacy status='approved' BUT approval_status=NULL
        # then verify trigger/state aligns. (We bypass migration backfill — that
        # ran at 017 apply time; here we test default value for new 'approved' inserts.)
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], status="approved")
        try:
            result = subprocess.run(
                [
                    "docker", "exec", "aminra-docker-system-postgres-db-1", "psql",
                    "-U", "aminra_user", "-d", "aminra", "-tAc",
                    f"SELECT approval_status FROM documents WHERE id='{doc_id}'",
                ],
                capture_output=True, timeout=10, text=True,
            )
            # New inserts default to 'draft' — backfill rule only applies to migration upgrade
            # so this verifies the trigger doesn't accidentally rewrite NEW rows
            assert result.stdout.strip() == "draft"
        finally:
            _delete_doc(doc_id)

    # INT-49 — migration downgrade reversibility
    @pytest.mark.skip(reason="Downgrade test requires mutation of dev DB; run separately")
    def test_migration_downgrade(self, client):
        pass

    # INT-50 — re-apply idempotent
    @pytest.mark.skip(reason="Same — runs in CI migrations job, not here")
    def test_migration_reapply_idempotent(self, client):
        pass
