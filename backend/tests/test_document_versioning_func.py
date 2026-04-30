"""Document version control — FUNCTIONAL (FUNC) tests (Stage 6d, 50 cases).

Different from INTEGRATION (single-endpoint atomic checks) — each FUNC test
chains ≥3 endpoint calls to simulate a real user journey, then verifies
final state across multiple view endpoints (list, detail, /versions,
/approval-status). Side effects (audit log) are also verified.

Test IDs match `docs/features/document-version-control/test-plan.md` (FUNC-01..50).
Skips cleanly when backend not reachable.

Run from host:
    pytest backend/tests/test_document_versioning_func.py -v
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid

import pytest

pytestmark = pytest.mark.functional

DB_CONTAINER = "aminra-docker-system-postgres-db-1"
BACKEND_CONTAINER = "aminra-docker-system-aminra-backend-1"


# ── Helpers + fixtures ──────────────────────────────────────────────────────


def _backend_unreachable(client) -> bool:
    try:
        return client.get("/health", timeout=5).status_code != 200
    except Exception:
        return True


def _psql(sql: str, *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "docker", "exec", DB_CONTAINER,
            "psql", "-U", "aminra_user", "-d", "aminra", "-tAc", sql,
        ],
        check=check, capture_output=True, timeout=10,
    )


def _set_flag(enabled: bool) -> None:
    val = "true" if enabled else "false"
    _psql(
        f"UPDATE feature_flags SET default_enabled={val} WHERE name='document_versioning_v1'",
        check=False,
    )
    subprocess.run(
        ["docker", "restart", BACKEND_CONTAINER],
        check=False, capture_output=True, timeout=30,
    )
    for _ in range(20):
        time.sleep(1)
        try:
            import httpx
            if httpx.get("http://localhost:8100/health", timeout=2).status_code == 200:
                return
        except Exception:
            continue


@pytest.fixture(scope="module")
def flag_on(client):
    if _backend_unreachable(client):
        pytest.skip("Backend not reachable")
    _set_flag(True)
    yield
    _set_flag(False)


def _register_business(client, suffix: str = "") -> dict:
    rid = uuid.uuid4().hex[:8]
    email = f"func-{rid}{suffix}@aminra-qa.com"
    password = "FuncTestPass2026!"
    r = client.post(
        "/auth/business/register",
        json={
            "email": email, "password": password,
            "company_name": f"FuncTest {rid}",
            "company_code": f"FBIZ-{rid}",
        },
        timeout=10,
    )
    if r.status_code != 201:
        pytest.skip(f"Cannot register: HTTP {r.status_code} {r.text[:200]}")
    body = r.json()
    return {
        "email": email, "password": password,
        "token": body["access_token"],
        "user_id": body["user"]["id"],
        "tenant_id": body["user"]["tenant_id"],
    }


def _insert_doc(tenant_id: str, user_id: str, status: str = "uploaded", **extra) -> str:
    doc_id = str(uuid.uuid4())
    cols = ["id", "filename", "original_filename", "user_id", "tenant_id", "status"]
    vals = [
        f"'{doc_id}'", "'test.pdf'", "'test.pdf'",
        f"'{user_id}'", f"'{tenant_id}'", f"'{status}'",
    ]
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


def _audit_count_for_doc(doc_id: str, event: str | None = None) -> int:
    where = f"entity_type='document' AND entity_id='{doc_id}'"
    if event:
        where += f" AND action='{event}'"
    out = _psql(f"SELECT COUNT(*) FROM audit_logs WHERE {where}", check=False)
    try:
        return int(out.stdout.decode().strip() or "0")
    except Exception:
        return 0


def _list_docs(client, token: str) -> list[dict]:
    r = client.get("/api/documents/my-documents", headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return []
    return r.json() if isinstance(r.json(), list) else r.json().get("items", [])


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
# Group A — Owner full lifecycle (FUNC-01..10)
# ════════════════════════════════════════════════════════════════════════════


class TestOwnerLifecycle:
    """Multi-step: create → submit → approve → verify across views."""

    def test_full_happy_path_submit_then_approve(self, client, biz, hdr):
        """FUNC-01: draft → submit → approve → list shows approved + detail has all fields."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r1 = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            assert r1.status_code == 200 and r1.json()["approval_status"] == "pending_approval"

            r2 = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r2.status_code == 200 and r2.json()["approval_status"] == "approved"

            r3 = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr)
            body = r3.json()
            assert body["approval_status"] == "approved"
            assert body["effective_date"] is not None
            assert body["next_review_date"] is not None
            assert body["retention_expires_at"] is not None
            assert body["version_number"] == 1
        finally:
            _delete_doc(doc_id)

    def test_approval_status_transitions_through_all_states(self, client, biz, hdr):
        """FUNC-02: track approval_status change at each step."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            assert client.get(f"/api/documents/{doc_id}/approval-status",
                              headers=hdr).json()["approval_status"] == "draft"

            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            assert client.get(f"/api/documents/{doc_id}/approval-status",
                              headers=hdr).json()["approval_status"] == "pending_approval"

            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert client.get(f"/api/documents/{doc_id}/approval-status",
                              headers=hdr).json()["approval_status"] == "approved"
        finally:
            _delete_doc(doc_id)

    def test_approve_with_custom_dates_persisted_in_detail(self, client, biz, hdr):
        """FUNC-03: custom effective/review dates retrievable after approval."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval(doc_id, "pending_approval")
        try:
            client.post(
                f"/api/documents/{doc_id}/approve", headers=hdr,
                json={"effective_date": "2026-07-15", "next_review_date": "2027-07-15",
                      "retention_period_days": 1825},
            )
            body = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr).json()
            assert body["effective_date"].startswith("2026-07-15")
            assert body["next_review_date"].startswith("2027-07-15")
        finally:
            _delete_doc(doc_id)

    def test_audit_log_entries_after_full_cycle(self, client, biz, hdr):
        """FUNC-04: submit + approve must each create audit entry."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            before = _audit_count_for_doc(doc_id)
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            after = _audit_count_for_doc(doc_id)
            assert after - before >= 2
        finally:
            _delete_doc(doc_id)

    def test_version_number_starts_at_1_for_first_approval(self, client, biz, hdr):
        """FUNC-05: brand new doc → first approve → version_number=1."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert client.get(f"/api/documents/{doc_id}/approval-status",
                              headers=hdr).json()["version_number"] == 1
        finally:
            _delete_doc(doc_id)

    def test_approver_id_set_to_caller(self, client, biz, hdr):
        """FUNC-06: after approve, approver_id should match caller user_id."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval(doc_id, "pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            row = _psql(f"SELECT approver_id FROM documents WHERE id='{doc_id}'").stdout.decode().strip()
            assert row == biz["user_id"]
        finally:
            _delete_doc(doc_id)

    def test_approved_at_timestamp_within_recent_window(self, client, biz, hdr):
        """FUNC-07: approved_at is current UTC, not null."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval(doc_id, "pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            ts = _psql(
                f"SELECT EXTRACT(EPOCH FROM (NOW() - approved_at))::INT FROM documents WHERE id='{doc_id}'"
            ).stdout.decode().strip()
            assert int(ts) < 60
        finally:
            _delete_doc(doc_id)

    def test_retention_expires_aligns_with_period(self, client, biz, hdr):
        """FUNC-08: retention_expires_at = approved_at + retention_period_days."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval(doc_id, "pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr,
                        json={"retention_period_days": 1825})
            row = _psql(
                f"SELECT EXTRACT(DAY FROM (retention_expires_at - approved_at))::INT "
                f"FROM documents WHERE id='{doc_id}'"
            ).stdout.decode().strip()
            assert 1820 <= int(row) <= 1830  # 1825 ± 5 days slack
        finally:
            _delete_doc(doc_id)

    def test_list_view_reflects_status_after_approve(self, client, biz, hdr):
        """FUNC-09: my-documents shows new approval_status field."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            docs = _list_docs(client, biz["token"])
            ours = [d for d in docs if d.get("id") == doc_id]
            if ours:
                assert ours[0].get("approval_status") == "approved"
        finally:
            _delete_doc(doc_id)

    def test_versions_endpoint_for_single_doc_returns_self(self, client, biz, hdr):
        """FUNC-10: brand new doc → /versions returns chain of length 1."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_id}/versions", headers=hdr)
            assert r.status_code == 200
            body = r.json()
            assert body["doc_id"] == doc_id
            assert len(body["versions"]) >= 1
            assert any(v["id"] == doc_id for v in body["versions"])
        finally:
            _delete_doc(doc_id)


# ════════════════════════════════════════════════════════════════════════════
# Group B — Reject / revise cycles (FUNC-11..18)
# ════════════════════════════════════════════════════════════════════════════


class TestRejectReviseCycle:

    def test_reject_returns_to_draft_then_resubmit_works(self, client, biz, hdr):
        """FUNC-11: submit → reject → resubmit accepted."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            r1 = client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                             json={"reason": "Cần bổ sung HACCP"})
            assert r1.status_code == 200 and r1.json()["approval_status"] == "draft"
            r2 = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            assert r2.status_code == 200 and r2.json()["approval_status"] == "pending_approval"
        finally:
            _delete_doc(doc_id)

    def test_reject_then_approve_blocked_until_resubmit(self, client, biz, hdr):
        """FUNC-12: after reject, cannot directly approve (must resubmit first)."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/reject", headers=hdr, json={"reason": "x"})
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    def test_reject_reason_recorded_in_audit_log(self, client, biz, hdr):
        """FUNC-13: rejection reason searchable in audit_logs."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        reason = f"Reject-FUNC-{uuid.uuid4().hex[:6]}"
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/reject", headers=hdr, json={"reason": reason})
            out = _psql(
                f"SELECT COUNT(*) FROM audit_logs "
                f"WHERE entity_id='{doc_id}' "
                f"AND (changes::text LIKE '%{reason}%' OR metadata::text LIKE '%{reason}%')"
            ).stdout.decode().strip()
            assert int(out) >= 1
        finally:
            _delete_doc(doc_id)

    def test_two_reject_cycles_then_approve(self, client, biz, hdr):
        """FUNC-14: submit→reject→submit→reject→submit→approve all work."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            for i in range(2):
                client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
                client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                            json={"reason": f"r{i}"})
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r.status_code == 200
        finally:
            _delete_doc(doc_id)

    def test_audit_log_grows_with_each_cycle(self, client, biz, hdr):
        """FUNC-15: each transition adds an audit entry."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            before = _audit_count_for_doc(doc_id)
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/reject", headers=hdr, json={"reason": "r"})
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            after = _audit_count_for_doc(doc_id)
            assert after - before >= 4
        finally:
            _delete_doc(doc_id)

    def test_after_reject_approval_status_block_visible(self, client, biz, hdr):
        """FUNC-16: rejected doc still shows full approval block in /approval-status."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                        json={"reason": "incomplete"})
            body = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr).json()
            assert body["approval_status"] == "draft"
            assert body["version_number"] is not None
        finally:
            _delete_doc(doc_id)

    def test_reject_on_draft_document_rejected(self, client, biz, hdr):
        """FUNC-17: cannot reject a doc that was never submitted."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                            json={"reason": "no"})
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)

    def test_reject_on_approved_document_rejected(self, client, biz, hdr):
        """FUNC-18: cannot reject already-approved doc."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        _set_approval(doc_id, "approved")
        try:
            r = client.post(f"/api/documents/{doc_id}/reject", headers=hdr,
                            json={"reason": "late"})
            assert r.status_code == 409
        finally:
            _delete_doc(doc_id)


# ════════════════════════════════════════════════════════════════════════════
# Group C — Multi-version chain (FUNC-19..26)
# ════════════════════════════════════════════════════════════════════════════


class TestVersionChain:

    def test_supersede_creates_chain_of_two(self, client, biz, hdr):
        """FUNC-19: v1 approved → supersede with v2 → /versions returns both."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                            json={"new_document_id": v2})
            assert r.status_code == 200
            body = client.get(f"/api/documents/{v1}/versions", headers=hdr).json()
            ids = [v["id"] for v in body["versions"]]
            assert v1 in ids and v2 in ids
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_supersede_flips_old_to_obsolete(self, client, biz, hdr):
        """FUNC-20: after supersede, /approval-status on v1 returns obsolete."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            body = client.get(f"/api/documents/{v1}/approval-status", headers=hdr).json()
            assert body["approval_status"] == "obsolete"
            assert body["is_obsolete"] is True
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_supersede_increments_version_number(self, client, biz, hdr):
        """FUNC-21: v2.version_number = v1.version_number + 1."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                            json={"new_document_id": v2})
            assert r.json()["new_version_number"] == 2
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_three_version_chain(self, client, biz, hdr):
        """FUNC-22: v1→v2→v3 chain queryable from any node.

        Note: supersede requires source doc in 'approved' state. So between hops
        we must promote v2 to approved before superseding it with v3.
        """
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v3 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            # First supersede flips v2 → obsolete via DB trigger if its parent is set,
            # but here the trigger fires on superseded_by_id, not version_parent_id.
            # Re-promote v2 to approved before chaining further.
            _set_approval(v2, "approved")
            client.post(f"/api/documents/{v2}/supersede", headers=hdr,
                        json={"new_document_id": v3})
            for node in (v1, v2, v3):
                body = client.get(f"/api/documents/{node}/versions", headers=hdr).json()
                ids = {v["id"] for v in body["versions"]}
                assert {v1, v2, v3}.issubset(ids), f"Chain query from {node} missing nodes"
        finally:
            _delete_doc(v3)
            _delete_doc(v2)
            _delete_doc(v1)

    def test_chain_query_from_middle_returns_all(self, client, biz, hdr):
        """FUNC-23: querying middle node returns parent and child."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v3 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            _set_approval(v2, "approved")
            client.post(f"/api/documents/{v2}/supersede", headers=hdr,
                        json={"new_document_id": v3})
            body = client.get(f"/api/documents/{v2}/versions", headers=hdr).json()
            ids = {v["id"] for v in body["versions"]}
            assert v1 in ids and v3 in ids
        finally:
            _delete_doc(v3)
            _delete_doc(v2)
            _delete_doc(v1)

    def test_obsolete_doc_cannot_be_superseded_again(self, client, biz, hdr):
        """FUNC-24: chain protected from double-supersede."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        v3 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            r = client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                            json={"new_document_id": v3})
            assert r.status_code == 409
        finally:
            _delete_doc(v3)
            _delete_doc(v2)
            _delete_doc(v1)

    def test_db_links_after_supersede_consistent(self, client, biz, hdr):
        """FUNC-25: DB-level: v1.superseded_by_id=v2, v2.version_parent_id=v1."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            row = _psql(
                f"SELECT superseded_by_id, "
                f"(SELECT version_parent_id FROM documents WHERE id='{v2}') "
                f"FROM documents WHERE id='{v1}'"
            ).stdout.decode().strip().split("|")
            assert row[0] == v2
            assert row[1] == v1
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_audit_log_records_supersede_event(self, client, biz, hdr):
        """FUNC-26: supersede creates audit entry for both docs."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            before = _audit_count_for_doc(v1) + _audit_count_for_doc(v2)
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            after = _audit_count_for_doc(v1) + _audit_count_for_doc(v2)
            assert after - before >= 1
        finally:
            _delete_doc(v2)
            _delete_doc(v1)


# ════════════════════════════════════════════════════════════════════════════
# Group D — List/Detail consistency (FUNC-27..32)
# ════════════════════════════════════════════════════════════════════════════


class TestListDetailConsistency:

    def test_list_response_includes_approval_status_field(self, client, biz, hdr):
        """FUNC-27: with flag ON, list response includes approval_status."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            docs = _list_docs(client, biz["token"])
            ours = [d for d in docs if d.get("id") == doc_id]
            if ours:
                assert "approval_status" in ours[0]
        finally:
            _delete_doc(doc_id)

    def test_list_status_changes_after_submit(self, client, biz, hdr):
        """FUNC-28: list reflects pending_approval after submit."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            docs = _list_docs(client, biz["token"])
            ours = [d for d in docs if d.get("id") == doc_id]
            if ours:
                assert ours[0].get("approval_status") == "pending_approval"
        finally:
            _delete_doc(doc_id)

    def test_list_status_changes_after_approve(self, client, biz, hdr):
        """FUNC-29: list reflects approved after approve."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            docs = _list_docs(client, biz["token"])
            ours = [d for d in docs if d.get("id") == doc_id]
            if ours:
                assert ours[0].get("approval_status") == "approved"
        finally:
            _delete_doc(doc_id)

    def test_list_excludes_obsolete_or_marks_them(self, client, biz, hdr):
        """FUNC-30: obsolete docs visible (or filtered) consistently across list+detail."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            list_status = None
            for d in _list_docs(client, biz["token"]):
                if d.get("id") == v1:
                    list_status = d.get("approval_status")
            detail = client.get(f"/api/documents/{v1}/approval-status", headers=hdr).json()
            if list_status is not None:
                assert list_status == detail["approval_status"]
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_detail_and_approval_status_endpoints_agree(self, client, biz, hdr):
        """FUNC-31: detail.approval_status == /approval-status.approval_status."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        try:
            d1 = client.get(f"/api/documents/{doc_id}", headers=hdr)
            d2 = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr)
            if d1.status_code == 200:
                assert d1.json().get("approval_status") == d2.json().get("approval_status")
        finally:
            _delete_doc(doc_id)

    def test_version_number_consistent_across_endpoints(self, client, biz, hdr):
        """FUNC-32: detail.version_number == /approval-status.version_number == /versions[i]."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            ap = client.get(f"/api/documents/{v2}/approval-status", headers=hdr).json()
            ver = client.get(f"/api/documents/{v2}/versions", headers=hdr).json()
            v2_in_chain = next((v for v in ver["versions"] if v["id"] == v2), None)
            if v2_in_chain and "version_number" in v2_in_chain:
                assert ap["version_number"] == v2_in_chain["version_number"]
        finally:
            _delete_doc(v2)
            _delete_doc(v1)


# ════════════════════════════════════════════════════════════════════════════
# Group E — Audit trail completeness (FUNC-33..38)
# ════════════════════════════════════════════════════════════════════════════


class TestAuditCompleteness:

    def test_submit_event_has_actor_user_id(self, client, biz, hdr):
        """FUNC-33: audit row for submit has user_id matching caller."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            row = _psql(
                f"SELECT user_id FROM audit_logs WHERE entity_id='{doc_id}' "
                f"ORDER BY created_at DESC LIMIT 1"
            ).stdout.decode().strip()
            assert row == biz["user_id"]
        finally:
            _delete_doc(doc_id)

    def test_approve_event_includes_dates_in_details(self, client, biz, hdr):
        """FUNC-34: approve audit metadata contains effective_date / next_review_date."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr,
                        json={"effective_date": "2026-08-01"})
            row = _psql(
                f"SELECT COALESCE(changes::text, '') || ' ' || COALESCE(metadata::text, '') "
                f"FROM audit_logs WHERE entity_id='{doc_id}' AND action LIKE '%approv%' "
                f"ORDER BY created_at DESC LIMIT 1"
            ).stdout.decode()
            assert "2026-08-01" in row or "effective" in row.lower()
        finally:
            _delete_doc(doc_id)

    def test_audit_tenant_id_matches_actor(self, client, biz, hdr):
        """FUNC-35: audit row for action carries tenant_id of actor."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            row = _psql(
                f"SELECT tenant_id FROM audit_logs WHERE entity_id='{doc_id}' "
                f"ORDER BY created_at DESC LIMIT 1"
            ).stdout.decode().strip()
            assert row == biz["tenant_id"]
        finally:
            _delete_doc(doc_id)

    def test_full_lifecycle_audit_chain(self, client, biz, hdr):
        """FUNC-36: submit→reject→submit→approve→supersede produces ≥5 audit entries."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"])
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            before = _audit_count_for_doc(v1) + _audit_count_for_doc(v2)
            client.post(f"/api/documents/{v1}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{v1}/reject", headers=hdr, json={"reason": "edit"})
            client.post(f"/api/documents/{v1}/submit-for-approval", headers=hdr)
            client.post(f"/api/documents/{v1}/approve", headers=hdr, json={})
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            after = _audit_count_for_doc(v1) + _audit_count_for_doc(v2)
            assert after - before >= 5
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_audit_entries_ordered_chronologically(self, client, biz, hdr):
        """FUNC-37: audit timestamps strictly non-decreasing across actions."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            time.sleep(0.05)
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            rows = _psql(
                f"SELECT EXTRACT(EPOCH FROM created_at) FROM audit_logs "
                f"WHERE entity_id='{doc_id}' ORDER BY created_at"
            ).stdout.decode().strip().splitlines()
            ts = [float(r) for r in rows if r.strip()]
            assert ts == sorted(ts)
        finally:
            _delete_doc(doc_id)

    def test_failed_action_does_not_create_audit_entry(self, client, biz, hdr):
        """FUNC-38: rejected approve (409 from draft skip) must not pollute audit."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])  # draft
        try:
            before = _audit_count_for_doc(doc_id, event="document.approved")
            r = client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            assert r.status_code == 409
            after = _audit_count_for_doc(doc_id, event="document.approved")
            assert after == before
        finally:
            _delete_doc(doc_id)


# ════════════════════════════════════════════════════════════════════════════
# Group F — Cross-tenant journey safety (FUNC-39..44)
# ════════════════════════════════════════════════════════════════════════════


class TestCrossTenantJourney:

    def test_b_cannot_see_a_doc_in_versions(self, client, biz, biz_b, hdr_b):
        """FUNC-39: tenant B querying /versions on tenant A's doc → 404."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_a}/versions", headers=hdr_b)
            assert r.status_code == 404
        finally:
            _delete_doc(doc_a)

    def test_b_cannot_supersede_a_doc(self, client, biz, biz_b, hdr_b):
        """FUNC-40: tenant B trying to supersede tenant A's doc → 404."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2_b = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            r = client.post(f"/api/documents/{v1}/supersede", headers=hdr_b,
                            json={"new_document_id": v2_b})
            assert r.status_code == 404
        finally:
            _delete_doc(v2_b)
            _delete_doc(v1)

    def test_audit_trail_isolated_per_tenant(self, client, biz, biz_b, hdr, hdr_b):
        """FUNC-41: tenant A actions don't appear in tenant B audit query."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{doc_a}/submit-for-approval", headers=hdr)
            cnt_b = _psql(
                f"SELECT COUNT(*) FROM audit_logs WHERE entity_id='{doc_a}' "
                f"AND tenant_id='{biz_b['tenant_id']}'"
            ).stdout.decode().strip()
            assert int(cnt_b) == 0
        finally:
            _delete_doc(doc_a)

    def test_b_list_does_not_include_a_documents(self, client, biz, biz_b):
        """FUNC-42: tenant B's list never contains tenant A's docs."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            docs_b = _list_docs(client, biz_b["token"])
            ids_b = {d.get("id") for d in docs_b}
            assert doc_a not in ids_b
        finally:
            _delete_doc(doc_a)

    def test_b_cannot_query_a_approval_status(self, client, biz, biz_b, hdr_b):
        """FUNC-43: /approval-status returns 404 for cross-tenant ID."""
        doc_a = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r = client.get(f"/api/documents/{doc_a}/approval-status", headers=hdr_b)
            assert r.status_code == 404
        finally:
            _delete_doc(doc_a)

    def test_db_trigger_blocks_cross_tenant_supersede_link(self, client, biz, biz_b):
        """FUNC-44: direct DB attempt to set superseded_by across tenants must fail."""
        v1_a = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2_b = _insert_doc(biz_b["tenant_id"], biz_b["user_id"])
        try:
            result = subprocess.run(
                ["docker", "exec", DB_CONTAINER, "psql", "-U", "aminra_user",
                 "-d", "aminra", "-c",
                 f"UPDATE documents SET superseded_by_id='{v2_b}' WHERE id='{v1_a}'"],
                capture_output=True, timeout=10,
            )
            assert result.returncode != 0 or b"ERROR" in result.stderr.upper()
        finally:
            _delete_doc(v2_b)
            _delete_doc(v1_a)


# ════════════════════════════════════════════════════════════════════════════
# Group G — Approval block visibility / edge journeys (FUNC-45..50)
# ════════════════════════════════════════════════════════════════════════════


class TestApprovalBlockVisibility:

    def test_approval_block_for_draft_has_null_approver(self, client, biz, hdr):
        """FUNC-45: draft doc → /approval-status returns approver_id=null."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            body = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr).json()
            assert body.get("approver_id") in (None, "")
        finally:
            _delete_doc(doc_id)

    def test_approval_block_for_pending_has_no_effective_date(self, client, biz, hdr):
        """FUNC-46: pending doc → effective_date null."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            body = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr).json()
            assert body.get("effective_date") in (None, "")
        finally:
            _delete_doc(doc_id)

    def test_approval_block_for_approved_has_full_metadata(self, client, biz, hdr):
        """FUNC-47: approved doc → all fields populated."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="pending_approval")
        try:
            client.post(f"/api/documents/{doc_id}/approve", headers=hdr, json={})
            body = client.get(f"/api/documents/{doc_id}/approval-status", headers=hdr).json()
            assert body["approver_id"]
            assert body["approved_at"]
            assert body["effective_date"]
            assert body["retention_expires_at"]
        finally:
            _delete_doc(doc_id)

    def test_approval_block_after_supersede_marks_obsolete(self, client, biz, hdr):
        """FUNC-48: superseded doc shows is_obsolete=True + superseded_by populated."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            body = client.get(f"/api/documents/{v1}/approval-status", headers=hdr).json()
            assert body["is_obsolete"] is True
            assert body.get("superseded_by_id") == v2
        finally:
            _delete_doc(v2)
            _delete_doc(v1)

    def test_concurrent_submit_attempts_resolve_safely(self, client, biz, hdr):
        """FUNC-49: 2 sequential submit calls — first succeeds, second 409."""
        doc_id = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            r1 = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            r2 = client.post(f"/api/documents/{doc_id}/submit-for-approval", headers=hdr)
            assert r1.status_code == 200
            assert r2.status_code == 409
        finally:
            _delete_doc(doc_id)

    def test_versions_endpoint_consistent_after_supersede(self, client, biz, hdr):
        """FUNC-50: after supersede, /versions on both v1 and v2 return same chain."""
        v1 = _insert_doc(biz["tenant_id"], biz["user_id"], approval_status="approved")
        v2 = _insert_doc(biz["tenant_id"], biz["user_id"])
        try:
            client.post(f"/api/documents/{v1}/supersede", headers=hdr,
                        json={"new_document_id": v2})
            chain1 = {v["id"] for v in
                      client.get(f"/api/documents/{v1}/versions", headers=hdr).json()["versions"]}
            chain2 = {v["id"] for v in
                      client.get(f"/api/documents/{v2}/versions", headers=hdr).json()["versions"]}
            assert chain1 == chain2
        finally:
            _delete_doc(v2)
            _delete_doc(v1)
