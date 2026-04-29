"""GDPR Article 17 / VN Nghị định 13 — Right to be forgotten.

Two-step flow:
  1. request_deletion()  — caller requests deletion; we create a token and
     email a confirmation link. The account is NOT deleted yet.
  2. confirm_deletion()  — user clicks the link; we anonymize their PII and
     mark deleted_at. Login is blocked from this point on.

Anonymization strategy:
  - users.email           → "deleted-{short_id}@aminra.deleted" (preserves UNIQUE)
  - users.password_hash   → unrecoverable random string
  - users.company_name    → "[deleted]"
  - users.address/phone/representative_name → NULL
  - users.deleted_at      → NOW()
  - audit_logs.user_email → "[deleted]" (forensic action history kept)

Records intentionally NOT deleted:
  - halal_certificates: legal artifacts; public verify must continue. Privacy
    policy makes this clear.
  - audit_logs entries: minimum 5-year retention by compliance.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

log = logging.getLogger("aminra.data_deletion")

DELETION_TTL_MINUTES = 60
DELETION_TOKEN_BYTES = 32


# ── Step 1: request ────────────────────────────────────────────────────────


async def create_deletion_token(db, user_id: str) -> tuple[str, datetime]:
    """Generate + persist a single-use deletion confirmation token.

    Invalidates any prior unused tokens for this user (only the latest one
    is valid).
    """
    token = secrets.token_urlsafe(DELETION_TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=DELETION_TTL_MINUTES)

    # Mark prior tokens as confirmed (i.e. consumed/dead) so they can't replay.
    await db.execute(
        "UPDATE deletion_tokens SET confirmed_at = NOW() WHERE user_id = $1 AND confirmed_at IS NULL",
        user_id,
    )
    await db.execute(
        "INSERT INTO deletion_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)",
        user_id,
        token,
        expires_at,
    )
    return token, expires_at


# ── Step 2: confirm + anonymize ────────────────────────────────────────────


class TokenInvalid(Exception):
    """Raised when the deletion token is missing, used, or expired."""


async def confirm_and_anonymize(db, token: str) -> dict:
    """Validate the token, anonymize PII, mark deleted. Returns audit metadata."""
    row = await db.fetchrow(
        """
        SELECT t.id AS token_id, t.user_id, t.expires_at, t.confirmed_at,
               u.email, u.role, u.tenant_id, u.deleted_at
        FROM deletion_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = $1
        """,
        token,
    )
    if row is None:
        raise TokenInvalid("Token không tồn tại")
    if row["confirmed_at"] is not None:
        raise TokenInvalid("Token đã được sử dụng")
    if row["expires_at"] < datetime.now(timezone.utc):
        raise TokenInvalid("Token đã hết hạn")
    if row["deleted_at"] is not None:
        raise TokenInvalid("Tài khoản đã bị xoá trước đó")

    user_id = row["user_id"]
    original_email = row["email"]
    short = uuid.UUID(str(user_id)).hex[:12]
    anonymized_email = f"deleted-{short}@aminra.deleted"
    fake_hash = "$2b$12$" + secrets.token_urlsafe(53)[:53]

    await db.execute(
        """
        UPDATE users
           SET email               = $1,
               password_hash       = $2,
               company_name        = '[deleted]',
               company_code        = NULL,
               address             = NULL,
               phone               = NULL,
               representative_name = NULL,
               status              = 'suspended',
               deleted_at          = NOW(),
               updated_at          = NOW()
         WHERE id = $3
        """,
        anonymized_email,
        fake_hash,
        user_id,
    )

    # Mark the token consumed.
    await db.execute(
        "UPDATE deletion_tokens SET confirmed_at = NOW() WHERE id = $1",
        row["token_id"],
    )

    # Anonymize the user's email in audit_logs (action/timestamps preserved
    # for forensic chain — only the readable PII goes).
    await db.execute(
        "UPDATE audit_logs SET user_email = '[deleted]' WHERE user_id = $1",
        user_id,
    )

    log.info("[deletion] account anonymized user_id=%s", user_id)

    return {
        "user_id": str(user_id),
        "anonymized_email": anonymized_email,
        "original_email_hash": _short_hash(original_email),
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }


def _short_hash(value: str) -> str:
    """Tiny hex digest for audit metadata — proves *something* was anonymized
    without storing the original PII."""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
