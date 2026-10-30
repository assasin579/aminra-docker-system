"""User data rights endpoints (Vietnam Nghị định 13 + EU GDPR).

- GET  /me/export-data     — right to access + portability (Article 20)
- POST /me/request-deletion — right to be forgotten step 1 (Article 17)
- POST /me/confirm-deletion — right to be forgotten step 2 (token confirm)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.identity import resolve_canonical_user_id
from auth.jwt_utils import get_current_user
from auth.rate_limit import rate_limit_api, rate_limit_data_export
from services.audit_log import log_audit
from services.data_deletion import (
    DELETION_TTL_MINUTES,
    TokenInvalid,
    confirm_and_anonymize,
    create_deletion_token,
)
from services.data_export import export_user_data
from services.mailer import get_mailer

log = logging.getLogger("aminra.gdpr")
router = APIRouter()


@router.get("/me/export-data")
async def export_my_data(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_data_export),
):
    """Return a complete JSON dump of the calling user's personal data.

    Compliance:
    - Vietnam Nghị định 13/2023/NĐ-CP — Quyền tiếp cận dữ liệu cá nhân
    - EU GDPR Article 20 — Right to data portability

    The response is served as a downloadable JSON file with a timestamped
    filename so users can archive multiple exports.
    """
    bundle = await export_user_data(db, user)

    actor_id = await resolve_canonical_user_id(user, db)
    await log_audit(
        db,
        user=user,
        action="data.export.requested",
        entity_type="user",
        entity_id=str(actor_id) if actor_id else user.get("email", ""),
        metadata={
            "byte_size": len(json.dumps(bundle)),
            "section_counts": {
                "notifications": len(bundle["data_subject"]["notifications"]),
                "audit_logs": len(bundle["data_subject"]["audit_logs"]),
                "documents": len(bundle.get("tenant_data", {}).get("documents", [])),
                "submissions": len(bundle.get("tenant_data", {}).get("submissions", [])),
                "certificates": len(bundle.get("tenant_data", {}).get("certificates", [])),
            },
        },
        request=request,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"aminra-export-{user['sub'][:8]}-{timestamp}.json"

    return Response(
        content=json.dumps(bundle, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Format-Version": bundle["export_format_version"],
        },
    )


# ── Right to be forgotten (Article 17) ─────────────────────────────────────


class RequestDeletionIn(BaseModel):
    lang: str = "vi"


class ConfirmDeletionIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=255)


@router.post("/me/request-deletion")
async def request_deletion(
    body: RequestDeletionIn,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Step 1 of GDPR Article 17 / Nghị định 13 right to erasure.

    Generates a single-use confirmation token and emails it. The account is
    NOT deleted yet — execution requires a separate POST /me/confirm-deletion.
    """
    user_id = await resolve_canonical_user_id(user, db)
    if not user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User row not found in AMINRA DB")
    email = user["email"]
    company = (await db.fetchval("SELECT company_name FROM users WHERE id = $1", user_id)) or ""

    token, _expires = await create_deletion_token(db, user_id)

    mailer = get_mailer()
    confirm_url = f"{mailer.config.app_base_url.rstrip('/')}/account/confirm-deletion?token={token}"
    sent = await mailer.send_template(
        to=email,
        template="account_deletion",
        context={
            "user_name": company or email,
            "user_email": email,
            "confirm_url": confirm_url,
            "ttl_minutes": DELETION_TTL_MINUTES,
        },
        lang=body.lang,
    )

    await log_audit(
        db,
        user=user,
        action="data.delete.requested" if sent else "data.delete.request_email_failed",
        entity_type="user",
        entity_id=user_id,
        metadata={"ttl_minutes": DELETION_TTL_MINUTES, "email_sent": sent},
        request=request,
    )
    return {"message": "Đã gửi email xác nhận. Vui lòng kiểm tra hộp thư."}


@router.post("/me/confirm-deletion")
async def confirm_deletion(
    body: ConfirmDeletionIn,
    request: Request,
    db: Connection = Depends(get_db),
    _: None = Depends(rate_limit_api),
):
    """Step 2: consume the token + anonymize PII + soft-delete account.

    No JWT required — the confirmation token IS the authorization. (Same
    pattern as password reset; rate-limited to prevent token guessing.)
    """
    try:
        result = await confirm_and_anonymize(db, body.token)
    except TokenInvalid as e:
        await log_audit(
            db,
            action="data.delete.confirm_invalid_token",
            entity_type="user",
            metadata={"reason": str(e)},
            request=request,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    await log_audit(
        db,
        action="data.delete.confirmed",
        entity_type="user",
        entity_id=result["user_id"],
        metadata={
            "anonymized_email": result["anonymized_email"],
            "original_email_hash": result["original_email_hash"],
        },
        request=request,
    )
    return {"message": "Tài khoản đã bị xoá. Bạn sẽ không thể đăng nhập với tài khoản này nữa."}
