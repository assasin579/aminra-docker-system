"""Web Push (VAPID) delivery service.

Used by `notify()` to send push notifications to all subscribed devices of a
user. VAPID keys are loaded from env (VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY).
Subscriptions returning HTTP 410 Gone are auto-removed from the DB.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("aminra.web_push")

VAPID_PUBLIC_KEY  = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CONTACT     = os.getenv("VAPID_CONTACT_EMAIL", "mailto:support@aminra.vn")


def is_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


async def push_to_user(db, user_id: str, payload: dict[str, Any]) -> int:
    """Deliver `payload` as a web push to every subscription of `user_id`.

    Returns count of successful deliveries. Stale (410 Gone) subscriptions are
    silently removed. Failures are logged but never raise — push is best-effort.
    """
    if not is_configured():
        return 0
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        log.warning("pywebpush not installed — skipping web push delivery")
        return 0

    rows = await db.fetch(
        "SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id=$1",
        user_id,
    )
    delivered = 0
    stale_ids: list[str] = []
    body = json.dumps(payload)

    for r in rows:
        sub = {
            "endpoint": r["endpoint"],
            "keys": {"p256dh": r["p256dh"], "auth": r["auth"]},
        }
        try:
            webpush(
                subscription_info=sub,
                data=body,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CONTACT},
            )
            delivered += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                stale_ids.append(str(r["id"]))
            else:
                log.warning(f"[web_push] delivery failed status={status} err={e}")
        except Exception as e:
            log.warning(f"[web_push] unexpected delivery error: {e}")

    if stale_ids:
        await db.execute(
            "DELETE FROM push_subscriptions WHERE id = ANY($1::uuid[])",
            stale_ids,
        )
        log.info(f"[web_push] pruned {len(stale_ids)} stale subscriptions for user {user_id}")

    if delivered:
        await db.execute(
            "UPDATE push_subscriptions SET last_used_at=NOW() WHERE user_id=$1",
            user_id,
        )

    return delivered
