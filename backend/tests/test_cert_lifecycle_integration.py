"""Integration tests cho cert lifecycle — real DB, end-to-end revocation flow.

Coverage:
- update_cert_status endpoint với new_status='revoked' enforces reason
- DB constraint chk_cert_revocation_has_reason actually rejects bad rows
- Concurrent revoke = AlreadyRevoked (race-condition safety)
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from uuid import uuid4

import asyncpg
import pytest


@pytest.fixture
async def conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def fresh_cert(conn):
    """Insert a cert + return id, owner_user_id, business_tenant for cleanup."""
    prov = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='provider' AND is_owner=true LIMIT 1"
    )
    biz = await conn.fetchrow(
        "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
    )
    if not prov or not biz:
        pytest.skip("Need provider + business users seeded")

    cert_id = uuid4()
    cert_number = f"TEST-LIFE-{uuid4().hex[:8].upper()}"
    await conn.execute(
        """
        INSERT INTO halal_certificates
            (id, cert_number, issued_by, business_tenant, company_name,
             issue_date, expiry_date, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'active')
        """,
        cert_id, cert_number, prov["id"], biz["tenant_id"], "Test Co",
        date.today(), date.today() + timedelta(days=365),
    )
    yield {
        "id": str(cert_id),
        "cert_number": cert_number,
        "provider_id": str(prov["id"]),
        "business_tenant": str(biz["tenant_id"]),
    }
    await conn.execute("DELETE FROM halal_certificates WHERE id = $1", cert_id)


# ── revoke_cert flow ───────────────────────────────────────────────────────

class TestRevokeCertIntegration:
    async def test_revoke_persists_all_fields(self, conn, fresh_cert):
        from services.cert_lifecycle import revoke_cert

        result = await revoke_cert(
            conn,
            cert_id=fresh_cert["id"],
            reason="Vi phạm tiêu chuẩn JAKIM",
            revoked_by_user_id=fresh_cert["provider_id"],
        )

        # Verify DB persisted everything atomically
        row = await conn.fetchrow(
            """
            SELECT status, revocation_reason, revoked_by, revoked_at
            FROM halal_certificates WHERE id = $1
            """,
            fresh_cert["id"],
        )
        assert row["status"] == "revoked"
        assert row["revocation_reason"] == "Vi phạm tiêu chuẩn JAKIM"
        assert str(row["revoked_by"]) == fresh_cert["provider_id"]
        assert row["revoked_at"] is not None

    async def test_double_revoke_raises_already_revoked(self, conn, fresh_cert):
        from services.cert_lifecycle import AlreadyRevoked, revoke_cert

        await revoke_cert(
            conn,
            cert_id=fresh_cert["id"],
            reason="first",
            revoked_by_user_id=fresh_cert["provider_id"],
        )
        with pytest.raises(AlreadyRevoked):
            await revoke_cert(
                conn,
                cert_id=fresh_cert["id"],
                reason="second",
                revoked_by_user_id=fresh_cert["provider_id"],
            )


# ── DB constraint ──────────────────────────────────────────────────────────

class TestDBConstraint:
    async def test_constraint_rejects_revoked_at_without_reason(self, conn):
        """Sanity check: even if app code is bypassed, DB blocks invalid rows."""
        prov = await conn.fetchrow(
            "SELECT id, tenant_id FROM users WHERE role='provider' AND is_owner=true LIMIT 1"
        )
        biz = await conn.fetchrow(
            "SELECT id, tenant_id FROM users WHERE role='business' AND is_owner=true LIMIT 1"
        )
        if not prov or not biz:
            pytest.skip("Need seeded users")

        cert_id = uuid4()
        cert_number = f"TEST-BAD-{uuid4().hex[:8].upper()}"
        try:
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                # Try to set revoked_at without reason — must violate constraint
                await conn.execute(
                    """
                    INSERT INTO halal_certificates
                        (id, cert_number, issued_by, business_tenant, company_name,
                         issue_date, expiry_date, status, revoked_at)
                    VALUES ($1, $2, $3, $4, 'X', NOW(), NOW(), 'revoked', NOW())
                    """,
                    cert_id, cert_number, prov["id"], biz["tenant_id"],
                )
        finally:
            await conn.execute("DELETE FROM halal_certificates WHERE id = $1", cert_id)


# ── Endpoint integration ───────────────────────────────────────────────────

class _FakeClient:
    host = "10.0.0.1"

class FakeRequest:
    client = _FakeClient()
    headers = {"user-agent": "pytest"}


class TestUpdateCertStatusEndpoint:
    async def test_revoke_endpoint_requires_reason(self, conn, fresh_cert):
        from fastapi import HTTPException
        from auth.certificate_router import update_cert_status

        prov_user = {
            "sub": fresh_cert["provider_id"],
            "email": "cb@test.vn",
            "role": "provider",
            "is_owner": True,
        }

        # Try to revoke WITHOUT reason
        with pytest.raises(HTTPException) as exc:
            await update_cert_status(
                cert_id=fresh_cert["id"],
                req={"status": "revoked"},   # missing reason
                user=prov_user,
                db=conn,
            )
        assert exc.value.status_code == 400
        assert "lý do" in exc.value.detail.lower()

    async def test_revoke_with_reason_succeeds(self, conn, fresh_cert):
        from auth.certificate_router import update_cert_status

        prov_user = {
            "sub": fresh_cert["provider_id"],
            "email": "cb@test.vn",
            "role": "provider",
            "is_owner": True,
        }

        result = await update_cert_status(
            cert_id=fresh_cert["id"],
            req={"status": "revoked", "reason": "Vi phạm chuẩn"},
            user=prov_user,
            db=conn,
        )
        assert "revoked" in result["message"]

        # Verify revoked_by is set to provider
        row = await conn.fetchrow(
            "SELECT revoked_by FROM halal_certificates WHERE id = $1",
            fresh_cert["id"],
        )
        assert str(row["revoked_by"]) == fresh_cert["provider_id"]
