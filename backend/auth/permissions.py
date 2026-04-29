"""Permission system — owner has all, members have view-only by default.

Tier-1 #24 (2026-04-29): adds `can_approve_documents` for the document
version-control state machine. IHC members (users.ihc_role IS NOT NULL)
auto-receive this permission per JAKIM MS 1500 §5.4 (Internal Halal
Committee oversight). Tenant owners always have it.
"""

import json
from fastapi import HTTPException

DEFAULT_PERMISSIONS = {
    "can_edit": False,
    "can_delete": False,
    "can_approve": False,
    "can_upload": False,
    "can_approve_documents": False,
}

ALL_PERMISSIONS = {
    "can_edit": True,
    "can_delete": True,
    "can_approve": True,
    "can_upload": True,
    "can_approve_documents": True,
}

PERMISSION_LABELS = {
    "can_edit": "Chỉnh sửa dữ liệu",
    "can_delete": "Xóa dữ liệu",
    "can_approve": "Xác nhận / Phê duyệt",
    "can_upload": "Upload tài liệu",
    "can_approve_documents": "Phê duyệt tài liệu Halal",
}


def _ihc_member(user_or_row: dict) -> bool:
    """IHC members (any user with non-empty ihc_role) auto-get
    can_approve_documents per JAKIM MS 1500 §5.4. Defensive against missing key."""
    return bool(user_or_row.get("ihc_role"))


def get_user_permissions(user: dict) -> dict:
    """Get effective permissions for a user.

    Resolution:
      1. owner → ALL_PERMISSIONS
      2. IHC member → DEFAULT_PERMISSIONS + {can_approve_documents: True} merged with explicit
      3. else → DEFAULT_PERMISSIONS merged with explicit overrides
    """
    if user.get("is_owner"):
        return ALL_PERMISSIONS
    perms = user.get("permissions") or DEFAULT_PERMISSIONS
    if isinstance(perms, str):
        perms = json.loads(perms)
    merged = {**DEFAULT_PERMISSIONS, **perms}
    if _ihc_member(user):
        merged["can_approve_documents"] = True
    return merged


def check_permission(user: dict, permission: str, db_permissions: dict = None):
    """Raise 403 if user doesn't have the required permission."""
    if user.get("is_owner"):
        return  # Owner always passes

    perms = db_permissions or get_user_permissions(user)
    if not perms.get(permission, False):
        label = PERMISSION_LABELS.get(permission, permission)
        raise HTTPException(403, f"Bạn không có quyền: {label}. Liên hệ chủ tài khoản để được cấp quyền.")


async def check_permission_db(user: dict, permission: str):
    """Fetch permissions from DB and check. Use this in endpoints.

    Reads `permissions` JSONB AND `ihc_role` so IHC members get
    can_approve_documents even without explicit override.
    """
    if user.get("is_owner"):
        return

    from auth.db import get_pool

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT permissions, ihc_role FROM users WHERE id = $1", user.get("sub"))

    perms = DEFAULT_PERMISSIONS.copy()
    if row and row["permissions"]:
        db_perms = row["permissions"]
        if isinstance(db_perms, str):
            db_perms = json.loads(db_perms)
        perms.update(db_perms)

    # IHC auto-grant (post-explicit so explicit override can't take it away —
    # rationale: IHC role is mandatory for halal cert; revoke ihc_role first
    # if you need to revoke document approval rights)
    if row and row.get("ihc_role"):
        perms["can_approve_documents"] = True

    if not perms.get(permission, False):
        label = PERMISSION_LABELS.get(permission, permission)
        raise HTTPException(403, f"Bạn không có quyền: {label}. Liên hệ chủ tài khoản để được cấp quyền.")
