"""Unit tests for services/anchor_bitcoin.py.

Calendar-server interaction is exercised separately (integration test, opt-in).
We focus here on:
- Input validation
- Bitcoin-attestation walk logic on hand-built timestamps
- verify_proof against complete proofs (with simulated BTC attestation)
"""
from __future__ import annotations

import base64
from io import BytesIO

import pytest


# ── Validation ─────────────────────────────────────────────────────────────

class TestValidation:
    def test_rejects_wrong_digest_size(self):
        from services.anchor_bitcoin import submit_digest
        with pytest.raises(ValueError, match="32 bytes"):
            submit_digest(b"\xab" * 16)
        with pytest.raises(ValueError, match="32 bytes"):
            submit_digest(b"\xab" * 64)


# ── Bitcoin attestation walk logic ─────────────────────────────────────────

class TestAttestationDetection:
    def test_finds_btc_attestation_at_root(self):
        from opentimestamps.core.timestamp import Timestamp
        from opentimestamps.core.notary import BitcoinBlockHeaderAttestation
        from services.anchor_bitcoin import _has_bitcoin_attestation, _find_btc_height

        digest = b"\xab" * 32
        ts = Timestamp(digest)
        ts.attestations.add(BitcoinBlockHeaderAttestation(height=850000))

        assert _has_bitcoin_attestation(ts) is True
        assert _find_btc_height(ts) == 850000

    def test_no_attestation_returns_false(self):
        from opentimestamps.core.timestamp import Timestamp
        from services.anchor_bitcoin import _has_bitcoin_attestation, _find_btc_height

        ts = Timestamp(b"\xcd" * 32)
        assert _has_bitcoin_attestation(ts) is False
        assert _find_btc_height(ts) is None

    def test_only_pending_attestation_returns_false(self):
        from opentimestamps.core.timestamp import Timestamp
        from opentimestamps.core.notary import PendingAttestation
        from services.anchor_bitcoin import _has_bitcoin_attestation

        ts = Timestamp(b"\xef" * 32)
        # PendingAttestation = waiting for Bitcoin block; not the same as confirmed
        ts.attestations.add(PendingAttestation(uri="https://alice.btc.calendar.opentimestamps.org"))
        assert _has_bitcoin_attestation(ts) is False


# ── verify_proof ───────────────────────────────────────────────────────────

class TestVerifyProof:
    def _build_proof_b64(self, digest: bytes, *, with_btc_height: int | None = None) -> str:
        """Helper: build a serializable .ots proof with at least one attestation."""
        from opentimestamps.core.timestamp import (
            DetachedTimestampFile, OpSHA256, Timestamp,
        )
        from opentimestamps.core.notary import (
            BitcoinBlockHeaderAttestation, PendingAttestation,
        )
        from opentimestamps.core.serialize import StreamSerializationContext

        ts = Timestamp(digest)
        if with_btc_height is not None:
            ts.attestations.add(BitcoinBlockHeaderAttestation(height=with_btc_height))
        else:
            ts.attestations.add(PendingAttestation(uri="https://test.calendar"))
        detached = DetachedTimestampFile(file_hash_op=OpSHA256(), timestamp=ts)

        buf = BytesIO()
        detached.serialize(StreamSerializationContext(buf))
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def test_complete_proof_with_btc_verifies(self):
        from services.anchor_bitcoin import verify_proof

        digest = b"\xab" * 32
        proof_b64 = self._build_proof_b64(digest, with_btc_height=850000)

        verified, height = verify_proof(proof_b64, digest)
        assert verified is True
        assert height == 850000

    def test_pending_proof_returns_false(self):
        """Calendar-only proof (still waiting for Bitcoin block) — not yet verifiable."""
        from services.anchor_bitcoin import verify_proof

        digest = b"\xcd" * 32
        proof_b64 = self._build_proof_b64(digest)  # no btc height → only pending

        verified, height = verify_proof(proof_b64, digest)
        assert verified is False
        assert height is None

    def test_verify_rejects_wrong_digest(self):
        """Forge attempt: claim a proof is for a different digest."""
        from services.anchor_bitcoin import verify_proof

        original = b"\x01" * 32
        wrong = b"\x02" * 32
        proof_b64 = self._build_proof_b64(original, with_btc_height=850000)

        verified, _ = verify_proof(proof_b64, wrong)
        assert verified is False


# ── OtsResult shape ────────────────────────────────────────────────────────

class TestOtsResult:
    def test_dataclass_has_expected_fields(self):
        from services.anchor_bitcoin import OtsResult
        result = OtsResult(proof_b64="abcd", is_complete=False)
        assert result.proof_b64 == "abcd"
        assert result.is_complete is False
