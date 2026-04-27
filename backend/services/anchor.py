"""Daily anchor orchestration.

Glues together: DB query → hash certs/batches → Merkle tree → Polygon
submission → persist anchor record + Merkle proofs.

`run_daily_anchor()` is the entry point called by the ARQ cron job. It is
also testable in isolation via `_run_daily_anchor_with(...)`, which accepts
injected DB pool + anchor service for unit tests.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Protocol

import asyncpg

from services.audit_log import log_audit
from services.certificate_pdf import CertificateData, compute_cert_hash
from services.merkle import MerkleTree, sha256_hex

log = logging.getLogger("aminra.anchor")


# ── Anchor service Protocol — lets tests inject a fake ──────────────────────

class AnchorSubmitter(Protocol):
    async def anchor_root(
        self, merkle_root: str, timestamp: int,
        cert_count: int, batch_count: int = 0, metadata: str = "",
    ) -> "AnchorResult": ...


# ── Hash gathering ──────────────────────────────────────────────────────────

async def _pending_cert_leaves(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    """Return list of (cert_id, leaf_hash) for certs not yet anchored.

    Hash = SHA-256 of canonical cert fields, same as embedded in the PDF
    footer (compute_cert_hash). Recompute on the fly so we don't need to
    cache it in the table (hash is deterministic from cert fields).
    """
    rows = await conn.fetch(
        """
        SELECT c.id, c.cert_number, c.company_name, c.issue_date, c.expiry_date,
               c.notes, u.company_name AS provider_name
        FROM halal_certificates c
        LEFT JOIN users u ON u.id = c.issued_by
        LEFT JOIN cert_anchor_proofs p
               ON p.cert_id = c.id
        WHERE p.cert_id IS NULL
        ORDER BY c.created_at ASC
        """
    )
    leaves = []
    app_base = os.getenv("APP_BASE_URL", "http://localhost:3100").rstrip("/")
    for r in rows:
        data = CertificateData(
            cert_number=r["cert_number"],
            business_name=r["company_name"] or "",
            provider_name=r["provider_name"] or "",
            issue_date=r["issue_date"],
            expiry_date=r["expiry_date"],
            notes=r["notes"] or "",
            verify_url=f"{app_base}/verify/{r['cert_number']}",
        )
        leaf = compute_cert_hash(data)
        leaves.append((str(r["id"]), leaf))
    return leaves


async def _pending_batch_leaves(conn: asyncpg.Connection) -> list[tuple[str, str]]:
    """Return list of (batch_id, leaf_hash) for production batches not yet
    anchored. Uses the existing integrity_hash column populated when a batch
    is sealed (supply_chain/batch_router.py)."""
    rows = await conn.fetch(
        """
        SELECT b.id, b.integrity_hash
        FROM production_batches b
        LEFT JOIN batch_anchor_proofs p ON p.batch_id = b.id
        WHERE b.integrity_hash IS NOT NULL
          AND p.batch_id IS NULL
        ORDER BY b.created_at ASC
        """
    )
    return [(str(r["id"]), r["integrity_hash"]) for r in rows]


# ── Persistence ─────────────────────────────────────────────────────────────

async def _persist_anchor(
    conn: asyncpg.Connection,
    *,
    chain: str,
    merkle_root: str,
    tx_hash: str,
    block_number: int,
    cert_leaves: list[tuple[str, str]],
    batch_leaves: list[tuple[str, str]],
    tree: MerkleTree,
    metadata: dict,
) -> str:
    """Insert anchor + per-leaf proofs in a transaction. Returns anchor_id."""
    async with conn.transaction():
        anchor_row = await conn.fetchrow(
            """
            INSERT INTO blockchain_anchors
                (chain, merkle_root, tx_hash, block_number,
                 cert_count, batch_count,
                 status, confirmed_at, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, 'confirmed', NOW(), $7::jsonb)
            RETURNING id
            """,
            chain, merkle_root, tx_hash, block_number,
            len(cert_leaves), len(batch_leaves),
            json.dumps(metadata),
        )
        anchor_id = anchor_row["id"]

        # Build proof for every leaf — leaves[0..N-1] = certs, leaves[N..] = batches
        leaf_index_offset = 0
        for i, (cert_id, leaf_hash) in enumerate(cert_leaves):
            proof = tree.proof_for_index(i)
            await conn.execute(
                """
                INSERT INTO cert_anchor_proofs
                    (cert_id, anchor_id, leaf_hash, leaf_index, proof_path)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                cert_id, anchor_id, leaf_hash, i,
                json.dumps([s.to_dict() for s in proof]),
            )
        leaf_index_offset = len(cert_leaves)
        for j, (batch_id, leaf_hash) in enumerate(batch_leaves):
            idx = leaf_index_offset + j
            proof = tree.proof_for_index(idx)
            await conn.execute(
                """
                INSERT INTO batch_anchor_proofs
                    (batch_id, anchor_id, leaf_hash, leaf_index, proof_path)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                batch_id, anchor_id, leaf_hash, idx,
                json.dumps([s.to_dict() for s in proof]),
            )

    return str(anchor_id)


# ── Public entry points ────────────────────────────────────────────────────

async def run_daily_anchor() -> dict:
    """Production entry point — opens DB pool + Polygon service from env."""
    from auth.db import get_pool
    from services.anchor_polygon import PolygonAnchor, PolygonConfig

    pool = get_pool()
    submitter = PolygonAnchor(PolygonConfig.from_env())
    async with pool.acquire() as conn:
        return await _run_daily_anchor_with(conn, submitter, chain="polygon")


async def _run_daily_anchor_with(
    conn: asyncpg.Connection,
    submitter: AnchorSubmitter,
    *,
    chain: str = "polygon",
) -> dict:
    """Testable core. Caller injects the DB connection + anchor service."""
    cert_leaves = await _pending_cert_leaves(conn)
    batch_leaves = await _pending_batch_leaves(conn)

    if not cert_leaves and not batch_leaves:
        log.info("[anchor] no pending items; skipping")
        return {"status": "skipped", "reason": "no_pending_items"}

    all_leaves = [h for _, h in cert_leaves] + [h for _, h in batch_leaves]
    tree = MerkleTree(all_leaves)
    timestamp = int(datetime.now(timezone.utc).timestamp())

    metadata_json = {
        "anchor_run_at": datetime.now(timezone.utc).isoformat(),
        "cert_ids":  [cid for cid, _ in cert_leaves[:10]],   # first 10 for trace
        "batch_ids": [bid for bid, _ in batch_leaves[:10]],
    }

    log.info(
        "[anchor] submitting root=%s certs=%d batches=%d",
        tree.root[:16], len(cert_leaves), len(batch_leaves),
    )

    try:
        result = await submitter.anchor_root(
            merkle_root="0x" + tree.root,
            timestamp=timestamp,
            cert_count=len(cert_leaves),
            batch_count=len(batch_leaves),
            metadata=f"https://aminra.vn/anchors/{datetime.now(timezone.utc):%Y-%m-%d}",
        )
    except Exception as e:
        log.exception("[anchor] submission failed")
        # Record the failure for retry/observability
        await conn.execute(
            """
            INSERT INTO blockchain_anchors
                (chain, merkle_root, cert_count, batch_count, status, error_message)
            VALUES ($1, $2, $3, $4, 'failed', $5)
            """,
            chain, "0x" + tree.root,
            len(cert_leaves), len(batch_leaves),
            str(e),
        )
        return {"status": "failed", "error": str(e)}

    anchor_id = await _persist_anchor(
        conn,
        chain=chain,
        merkle_root="0x" + tree.root,
        tx_hash=result.tx_hash,
        block_number=result.block_number,
        cert_leaves=cert_leaves,
        batch_leaves=batch_leaves,
        tree=tree,
        metadata=metadata_json,
    )

    await log_audit(
        conn,
        action="anchor.submitted",
        entity_type="blockchain_anchor",
        entity_id=anchor_id,
        metadata={
            "chain": chain,
            "merkle_root": "0x" + tree.root,
            "tx_hash": result.tx_hash,
            "cert_count": len(cert_leaves),
            "batch_count": len(batch_leaves),
        },
    )

    log.info(
        "[anchor] confirmed anchor_id=%s tx=%s block=%s gas=%d",
        anchor_id, result.tx_hash, result.block_number, result.gas_used,
    )
    return {
        "status": "confirmed",
        "anchor_id": anchor_id,
        "merkle_root": "0x" + tree.root,
        "tx_hash": result.tx_hash,
        "block_number": result.block_number,
        "cert_count": len(cert_leaves),
        "batch_count": len(batch_leaves),
    }
