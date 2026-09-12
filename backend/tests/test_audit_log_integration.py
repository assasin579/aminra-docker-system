"""Integration tests for the audit_log admin endpoint + cert-issue wiring.

These tests don't hit the live container — they construct router functions
directly with a FakeConn so we can verify (a) the admin endpoint composes
the right query + serializes rows, (b) the cert-issue endpoint actually
records an audit entry as a side-effect.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


ADMIN_USER = {
    "sub":   str(uuid4()),
    "email": "admin@aminra.com",
    "role":  "admin",
}


# ── Admin endpoint: list_audit_logs ─────────────────────────────────────────

class TestListAuditLogsEndpoint:
    async def test_returns_serialized_logs_with_paging(self):
        from auth.audit_log_router import list_audit_logs

        log_id = uuid4()
        user_id = uuid4()
        tenant_id = uuid4()
        entity_id = uuid4()
        when = datetime(2026, 4, 25, 10, 30, tzinfo=timezone.utc)

        db = FakeConn()
        db.fetch_responses = [
            ("SELECT * FROM audit_logs", [
                FakeRecord(
                    id=log_id,
                    user_id=user_id,
                    user_email="biz@example.vn",
                    user_role="business",
                    tenant_id=tenant_id,
                    action="certificate.issue",
                    entity_type="certificate",
                    entity_id=entity_id,
                    changes=None,
                    metadata=json.dumps({"ip": "1.2.3.4"}),
                    created_at=when,
                ),
            ]),
        ]
        db.fetchval_responses = [
            ("SELECT COUNT(*) FROM audit_logs", 1),
        ]

        result = await list_audit_logs(
            user_id=None, tenant_id=None, action=None,
            entity_type=None, entity_id=None,
            from_date=None, to_date=None,
            page=1, limit=50, sort="created_at", order="desc",
            admin=ADMIN_USER, db=db,
        )

        assert result["total"] == 1
        assert result["page"] == 1
        assert len(result["logs"]) == 1
        log_row = result["logs"][0]
        assert log_row["id"] == str(log_id)
        assert log_row["user_email"] == "biz@example.vn"
        assert log_row["action"] == "certificate.issue"
        assert log_row["metadata"] == {"ip": "1.2.3.4"}
        assert log_row["changes"] is None
        assert log_row["created_at"] == when.isoformat()

    async def test_invalid_filter_field_returns_400(self):
        from fastapi import HTTPException
        from auth.audit_log_router import list_audit_logs

        db = FakeConn()
        with pytest.raises(HTTPException) as exc:
            await list_audit_logs(
                user_id=None, tenant_id=None, action=None,
                entity_type=None, entity_id=None,
                from_date=None, to_date=None,
                page=1, limit=50, sort="; DROP TABLE", order="desc",
                admin=ADMIN_USER, db=db,
            )
        assert exc.value.status_code == 400


# ── Cross-cutting: cert issue records an audit entry ────────────────────────

class TestCertIssueEmitsAuditLog:
    async def test_issue_certificate_inserts_audit_log_row(self, monkeypatch, tmp_path):
        from auth.certificate_router import issue_certificate_for_company, IssueCertRequest

        monkeypatch.setenv("CERT_PDF_DIR", str(tmp_path / "certs"))
        monkeypatch.setenv("APP_BASE_URL", "https://aminra.test")
        import importlib
        from auth import certificate_router
        importlib.reload(certificate_router)

        BUSINESS_TENANT_ID = uuid4()
        PROVIDER_USER_ID = uuid4()
        BUSINESS_OWNER_ID = uuid4()

        provider_user = {
            "sub":       str(PROVIDER_USER_ID),
            "email":     "cb@example.vn",
            "role":      "provider",
            "is_owner":  True,
            "tenant_id": str(uuid4()),
        }

        db = FakeConn()
        db.fetch_responses = [
            ("FROM submissions WHERE business_tenant", [
                FakeRecord(id=uuid4(), status="approved"),
            ]),
        ]
        db.fetchrow_responses = [
            ("FROM halal_certificates WHERE business_tenant=$1 AND issued_by=$2 AND status='active'", None),
            ("FROM users WHERE id=$1", FakeRecord(company_name="Halal CB Vietnam")),
            ("(id=$1 OR tenant_id=$1) AND is_owner=true",
             FakeRecord(id=BUSINESS_OWNER_ID, company_name="Halal Foods Co")),
            ("INSERT INTO halal_certificates", FakeRecord(id=uuid4())),
        ]
        db.fetchval_responses = [
            ("COUNT(*) FROM halal_certificates WHERE cert_number LIKE", 0),
        ]

        await certificate_router.issue_certificate_for_company(
            business_tenant_id=str(BUSINESS_TENANT_ID),
            req=IssueCertRequest(),
            user=provider_user,
            db=db,
        )

        # Find the audit-log execute call
        audit_calls = [
            (sql, args) for kind, (sql, args) in db.calls
            if kind == "execute" and "INSERT INTO audit_logs" in sql
        ]
        assert len(audit_calls) == 1, f"expected 1 audit-log insert, got {len(audit_calls)}"

        _, args = audit_calls[0]
        # Positional: user_id, email, role, tenant_id, action, entity_type, entity_id, changes, metadata
        assert str(args[0]) == provider_user["sub"]
        assert args[1] == "cb@example.vn"
        assert args[2] == "provider"
        assert args[4] == "certificate.issue"
        assert args[5] == "certificate"
        meta = json.loads(args[8])
        assert meta["business_tenant"] == str(BUSINESS_TENANT_ID)
        assert meta["cert_number"].startswith(f"HALAL-{datetime.utcnow().year}-")


# ── Cross-cutting: cert status change records audit log ─────────────────────

class TestCertStatusChangeEmitsAuditLog:
    async def test_revoke_records_status_diff(self):
        from auth.certificate_router import update_cert_status

        cert_id = uuid4()
        provider_user = {
            "sub":      str(uuid4()),
            "email":    "cb@example.vn",
            "role":     "provider",
            "is_owner": True,
        }

        db = FakeConn()
        db.fetchrow_responses = [
            ("SELECT * FROM halal_certificates WHERE id=$1 AND issued_by=$2",
             FakeRecord(
                 id=cert_id,
                 cert_number="HALAL-2026-0001",
                 status="active",
                 business_tenant=uuid4(),
             )),
            # revoke_cert() preflight check
            ("SELECT id, cert_number, business_tenant, status, revoked_at",
             FakeRecord(
                 id=cert_id,
                 cert_number="HALAL-2026-0001",
                 business_tenant=uuid4(),
                 status="active",
                 revoked_at=None,
             )),
            # revoke_cert() UPDATE...RETURNING
            ("UPDATE halal_certificates",
             FakeRecord(revoked_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))),
            ("(id=$1 OR tenant_id=$1) AND is_owner=true", None),  # no biz owner → notify skipped
        ]

        await update_cert_status(
            cert_id=str(cert_id),
            req={"status": "revoked", "reason": "Vi phạm tiêu chuẩn"},
            user=provider_user,
            db=db,
        )

        # Find audit log insert
        audit_calls = [
            (sql, args) for kind, (sql, args) in db.calls
            if kind == "execute" and "INSERT INTO audit_logs" in sql
        ]
        assert len(audit_calls) == 1
        _, args = audit_calls[0]
        assert args[4] == "certificate.status_change"
        assert json.loads(args[7]) == {"status": ["active", "revoked"]}
        meta = json.loads(args[8])
        assert meta["reason"] == "Vi phạm tiêu chuẩn"
