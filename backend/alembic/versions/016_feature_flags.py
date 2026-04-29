"""feature flag system — global registry + per-tenant overrides

Two-table design:
- feature_flags: global registry of all flags (name, default, rollout %)
- tenant_feature_overrides: per-tenant override (forces on/off regardless of default)

Resolution order at runtime:
  1. If override row exists for (tenant_id, name) → use override.enabled
  2. Else if rollout_percentage > 0 → deterministic hash(tenant_id + name) % 100 < rollout_percentage
  3. Else → default_enabled

Tier-1 flags seeded as disabled defaults so the modules ship dark and roll
out per-tenant via overrides:
  - ihc_meetings_v1
  - training_matrix_v1
  - document_versioning_v1
  - internal_audit_v1
  - hazard_analysis_v1
  - ccp_table_v1
  - recall_workflow_v1

Revision ID: 016_feature_flags
Revises: 015_drop_self_assessments
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016_feature_flags"
down_revision: Union[str, None] = "015_drop_self_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIER_1_FLAGS = (
    ("ihc_meetings_v1", "Internal Halal Committee meeting records (Tier-1 #22)"),
    ("training_matrix_v1", "Per-employee Halal training records (Tier-1 #23)"),
    ("document_versioning_v1", "Document approver/effective_date/retention (Tier-1 #24)"),
    ("internal_audit_v1", "Internal Halal audit module (Tier-1 #27, MS 1500 §5.10)"),
    ("hazard_analysis_v1", "Halal hazard analysis worksheet (Tier-1 #28)"),
    ("ccp_table_v1", "Halal Critical Control Points table (Tier-1 #29)"),
    ("recall_workflow_v1", "Complaint + recall workflow with mock-drill (Tier-1 #30)"),
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE feature_flags (
            name              VARCHAR(64) PRIMARY KEY,
            description       TEXT,
            default_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
            rollout_percentage INTEGER NOT NULL DEFAULT 0
                              CHECK (rollout_percentage BETWEEN 0 AND 100),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE TABLE tenant_feature_overrides (
            tenant_id        UUID NOT NULL,
            feature_name     VARCHAR(64) NOT NULL
                            REFERENCES feature_flags(name) ON DELETE CASCADE ON UPDATE CASCADE,
            enabled          BOOLEAN NOT NULL,
            override_reason  TEXT,
            created_by       UUID,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tenant_id, feature_name)
        );
    """)
    op.execute("""
        CREATE INDEX idx_tenant_feature_overrides_tenant
          ON tenant_feature_overrides(tenant_id);
    """)
    op.execute("""
        CREATE TRIGGER update_tenant_feature_overrides_updated_at BEFORE UPDATE ON tenant_feature_overrides
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # Seed Tier-1 flags (disabled defaults — modules ship dark)
    for name, description in TIER_1_FLAGS:
        op.execute(
            "INSERT INTO feature_flags (name, description, default_enabled, rollout_percentage) "
            f"VALUES ('{name}', '{description}', FALSE, 0);"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_feature_overrides CASCADE;")
    op.execute("DROP TABLE IF EXISTS feature_flags CASCADE;")
