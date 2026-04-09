"""Permission system — owner has all, members have view-only by default."""

import json
from fastapi import HTTPException

DEFAULT_PERMISSIONS = {
    "can_edit": False,
    "can_delete": False,
    "can_approve": False,
    "can_upload": False,
}

ALL_PERMISSIONS = {
    "can_edit": True,
    "can_delete": True,
    "can_approve": True,
    "can_upload": True,
}

PERMISSION_LABELS = {
    "can_edit": "Chỉnh sửa dữ liệu",
    "can_delete": "Xóa dữ liệu",
    "can_approve": "Xác nhận / Phê duyệt",
    "can_upload": "Upload tài liệu",
}


def get_user_permissions(user: dict) -> dict:
    """Get effective permissions for a user. Owner always has all."""
    if user.get("is_owner"):
        return ALL_PERMISSIONS
    perms = user.get("permissions") or DEFAULT_PERMISSIONS
    if isinstance(perms, str):
        perms = json.loads(perms)
    return {**DEFAULT_PERMISSIONS, **perms}


def check_permission(user: dict, permission: str, db_permissions: dict = None):
    """Raise 403 if user doesn't have the required permission."""
    if user.get("is_owner"):
        return  # Owner always passes

    perms = db_permissions or get_user_permissions(user)
    if not perms.get(permission, False):
        label = PERMISSION_LABELS.get(permission, permission)
        raise HTTPException(403, f"Bạn không có quyền: {label}. Liên hệ chủ tài khoản để được cấp quyền.")


async def check_permission_db(user: dict, permission: str):
    """Fetch permissions from DB and check. Use this in endpoints."""
    if user.get("is_owner"):
        return

    from auth.db import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT permissions FROM users WHERE id = $1", user.get("sub"))

    perms = DEFAULT_PERMISSIONS.copy()
    if row and row["permissions"]:
        db_perms = row["permissions"]
        if isinstance(db_perms, str):
            db_perms = json.loads(db_perms)
        perms.update(db_perms)

    if not perms.get(permission, False):
        label = PERMISSION_LABELS.get(permission, permission)
        raise HTTPException(403, f"Bạn không có quyền: {label}. Liên hệ chủ tài khoản để được cấp quyền.")
