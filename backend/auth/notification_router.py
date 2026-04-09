"""In-app notification system."""

import logging
from uuid import UUID as _UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from asyncpg import Connection

from auth.db import get_db
from auth.jwt_utils import get_current_user

log = logging.getLogger("aminra.notifications")
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try: _UUID(v)
    except ValueError: raise HTTPException(400, "Invalid ID")
    return v


# ── Helper: create notification (call from other routers) ────────────────────

async def notify(db, user_id: str, type: str, title: str, message: str = "", link: str = ""):
    """Create a notification for a user. Call this from other endpoints."""
    try:
        await db.execute(
            "INSERT INTO notifications (user_id, type, title, message, link) VALUES ($1, $2, $3, $4, $5)",
            user_id, type, title, message, link,
        )
    except Exception as e:
        log.warning(f"[notify] Failed to create notification: {e}")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    offset = (page - 1) * limit
    rows = await db.fetch(
        "SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        user["sub"], limit, offset,
    )
    total = await db.fetchval("SELECT COUNT(*) FROM notifications WHERE user_id=$1", user["sub"])
    return {
        "notifications": [
            {
                "id": str(r["id"]),
                "type": r["type"],
                "title": r["title"],
                "message": r["message"],
                "read": r["read"],
                "link": r["link"],
                "created_at": r["created_at"].isoformat(),
            } for r in rows
        ],
        "total": total,
        "page": page,
    }


@router.get("/unread-count")
async def unread_count(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    count = await db.fetchval(
        "SELECT COUNT(*) FROM notifications WHERE user_id=$1 AND read=false", user["sub"])
    return {"count": count}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    _validate_uuid(notification_id)
    await db.execute(
        "UPDATE notifications SET read=true WHERE id=$1 AND user_id=$2",
        notification_id, user["sub"],
    )
    return {"message": "OK"}


@router.put("/read-all")
async def mark_all_read(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await db.execute("UPDATE notifications SET read=true WHERE user_id=$1 AND read=false", user["sub"])
    return {"message": "OK"}
