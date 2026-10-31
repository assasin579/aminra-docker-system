"""Merge attachment and audit-acceptance branches without rewriting applied history.

Existing installations with manually applied 052/053 objects must run the
verified reconciliation procedure before upgrading this merge revision.
"""
revision = "056_j1j2_lineage_merge"
down_revision = ("055_dossier_document_attachments", "053_audit_report_acceptance")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
