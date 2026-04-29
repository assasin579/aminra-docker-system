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
    try:
        _UUID(v)
    except ValueError:
        raise HTTPException(400, "Invalid ID")
    return v


# ── Helper: create notification (call from other routers) ────────────────────


async def notify(db, user_id: str, type: str, title: str, message: str = "", link: str = ""):
    """Create a notification for a user + best-effort web push delivery."""
    notification_id: str | None = None
    try:
        row = await db.fetchrow(
            "INSERT INTO notifications (user_id, type, title, message, link) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id,
            type,
            title,
            message,
            link,
        )
        notification_id = str(row["id"]) if row else None
    except Exception as e:
        log.warning(f"[notify] Failed to create notification: {e}")
        return

    try:
        from services.web_push import push_to_user

        await push_to_user(
            db,
            user_id,
            {
                "title": title,
                "message": message,
                "link": link,
                "tag": type,
                "notification_id": notification_id,
            },
        )
    except Exception as e:
        log.warning(f"[notify] web push delivery error (non-fatal): {e}")


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
        user["sub"],
        limit,
        offset,
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
            }
            for r in rows
        ],
        "total": total,
        "page": page,
    }


@router.get("/unread-count")
async def unread_count(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    count = await db.fetchval("SELECT COUNT(*) FROM notifications WHERE user_id=$1 AND read=false", user["sub"])
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
        notification_id,
        user["sub"],
    )
    return {"message": "OK"}


@router.put("/read-all")
async def mark_all_read(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await db.execute("UPDATE notifications SET read=true WHERE user_id=$1 AND read=false", user["sub"])
    return {"message": "OK"}


# ── Web Push subscriptions (PWA) ─────────────────────────────────────────────

import os as _os
from pydantic import BaseModel as _BaseModel


class PushSubscriptionRequest(_BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None


@router.get("/push-public-key")
async def get_vapid_public_key():
    return {"key": _os.getenv("VAPID_PUBLIC_KEY", "")}


@router.post("/push-subscriptions")
async def subscribe_push(
    req: PushSubscriptionRequest,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Register a PushSubscription for this device. Idempotent on `endpoint`.

    The browser may rotate the endpoint; treat each as a distinct subscription.
    """
    await db.execute(
        """INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent)
           VALUES ($1, $2, $3, $4, $5)
           ON CONFLICT (endpoint) DO UPDATE SET
               user_id=EXCLUDED.user_id,
               p256dh=EXCLUDED.p256dh,
               auth=EXCLUDED.auth,
               user_agent=EXCLUDED.user_agent,
               last_used_at=NOW()""",
        user["sub"],
        req.endpoint,
        req.p256dh,
        req.auth,
        req.user_agent,
    )
    return {"message": "subscribed"}


@router.delete("/push-subscriptions")
async def unsubscribe_push(
    endpoint: str = Query(..., min_length=10),
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    await db.execute(
        "DELETE FROM push_subscriptions WHERE endpoint=$1 AND user_id=$2",
        endpoint,
        user["sub"],
    )
    return {"message": "unsubscribed"}
