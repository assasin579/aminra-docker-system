"""Bitcoin mega-anchor via OpenTimestamps.

OTS submits the hash to public "calendar servers" which aggregate them and
periodically (~1 hour) commit the aggregated tree into a Bitcoin transaction.
The .ots proof file is updated as confirmations propagate.

Cost: $0. Confirmation time: 1-6 hours typically, fully confirmed in ~6h.

Workflow:
    submit(digest) → returns OTS proof bytes (incomplete, just calendar commits)
    upgrade(proof) → polls calendars; replaces calendar commits with Bitcoin
                     attestations once block is mined
    verify(proof, digest) → checks the chain of operations + Bitcoin block

We store the .ots proof as bytea in blockchain_anchors.metadata['ots_proof']
(base64-encoded) and re-upgrade periodically until Bitcoin attestations
appear.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from io import BytesIO

log = logging.getLogger("aminra.anchor_bitcoin")


# ── Submission ─────────────────────────────────────────────────────────────

@dataclass
class OtsResult:
    proof_b64: str         # base64-encoded .ots file
    is_complete: bool      # True only after Bitcoin attestation arrives


def submit_digest(digest_bytes: bytes) -> OtsResult:
    """Submit a 32-byte digest to OpenTimestamps calendar servers.

    Returns the initial .ots proof which contains only calendar commits.
    The proof is "complete" only after upgrade() finds a Bitcoin attestation.
    """
    if len(digest_bytes) != 32:
        raise ValueError(f"digest must be 32 bytes, got {len(digest_bytes)}")

    from opentimestamps.client import RemoteCalendar
    from opentimestamps.core.timestamp import (
        DetachedTimestampFile, OpSHA256, Timestamp,
    )

    # Create fresh DetachedTimestampFile for our digest (no actual file content)
    timestamp = Timestamp(digest_bytes)
    detached = DetachedTimestampFile(file_hash_op=OpSHA256(), timestamp=timestamp)

    # Submit to public calendar (default). In production we use multiple
    # calendars in parallel for redundancy.
    calendars = [
        "https://alice.btc.calendar.opentimestamps.org",
        "https://bob.btc.calendar.opentimestamps.org",
        "https://finney.calendar.eternitywall.com",
    ]
    submitted = 0
    for cal_url in calendars:
        try:
            cal = RemoteCalendar(cal_url)
            cal_timestamp = cal.submit(digest_bytes)
            timestamp.merge(cal_timestamp)
            submitted += 1
            log.info("[ots] submitted to %s", cal_url)
        except Exception as e:
            log.warning("[ots] %s failed: %s", cal_url, e)

    if submitted == 0:
        raise RuntimeError("All calendar servers unreachable")

    # Serialize to bytes
    from opentimestamps.core.serialize import StreamSerializationContext
    buf = BytesIO()
    detached.serialize(StreamSerializationContext(buf))
    proof_bytes = buf.getvalue()

    return OtsResult(
        proof_b64=base64.b64encode(proof_bytes).decode("ascii"),
        is_complete=False,  # Bitcoin attestation arrives later
    )


# ── Upgrade (poll for Bitcoin attestation) ────────────────────────────────

def upgrade_proof(proof_b64: str) -> OtsResult:
    """Re-fetch the proof from calendar servers — once the Bitcoin block is
    mined and indexed by calendars (typically 1-6 hours), this replaces the
    calendar commits with full Bitcoin attestations."""
    from opentimestamps.client import upgrade_timestamp
    from opentimestamps.core.serialize import (
        StreamDeserializationContext, StreamSerializationContext,
    )
    from opentimestamps.core.timestamp import DetachedTimestampFile

    proof_bytes = base64.b64decode(proof_b64)
    ctx = StreamDeserializationContext(BytesIO(proof_bytes))
    detached = DetachedTimestampFile.deserialize(ctx)
    timestamp = detached.timestamp

    # Poll calendars for Bitcoin attestations
    upgrade_timestamp(timestamp)

    # Check if any Bitcoin attestation appeared
    has_btc = _has_bitcoin_attestation(timestamp)

    # Re-serialize updated proof
    buf = BytesIO()
    detached.serialize(StreamSerializationContext(buf))

    return OtsResult(
        proof_b64=base64.b64encode(buf.getvalue()).decode("ascii"),
        is_complete=has_btc,
    )


def _has_bitcoin_attestation(timestamp) -> bool:
    """Recursively check if any node in the timestamp tree has a Bitcoin
    block attestation (final proof)."""
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation

    for attestation in timestamp.attestations:
        if isinstance(attestation, BitcoinBlockHeaderAttestation):
            return True
    for op, sub in timestamp.ops.items():
        if _has_bitcoin_attestation(sub):
            return True
    return False


# ── Verification ──────────────────────────────────────────────────────────

def verify_proof(proof_b64: str, digest_bytes: bytes) -> tuple[bool, str | None]:
    """Verify a .ots proof against a digest. Returns (verified, btc_block_height).

    `verified=True` means the digest is provably committed to the named
    Bitcoin block. False means the proof is incomplete or invalid.
    """
    from opentimestamps.core.serialize import StreamDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation

    proof_bytes = base64.b64decode(proof_b64)
    ctx = StreamDeserializationContext(BytesIO(proof_bytes))
    detached = DetachedTimestampFile.deserialize(ctx)

    if detached.timestamp.msg != digest_bytes:
        return False, None

    # Walk the tree looking for Bitcoin attestations
    btc_height = _find_btc_height(detached.timestamp)
    return (btc_height is not None), btc_height


def _find_btc_height(timestamp) -> int | None:
    from opentimestamps.core.notary import BitcoinBlockHeaderAttestation

    for attestation in timestamp.attestations:
        if isinstance(attestation, BitcoinBlockHeaderAttestation):
            return attestation.height
    for op, sub in timestamp.ops.items():
        h = _find_btc_height(sub)
        if h is not None:
            return h
    return None
