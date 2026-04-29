"""Password reset workflow.

3 endpoints:
    POST /auth/request-password-reset  → email an existing user a reset link
    POST /auth/verify-reset-token      → check if a token is still valid
    POST /auth/reset-password          → consume token + change password

Security:
- Request endpoint always returns 200 to avoid leaking account existence.
- Tokens are 32-byte URL-safe (~256 bits of entropy), single-use, 60 min TTL.
- All sibling tokens are invalidated on successful reset.
- Every event is captured in audit_logs.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from auth.db import get_db
from auth.password import WeakPasswordError, hash_password, validate_password_strength
from auth.rate_limit import rate_limit_api
from services.audit_log import log_audit
from services.mailer import get_mailer

log = logging.getLogger("aminra.password_reset")
router = APIRouter()


# ── Configuration ──────────────────────────────────────────────────────────

PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "60"))
PASSWORD_RESET_TOKEN_BYTES = 32  # 256-bit entropy


# ── Models ─────────────────────────────────────────────────────────────────


class RequestResetIn(BaseModel):
    email: EmailStr
    lang: str = "vi"


class VerifyTokenIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)


class ResetPasswordIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)
    new_password: str


GENERIC_OK = {"message": "Nếu email tồn tại, hướng dẫn đặt lại sẽ được gửi."}


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/request-password-reset")
async def request_password_reset(
    body: RequestResetIn,
    request: Request,
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Generate a single-use reset token + email the user.

    Returns the same 200 response whether or not the email exists, so an
    attacker can't probe the user database.
    """
    email = body.email.lower().strip()
    user = await db.fetchrow(
        "SELECT id, email, company_name FROM users WHERE LOWER(email) = $1",
        email,
    )

    if user is None:
        await log_audit(
            db,
            action="password_reset.request_unknown_email",
            entity_type="user",
            metadata={"email": email},
            request=request,
        )
        return GENERIC_OK

    token = secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)

    # Invalidate any existing un-used tokens for this user (defensive).
    await db.execute(
        "UPDATE password_reset_tokens SET used = true WHERE user_id = $1 AND used = false",
        user["id"],
    )
    await db.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)",
        user["id"],
        token,
        expires_at,
    )

    mailer = get_mailer()
    reset_url = f"{mailer.config.app_base_url.rstrip('/')}/reset-password?token={token}"
    sent = await mailer.send_template(
        to=user["email"],
        template="password_reset",
        context={
            "user_name": user["company_name"] or user["email"],
            "reset_url": reset_url,
            "ttl_minutes": PASSWORD_RESET_TTL_MINUTES,
        },
        lang=body.lang,
    )

    await log_audit(
        db,
        user={"sub": str(user["id"]), "email": user["email"]},
        action="password_reset.request" if sent else "password_reset.request_email_failed",
        entity_type="user",
        entity_id=str(user["id"]),
        metadata={"ttl_minutes": PASSWORD_RESET_TTL_MINUTES},
        request=request,
    )
    log.info("[password_reset] request user=%s sent=%s", user["id"], sent)
    return GENERIC_OK


@router.post("/verify-reset-token")
async def verify_reset_token(
    body: VerifyTokenIn,
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Pre-flight check from the UI before showing the new-password form."""
    row = await db.fetchrow(
        """
        SELECT t.id, t.expires_at, t.used, u.email
        FROM password_reset_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = $1
        """,
        body.token,
    )
    if row is None or row["used"] or row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token không hợp lệ hoặc đã hết hạn")
    return {"valid": True, "email": row["email"]}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordIn,
    request: Request,
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Consume a reset token and update the user's password."""
    try:
        validate_password_strength(body.new_password)
    except WeakPasswordError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    row = await db.fetchrow(
        """
        SELECT t.id AS token_id, t.user_id, t.expires_at, t.used,
               u.email, u.role, u.tenant_id
        FROM password_reset_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = $1
        """,
        body.token,
    )
    if row is None or row["used"] or row["expires_at"] < datetime.now(timezone.utc):
        await log_audit(
            db,
            action="password_reset.consume_invalid_token",
            entity_type="user",
            metadata={"reason": "missing_or_expired"},
            request=request,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token không hợp lệ hoặc đã hết hạn")

    new_hash = hash_password(body.new_password)
    await db.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2",
        new_hash,
        row["user_id"],
    )
    # Invalidate this token AND any siblings still active.
    await db.execute(
        "UPDATE password_reset_tokens SET used = true WHERE user_id = $1",
        row["user_id"],
    )

    await log_audit(
        db,
        user={
            "sub": str(row["user_id"]),
            "email": row["email"],
            "role": row["role"],
            "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
        },
        action="password_reset.success",
        entity_type="user",
        entity_id=str(row["user_id"]),
        request=request,
    )
    log.info("[password_reset] success user=%s", row["user_id"])
    return {"message": "Mật khẩu đã được đặt lại thành công"}
