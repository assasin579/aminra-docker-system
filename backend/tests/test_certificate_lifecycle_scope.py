"""P0 certificate lifecycle provider-scope regression tests.

A provider must never be able to revoke or mutate another provider's
certificate. This complements route-level RBAC by pinning the service invariant:
cert.issued_by must match the actor that performs the lifecycle mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord

pytestmark = pytest.mark.asyncio


class TestCertificateLifecycleProviderScope:
    async def test_revoke_rejects_cross_provider_actor_before_mutation(self):
        from services.cert_lifecycle import InvalidRevocation, revoke_cert

        cert_id = uuid4()
        owner_provider_id = uuid4()
        attacker_provider_id = uuid4()
        db = FakeConn()
        db.fetchrow_responses = [
            (
                "FROM halal_certificates WHERE id = $1",
                FakeRecord(
                    id=cert_id,
                    cert_number="HALAL-2026-0042",
                    business_tenant=uuid4(),
                    issued_by=owner_provider_id,
                    status="active",
                    revoked_at=None,
                ),
            ),
        ]

        with pytest.raises(InvalidRevocation, match="provider scope"):
            await revoke_cert(
                db,
                cert_id=str(cert_id),
                reason="malicious cross-provider revoke",
                revoked_by_user_id=str(attacker_provider_id),
            )

        assert not any(
            call[0] == "fetchrow" and "UPDATE halal_certificates" in call[1][0]
            for call in db.calls
        ), "cross-provider revoke must fail before UPDATE"

    async def test_revoke_allows_owning_provider_and_persists_reason(self):
        from services.cert_lifecycle import revoke_cert

        cert_id = uuid4()
        provider_id = uuid4()
        db = FakeConn()
        db.fetchrow_responses = [
            (
                "FROM halal_certificates WHERE id = $1",
                FakeRecord(
                    id=cert_id,
                    cert_number="HALAL-2026-0043",
                    business_tenant=uuid4(),
                    issued_by=provider_id,
                    status="active",
                    revoked_at=None,
                ),
            ),
            ("UPDATE halal_certificates", FakeRecord(revoked_at=datetime.now(timezone.utc))),
        ]

        result = await revoke_cert(
            db,
            cert_id=str(cert_id),
            reason="owner-provider revocation",
            revoked_by_user_id=str(provider_id),
        )

        assert result.cert_number == "HALAL-2026-0043"
        assert result.reason == "owner-provider revocation"
