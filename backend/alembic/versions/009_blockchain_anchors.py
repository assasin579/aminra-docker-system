"""blockchain anchors — Merkle root anchoring on Polygon + Bitcoin

Three tables:
    blockchain_anchors    — one row per Merkle root submitted to a chain
    cert_anchor_proofs    — links cert to anchor + stores Merkle proof
    batch_anchor_proofs   — same for production batches

Revision ID: 009_blockchain_anchors
Revises: 008_user_deletion
Create Date: 2026-04-25
"""
from typing import Sequence, Union
from alembic import op

revision: str = "009_blockchain_anchors"
down_revision: Union[str, None] = "008_user_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS blockchain_anchors (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            chain           VARCHAR(20)  NOT NULL,
            merkle_root     VARCHAR(66)  NOT NULL,
            tx_hash         VARCHAR(128),
            block_number    BIGINT,
            cert_count      INTEGER NOT NULL DEFAULT 0,
            batch_count     INTEGER NOT NULL DEFAULT 0,
            submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            confirmed_at    TIMESTAMPTZ,
            status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
            error_message   TEXT,
            parent_anchor   UUID REFERENCES blockchain_anchors(id) ON DELETE SET NULL,
            metadata        JSONB DEFAULT '{}'::jsonb
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_anchor_chain_status ON blockchain_anchors(chain, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_anchor_submitted    ON blockchain_anchors(submitted_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_anchor_tx_hash      ON blockchain_anchors(tx_hash) WHERE tx_hash IS NOT NULL;")
    # status must be one of: pending|submitted|confirmed|failed
    op.execute("""
        ALTER TABLE blockchain_anchors
            ADD CONSTRAINT chk_anchor_status
            CHECK (status IN ('pending', 'submitted', 'confirmed', 'failed'));
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS cert_anchor_proofs (
            cert_id     UUID NOT NULL REFERENCES halal_certificates(id) ON DELETE CASCADE,
            anchor_id   UUID NOT NULL REFERENCES blockchain_anchors(id) ON DELETE CASCADE,
            leaf_hash   VARCHAR(66) NOT NULL,
            leaf_index  INTEGER     NOT NULL,
            proof_path  JSONB       NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (cert_id, anchor_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cert_proof_cert   ON cert_anchor_proofs(cert_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cert_proof_anchor ON cert_anchor_proofs(anchor_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS batch_anchor_proofs (
            batch_id    UUID NOT NULL REFERENCES production_batches(id) ON DELETE CASCADE,
            anchor_id   UUID NOT NULL REFERENCES blockchain_anchors(id) ON DELETE CASCADE,
            leaf_hash   VARCHAR(66) NOT NULL,
            leaf_index  INTEGER     NOT NULL,
            proof_path  JSONB       NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (batch_id, anchor_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_batch_proof_batch  ON batch_anchor_proofs(batch_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_batch_proof_anchor ON batch_anchor_proofs(anchor_id);")

    # Append-only at DB level — anchors are immutable evidence
    op.execute("REVOKE UPDATE, DELETE ON blockchain_anchors FROM PUBLIC;")
    op.execute("REVOKE UPDATE, DELETE ON cert_anchor_proofs FROM PUBLIC;")
    op.execute("REVOKE UPDATE, DELETE ON batch_anchor_proofs FROM PUBLIC;")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch_anchor_proofs;")
    op.execute("DROP TABLE IF EXISTS cert_anchor_proofs;")
    op.execute("DROP TABLE IF EXISTS blockchain_anchors;")
