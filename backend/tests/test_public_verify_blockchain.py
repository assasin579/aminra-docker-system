"""Test the public verify endpoint includes blockchain anchor info."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from tests.test_certificate_pdf_integration import FakeConn, FakeRecord


CERT_ID = uuid4()


def _cert_row(status: str = "active", revoked: bool = False):
    return FakeRecord(
        id=CERT_ID,
        cert_number="HALAL-2026-0042",
        company_name="Halal Foods Co",
        issue_date=date(2026, 4, 25),
        expiry_date=date(2027, 4, 25),
        status=status,
        provider_name="Halal Cert Vietnam",
        revocation_reason="Vi phạm chuẩn" if revoked else None,
        revoked_at=datetime(2026, 5, 1, tzinfo=timezone.utc) if revoked else None,
        revoked_by=uuid4() if revoked else None,
    )


def _proof_row():
    return FakeRecord(
        leaf_hash="9a7b3c" * 10 + "abcd",  # 64 hex
        leaf_index=42,
        proof_path=json.dumps([
            {"sibling": "1" * 64, "position": "right"},
            {"sibling": "2" * 64, "position": "left"},
        ]),
        anchor_id=uuid4(),
        chain="polygon",
        merkle_root="0x" + "4f3a" * 16,
        tx_hash="0x" + "9e7c" * 16,
        block_number=50_123_456,
        confirmed_at=datetime(2026, 4, 25, 23, 5, tzinfo=timezone.utc),
        anchor_status="confirmed",
    )


# ── Cert without anchor ────────────────────────────────────────────────────

class TestNoAnchor:
    async def test_unanchored_cert_shows_pending_status(self):
        from auth.certificate_router import public_verify_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", _cert_row()),
            ("FROM cert_anchor_proofs", None),  # no anchor proof yet
        ]
        result = await public_verify_cert(cert_number="HALAL-2026-0042", db=db)

        assert result["valid"] is True
        assert result["blockchain"]["anchored"] is False
        assert "Anchor pending" in result["blockchain"]["note"]


# ── Cert with anchor ───────────────────────────────────────────────────────

class TestWithAnchor:
    async def test_anchored_cert_returns_full_blockchain_proof(self):
        from auth.certificate_router import public_verify_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", _cert_row()),
            ("FROM cert_anchor_proofs", _proof_row()),
        ]
        result = await public_verify_cert(cert_number="HALAL-2026-0042", db=db)

        bc = result["blockchain"]
        assert bc["anchored"] is True
        assert bc["chain"] == "polygon"
        assert bc["merkle_root"].startswith("0x")
        assert bc["tx_hash"].startswith("0x")
        assert bc["block_number"] == 50_123_456
        assert bc["explorer_url"] == f"https://polygonscan.com/tx/{bc['tx_hash']}"
        assert isinstance(bc["merkle_proof"], list)
        assert len(bc["merkle_proof"]) == 2
        assert bc["merkle_proof"][0]["position"] == "right"
        assert "verify_instructions" in bc

    async def test_bitcoin_anchor_uses_btc_explorer(self):
        from auth.certificate_router import public_verify_cert

        proof = _proof_row()
        # Override chain to bitcoin
        btc_proof = FakeRecord(**{**dict(proof), "chain": "bitcoin"})

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", _cert_row()),
            ("FROM cert_anchor_proofs", btc_proof),
        ]
        result = await public_verify_cert(cert_number="HALAL-2026-0042", db=db)
        assert result["blockchain"]["chain"] == "bitcoin"
        assert "blockchain.com/btc/tx" in result["blockchain"]["explorer_url"]


# ── 404 path ───────────────────────────────────────────────────────────────

class TestNotFound:
    async def test_unknown_cert_404(self):
        from fastapi import HTTPException
        from auth.certificate_router import public_verify_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", None),
        ]
        with pytest.raises(HTTPException) as exc:
            await public_verify_cert(cert_number="DOES-NOT-EXIST", db=db)
        assert exc.value.status_code == 404


# ── Status edge cases ──────────────────────────────────────────────────────

class TestStatusEdgeCases:
    async def test_expired_cert_marked_expired_even_if_active(self):
        from auth.certificate_router import public_verify_cert

        # Cert with past expiry but DB status = active
        expired = FakeRecord(
            id=CERT_ID,
            cert_number="HALAL-2025-0001",
            company_name="X",
            issue_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),  # expired
            status="active",
            provider_name="Y",
        )
        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", expired),
            ("FROM cert_anchor_proofs", _proof_row()),
        ]
        result = await public_verify_cert(cert_number="HALAL-2025-0001", db=db)
        assert result["status"] == "expired"
        assert result["valid"] is False
        # Anchor still attached — historical evidence, not invalidated by expiry
        assert result["blockchain"]["anchored"] is True

    async def test_revoked_cert_keeps_anchor_visible(self):
        """Revoked cert is forensically important — keep blockchain proof
        visible so observers can see when it WAS valid."""
        from auth.certificate_router import public_verify_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", _cert_row(status="revoked", revoked=True)),
            ("FROM cert_anchor_proofs", _proof_row()),
        ]
        result = await public_verify_cert(cert_number="HALAL-2026-0042", db=db)
        assert result["status"] == "revoked"
        assert result["valid"] is False
        assert result["blockchain"]["anchored"] is True
        # Revocation details exposed (Gap 3)
        assert result["revocation"] is not None
        assert result["revocation"]["reason"] == "Vi phạm chuẩn"
        assert result["revocation"]["revoked_at"] is not None

    async def test_active_cert_revocation_field_is_none(self):
        from auth.certificate_router import public_verify_cert

        db = FakeConn()
        db.fetchrow_responses = [
            ("FROM halal_certificates", _cert_row(status="active", revoked=False)),
            ("FROM cert_anchor_proofs", None),
        ]
        result = await public_verify_cert(cert_number="HALAL-2026-0042", db=db)
        assert result["revocation"] is None
