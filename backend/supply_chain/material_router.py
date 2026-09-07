"""Material CRUD — each material linked to a supplier."""

import logging
from uuid import UUID as _UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from auth.db import get_db
from auth.jwt_utils import get_current_user
from auth.permissions import check_permission_db
from .models import MaterialCreate, MaterialUpdate, MaterialOut
from .eligibility_service import assert_supplier_eligible

log = logging.getLogger("aminra.supply_chain.materials")
router = APIRouter()


def _validate_uuid(v: str) -> str:
    try:
        _UUID(v)
    except ValueError:
        raise HTTPException(400, "Invalid ID")
    return v


def _require_business(user: dict):
    if user.get("role") != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")
    return user.get("tenant_id")


@router.get("/materials")
async def list_materials(
    category: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    tenant_id = _require_business(user)
    cond = "WHERE m.tenant_id = $1"
    params: list = [tenant_id]
    idx = 2

    if category:
        cond += f" AND m.category = ${idx}"
        params.append(category)
        idx += 1
    if supplier_id:
        _validate_uuid(supplier_id)
        cond += f" AND m.supplier_id = ${idx}"
        params.append(supplier_id)
        idx += 1
    if search:
        cond += f" AND (m.name ILIKE ${idx} OR m.sku ILIKE ${idx})"
        params.append(f"%{search}%")
        idx += 1

    rows = await db.fetch(
        f"""
        SELECT m.*, s.name AS supplier_name
        FROM materials m
        LEFT JOIN suppliers s ON s.id = m.supplier_id
        {cond}
        ORDER BY m.created_at DESC
    """,
        *params,
    )

    return {
        "materials": [
            MaterialOut(
                id=str(r["id"]),
                name=r["name"],
                sku=r["sku"],
                category=r["category"],
                halal_risk=r["halal_risk"],
                description=r["description"],
                unit=r["unit"],
                supplier_id=str(r["supplier_id"]),
                supplier_name=r["supplier_name"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    }


@router.post("/materials")
async def create_material(req: MaterialCreate, user=Depends(get_current_user), db=Depends(get_db)):
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")
    _validate_uuid(req.supplier_id)

    # Verify supplier belongs to tenant
    s = await db.fetchrow("SELECT id FROM suppliers WHERE id=$1 AND tenant_id=$2", req.supplier_id, tenant_id)
    if not s:
        raise HTTPException(400, "Nhà cung cấp không tồn tại")
    await assert_supplier_eligible(db, tenant_id, req.supplier_id, req.category)

    row = await db.fetchrow(
        """
        INSERT INTO materials (tenant_id, supplier_id, name, sku, category, halal_risk, description, unit)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id
    """,
        tenant_id,
        req.supplier_id,
        req.name,
        req.sku,
        req.category,
        req.halal_risk or "unknown",
        req.description,
        req.unit,
    )

    log.info(f"[materials] Created {row['id']}")
    return {"id": str(row["id"]), "message": "Đã tạo nguyên liệu"}


@router.put("/materials/{mid}")
async def update_material(mid: str, req: MaterialUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(mid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_edit")

    updates, params, idx = [], [mid, tenant_id], 3
    current = await db.fetchrow(
        "SELECT supplier_id, category FROM materials WHERE id=$1 AND tenant_id=$2",
        mid,
        tenant_id,
    )
    if not current:
        raise HTTPException(404)
    next_supplier_id = str(current["supplier_id"])
    next_category = current["category"]
    supplier_changed = False
    category_changed = False
    for field in ["name", "supplier_id", "sku", "category", "halal_risk", "description", "unit"]:
        val = getattr(req, field, None)
        if val is not None:
            if field == "supplier_id":
                _validate_uuid(val)
                # Prevent cross-tenant FK swap: the supplier must belong to
                # this tenant, otherwise a malicious / mistaken update could
                # link a material to a competitor's supplier.
                owns = await db.fetchval(
                    "SELECT 1 FROM suppliers WHERE id=$1 AND tenant_id=$2",
                    val, tenant_id,
                )
                if not owns:
                    raise HTTPException(400, "Nhà cung cấp không tồn tại")
                next_supplier_id = val
                supplier_changed = True
            if field == "category":
                next_category = val
                category_changed = True
            updates.append(f"{field} = ${idx}")
            params.append(val)
            idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    if supplier_changed or category_changed:
        await assert_supplier_eligible(db, tenant_id, next_supplier_id, next_category)
    result = await db.execute(f"UPDATE materials SET {', '.join(updates)} WHERE id=$1 AND tenant_id=$2", *params)
    if result == "UPDATE 0":
        raise HTTPException(404)
    return {"message": "Đã cập nhật"}


@router.delete("/materials/{mid}")
async def delete_material(mid: str, user=Depends(get_current_user), db=Depends(get_db)):
    _validate_uuid(mid)
    tenant_id = _require_business(user)
    await check_permission_db(user, "can_delete")
    result = await db.execute("DELETE FROM materials WHERE id=$1 AND tenant_id=$2", mid, tenant_id)
    if result == "DELETE 0":
        raise HTTPException(404)
    return {"message": "Đã xoá"}
