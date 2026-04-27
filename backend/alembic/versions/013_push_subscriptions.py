"""web push subscriptions — store browser/device PushSubscription objects per user

Adds `push_subscriptions` keyed by `endpoint` (unique URL the browser provides).
A user may have multiple subscriptions (laptop + phone). Stale subscriptions are
removed when the push service returns 410 Gone on delivery.

Revision ID: 013_push_subscriptions
Revises: 012_submission_sla
Create Date: 2026-04-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "013_push_subscriptions"
down_revision: Union[str, None] = "012_submission_sla"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            endpoint     TEXT NOT NULL,
            p256dh       TEXT NOT NULL,
            auth         TEXT NOT NULL,
            user_agent   TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(endpoint)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions(user_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_push_subscriptions_user_id;")
    op.execute("DROP TABLE IF EXISTS push_subscriptions;")
