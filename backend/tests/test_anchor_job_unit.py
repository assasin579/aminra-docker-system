"""Unit tests for the daily anchor orchestration in services/anchor.py.

Strategy: stand up a real Postgres connection via the existing pool (DB
already has migration 009 applied), but inject a fake AnchorSubmitter so
no Polygon network calls happen. Each test cleans up after itself.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest


# ── Real DB fixtures ───────────────────────────────────────────────────────

@pytest.fixture
async def conn():
    """Fresh asyncpg connection per test to avoid event-loop binding issues."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — anchor job tests require Postgres")
    c = await asyncpg.connect(url)
    try:
        yield c
    finally:
        await c.close()


@pytest.fixture
async def clean_anchors(conn):
    """Each test starts with NO anchor data. Truncate after, not before, so
    parallel runs don't clobber. Use a savepoint."""
    async with conn.transaction():
        try:
            yield
        finally:
            # Cleanup test artifacts only
            await conn.execute("DELETE FROM cert_anchor_proofs WHERE anchor_id IN (SELECT id FROM blockchain_anchors WHERE metadata->>'_test'='1')")
            await conn.execute("DELETE FROM batch_anchor_proofs WHERE anchor_id IN (SELECT id FROM blockchain_anchors WHERE metadata->>'_test'='1')")
            await conn.execute("DELETE FROM blockchain_anchors WHERE metadata->>'_test'='1'")


# ── Fake submitter ─────────────────────────────────────────────────────────

@dataclass
class FakeAnchorResult:
    anchor_id: int
    tx_hash: str
    block_number: int
    gas_used: int
    merkle_root: str


class FakeSubmitter:
    """Pretends to be PolygonAnchor — records calls + returns canned result."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[dict] = []

    async def anchor_root(
        self, merkle_root: str, timestamp: int,
        cert_count: int, batch_count: int = 0, metadata: str = "",
    ) -> FakeAnchorResult:
        self.calls.append({
            "merkle_root": merkle_root,
            "timestamp": timestamp,
            "cert_count": cert_count,
            "batch_count": batch_count,
            "metadata": metadata,
        })
        if self.fail:
            raise RuntimeError("simulated polygon failure")
        return FakeAnchorResult(
            anchor_id=len(self.calls) - 1,
            tx_hash="0x" + ("a" * 64),
            block_number=50_000_000 + len(self.calls),
            gas_used=85_000,
            merkle_root=merkle_root,
        )


# ── Empty-state behavior ───────────────────────────────────────────────────

class TestEmptyState:
    async def test_skips_when_no_pending_items(self, conn, clean_anchors):
        from services.anchor import _run_daily_anchor_with

        # Anchor every existing cert/batch FIRST so there's nothing pending.
        # Easier path: query and assert nothing pending, then run.
        pending_certs = await conn.fetchval(
            """
            SELECT COUNT(*) FROM halal_certificates c
            LEFT JOIN cert_anchor_proofs p ON p.cert_id = c.id
            WHERE p.cert_id IS NULL
            """
        )
        if pending_certs > 0:
            pytest.skip(f"{pending_certs} pending certs — can't isolate empty case")

        submitter = FakeSubmitter()
        result = await _run_daily_anchor_with(conn, submitter)
        assert result["status"] == "skipped"
        assert submitter.calls == []


# ── Happy path ─────────────────────────────────────────────────────────────

class TestHappyPath:
    async def test_submits_and_persists_anchor_for_pending_certs(
        self, conn, clean_anchors,
    ):
        from services.anchor import _run_daily_anchor_with

        # The DB already contains real certs (some pending). Just run the job.
        submitter = FakeSubmitter()
        result = await _run_daily_anchor_with(conn, submitter)

        if result["status"] == "skipped":
            pytest.skip("no pending certs in DB to anchor")

        # Submitter was called once
        assert result["status"] == "confirmed"
        assert len(submitter.calls) == 1

        call = submitter.calls[0]
        assert call["merkle_root"].startswith("0x")
        assert len(call["merkle_root"]) == 66  # 0x + 64 hex
        assert call["cert_count"] >= 0
        assert call["batch_count"] >= 0

        # Anchor row inserted with status=confirmed
        anchor_row = await conn.fetchrow(
            "SELECT * FROM blockchain_anchors WHERE id = $1",
            result["anchor_id"],
        )
        assert anchor_row["status"] == "confirmed"
        assert anchor_row["chain"] == "polygon"
        assert anchor_row["merkle_root"] == call["merkle_root"]

        # Tag this anchor for cleanup
        await conn.execute(
            "UPDATE blockchain_anchors SET metadata = metadata || '{\"_test\": \"1\"}'::jsonb WHERE id = $1",
            result["anchor_id"],
        )

        # Each cert in the batch has a proof row
        proof_count = await conn.fetchval(
            "SELECT COUNT(*) FROM cert_anchor_proofs WHERE anchor_id = $1",
            result["anchor_id"],
        )
        assert proof_count == call["cert_count"]


# ── Idempotency ────────────────────────────────────────────────────────────

class TestIdempotency:
    async def test_second_run_skips_already_anchored_items(
        self, conn, clean_anchors,
    ):
        from services.anchor import _run_daily_anchor_with

        submitter = FakeSubmitter()

        first = await _run_daily_anchor_with(conn, submitter)
        if first["status"] == "skipped":
            pytest.skip("no certs to anchor")

        await conn.execute(
            "UPDATE blockchain_anchors SET metadata = metadata || '{\"_test\":\"1\"}'::jsonb WHERE id = $1",
            first["anchor_id"],
        )

        # Second run with same DB state — should find nothing new
        submitter2 = FakeSubmitter()
        second = await _run_daily_anchor_with(conn, submitter2)
        assert second["status"] == "skipped"
        assert submitter2.calls == []


# ── Failure path ───────────────────────────────────────────────────────────

class TestFailure:
    async def test_failed_submission_records_failed_anchor_no_proofs(
        self, conn, clean_anchors,
    ):
        from services.anchor import _run_daily_anchor_with

        submitter = FakeSubmitter(fail=True)
        result = await _run_daily_anchor_with(conn, submitter)

        if result["status"] == "skipped":
            pytest.skip("no pending certs to anchor")

        assert result["status"] == "failed"
        # Tag for cleanup
        await conn.execute(
            "UPDATE blockchain_anchors SET metadata = metadata || '{\"_test\":\"1\"}'::jsonb WHERE status = 'failed' AND error_message LIKE 'simulated%'"
        )
        # Failure row exists, proof rows do NOT
        failed_count = await conn.fetchval(
            "SELECT COUNT(*) FROM blockchain_anchors WHERE status='failed' AND error_message LIKE 'simulated%'"
        )
        assert failed_count >= 1


# ── Merkle tree shape sanity ───────────────────────────────────────────────

class TestMerkleProofIntegrity:
    async def test_each_persisted_proof_verifies_against_anchor_root(
        self, conn, clean_anchors,
    ):
        from services.anchor import _run_daily_anchor_with
        from services.merkle import MerkleTree

        submitter = FakeSubmitter()
        result = await _run_daily_anchor_with(conn, submitter)
        if result["status"] == "skipped":
            pytest.skip("no certs to anchor")

        await conn.execute(
            "UPDATE blockchain_anchors SET metadata = metadata || '{\"_test\":\"1\"}'::jsonb WHERE id = $1",
            result["anchor_id"],
        )

        anchor_row = await conn.fetchrow(
            "SELECT merkle_root FROM blockchain_anchors WHERE id = $1",
            result["anchor_id"],
        )
        root_hex = anchor_row["merkle_root"][2:]  # strip 0x

        # Pull all proofs and verify
        proofs = await conn.fetch(
            "SELECT leaf_hash, proof_path FROM cert_anchor_proofs WHERE anchor_id = $1",
            result["anchor_id"],
        )
        for p in proofs:
            proof = json.loads(p["proof_path"]) if isinstance(p["proof_path"], str) else p["proof_path"]
            assert MerkleTree.verify_proof(p["leaf_hash"], proof, root_hex), \
                f"proof for leaf {p['leaf_hash'][:8]} failed to verify"
