"""Standard types (tiêu chuẩn áp dụng) — admin CRUD + business list.

Tiêu chuẩn = JAKIM/MUI/BPJPH/TCVN scheme version (MS 1500:2019, MS 1480,
MPPHM, MS 2424:2019, MS 2200-2:2013). Mỗi tiêu chuẩn quy định danh sách
doc_types + số lượng required.

Industry schema (ngành nghề) M:N standard_types — 1 ngành có thể áp dụng
nhiều tiêu chuẩn. Khi tạo hồ sơ, user chọn 1 standard từ list available
cho industry của họ.

Endpoints:
  GET  /standard-types                       — list enabled (any auth)
  GET  /standard-types/{code_or_id}          — detail with doc_types
  GET  /standard-types/by-industry/{code}    — filter by industry's available
  GET  /admin/standard-types                 — list incl. disabled (admin)
  POST /admin/standard-types                 — create
  PATCH /admin/standard-types/{id}           — update
  DELETE /admin/standard-types/{id}          — soft delete
  PUT  /admin/standard-types/{id}/doc-types  — bulk replace doc_types
  PUT  /admin/industry-schemas/{id}/standards — bulk replace industry↔std mapping
"""

from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.db import get_db
from auth.identity import resolve_canonical_user_id
from auth.jwt_utils import get_current_user, require_admin

log = logging.getLogger("aminra.standard_type")

router = APIRouter()
admin_router = APIRouter()


# ── Pydantic schemas ────────────────────────────────────────────────────────


class DocTypeAssoc(BaseModel):
    doc_type: str
    required: bool = True
    display_order: int = 0


class StandardTypePublic(BaseModel):
    id: str
    code: str
    name_vi: str
    name_en: Optional[str] = None
    organization: Optional[str] = None
    scheme_version: Optional[str] = None
    description: Optional[str] = None
    full_text_url: Optional[str] = None
    enabled: bool
    display_order: int
    doc_types: List[DocTypeAssoc] = []
    is_default: Optional[bool] = None  # populated when fetching by-industry


class StandardTypeCreate(BaseModel):
    code: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,49}$")
    name_vi: str = Field(..., min_length=1, max_length=255)
    name_en: Optional[str] = None
    organization: Optional[str] = None
    scheme_version: Optional[str] = None
    description: Optional[str] = None
    full_text_url: Optional[str] = None
    enabled: bool = True
    display_order: int = 0


class StandardTypeUpdate(BaseModel):
    name_vi: Optional[str] = None
    name_en: Optional[str] = None
    organization: Optional[str] = None
    scheme_version: Optional[str] = None
    description: Optional[str] = None
    full_text_url: Optional[str] = None
    enabled: Optional[bool] = None
    display_order: Optional[int] = None


class DocTypesBulkReplace(BaseModel):
    doc_types: List[DocTypeAssoc]


class IndustryStandardAssoc(BaseModel):
    standard_type_id: UUID
    is_default: bool = False
    display_order: int = 0


class IndustryStandardsBulkReplace(BaseModel):
    standards: List[IndustryStandardAssoc]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _require_admin(user: dict) -> None:
    role = user.get("role")
    if role not in ("admin", "platform_admin", "provider"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    if role == "provider" and user.get("email") != "admin@aminra.com":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")


async def _fetch_doc_types(db, standard_type_id: UUID) -> List[DocTypeAssoc]:
    rows = await db.fetch(
        "SELECT doc_type, required, display_order FROM standard_doc_types "
        "WHERE standard_type_id = $1 ORDER BY display_order, doc_type",
        standard_type_id,
    )
    return [DocTypeAssoc(**dict(r)) for r in rows]


async def _row_to_public(db, row, is_default: Optional[bool] = None) -> StandardTypePublic:
    doc_types = await _fetch_doc_types(db, row["id"])
    return StandardTypePublic(
        id=str(row["id"]),
        code=row["code"],
        name_vi=row["name_vi"],
        name_en=row.get("name_en"),
        organization=row.get("organization"),
        scheme_version=row.get("scheme_version"),
        description=row.get("description"),
        full_text_url=row.get("full_text_url"),
        enabled=row["enabled"],
        display_order=row["display_order"],
        doc_types=doc_types,
        is_default=is_default,
    )


# ── Public endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=List[StandardTypePublic])
async def list_standards(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    rows = await db.fetch(
        "SELECT * FROM standard_types WHERE enabled = true "
        "ORDER BY display_order, name_vi"
    )
    return [await _row_to_public(db, r) for r in rows]


@router.get("/by-industry/{industry_code_or_id}", response_model=List[StandardTypePublic])
async def list_by_industry(
    industry_code_or_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Standards available for given industry (M:N via industry_standards).

    Returned in display_order of the mapping; each item includes `is_default`
    flag so FE can pre-select.
    """
    # Resolve industry by code or UUID
    try:
        ind_id = UUID(industry_code_or_id)
        industry_row = await db.fetchrow(
            "SELECT id FROM industry_schemas WHERE id = $1", ind_id,
        )
    except ValueError:
        industry_row = await db.fetchrow(
            "SELECT id FROM industry_schemas WHERE code = $1", industry_code_or_id,
        )
    if not industry_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Industry not found")

    rows = await db.fetch(
        """SELECT st.*, ins.is_default
           FROM industry_standards ins
           JOIN standard_types st ON st.id = ins.standard_type_id
           WHERE ins.industry_schema_id = $1 AND st.enabled = true
           ORDER BY ins.display_order, st.display_order""",
        industry_row["id"],
    )
    return [await _row_to_public(db, r, is_default=r["is_default"]) for r in rows]


@router.get("/{code_or_id}", response_model=StandardTypePublic)
async def get_standard(
    code_or_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        sid = UUID(code_or_id)
        row = await db.fetchrow("SELECT * FROM standard_types WHERE id = $1", sid)
    except ValueError:
        row = await db.fetchrow("SELECT * FROM standard_types WHERE code = $1", code_or_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found")
    return await _row_to_public(db, row)


# ── Admin endpoints ─────────────────────────────────────────────────────────


@admin_router.get("", response_model=List[StandardTypePublic])
async def admin_list_all(
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    rows = await db.fetch("SELECT * FROM standard_types ORDER BY display_order, name_vi")
    return [await _row_to_public(db, r) for r in rows]


@admin_router.post("", response_model=StandardTypePublic, status_code=201)
async def admin_create(
    req: StandardTypeCreate,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    existing = await db.fetchval(
        "SELECT 1 FROM standard_types WHERE code = $1", req.code,
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Code '{req.code}' already exists")
    row = await db.fetchrow(
        """INSERT INTO standard_types
           (code, name_vi, name_en, organization, scheme_version, description,
            full_text_url, enabled, display_order, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
           RETURNING *""",
        req.code, req.name_vi, req.name_en, req.organization, req.scheme_version,
        req.description, req.full_text_url, req.enabled, req.display_order,
        await resolve_canonical_user_id(user, db),
    )
    log.info("[standard] admin %s created %s", user["email"], req.code)
    actor_id = await resolve_canonical_user_id(user, db)
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, 'standard_type_created', 'standard_type', $2, $3::jsonb)",
        actor_id, row["id"], f'{{"code":"{req.code}"}}',
    )
    return await _row_to_public(db, row)


@admin_router.patch("/{standard_id}", response_model=StandardTypePublic)
async def admin_update(
    standard_id: UUID,
    req: StandardTypeUpdate,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    sets, params, idx = [], [], 1
    for field, val in req.model_dump(exclude_unset=True).items():
        sets.append(f"{field} = ${idx}")
        params.append(val)
        idx += 1
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    sets.append(f"updated_at = NOW()")
    params.append(standard_id)
    row = await db.fetchrow(
        f"UPDATE standard_types SET {', '.join(sets)} WHERE id = ${idx} RETURNING *",
        *params,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found")
    return await _row_to_public(db, row)


@admin_router.delete("/{standard_id}", status_code=204)
async def admin_disable(
    standard_id: UUID,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    result = await db.execute(
        "UPDATE standard_types SET enabled = false, updated_at = NOW() WHERE id = $1",
        standard_id,
    )
    if result.endswith("0"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found")


@admin_router.put("/{standard_id}/doc-types")
async def admin_replace_doc_types(
    standard_id: UUID,
    req: DocTypesBulkReplace,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    exists = await db.fetchval("SELECT 1 FROM standard_types WHERE id = $1", standard_id)
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Standard not found")
    async with db.transaction():
        await db.execute(
            "DELETE FROM standard_doc_types WHERE standard_type_id = $1", standard_id,
        )
        for dt in req.doc_types:
            await db.execute(
                "INSERT INTO standard_doc_types (standard_type_id, doc_type, required, display_order) "
                "VALUES ($1, $2, $3, $4)",
                standard_id, dt.doc_type, dt.required, dt.display_order,
            )
    return {"ok": True, "count": len(req.doc_types)}


# ── Industry ↔ Standard mapping (admin) ─────────────────────────────────────


@admin_router.put("/industries/{industry_id}/standards")
async def admin_replace_industry_standards(
    industry_id: UUID,
    req: IndustryStandardsBulkReplace,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """Replace the M:N mapping of standards available for an industry."""
    exists = await db.fetchval(
        "SELECT 1 FROM industry_schemas WHERE id = $1", industry_id,
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Industry not found")
    async with db.transaction():
        await db.execute(
            "DELETE FROM industry_standards WHERE industry_schema_id = $1", industry_id,
        )
        for s in req.standards:
            await db.execute(
                "INSERT INTO industry_standards "
                "(industry_schema_id, standard_type_id, is_default, display_order) "
                "VALUES ($1, $2, $3, $4)",
                industry_id, s.standard_type_id, s.is_default, s.display_order,
            )
    return {"ok": True, "count": len(req.standards)}
