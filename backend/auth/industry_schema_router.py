"""Industry schema routes — admin-managed CRUD + business-facing list.

Phase 1 (TASK #19, ADR-009 implicit):
  3 enabled schemas: food_manufacturing, restaurant_hotel,
  livestock_slaughter. All share same 13 doc_type set.

Phase 2 (defer): per-industry doc divergence when pilot CB demands.

Endpoints:
  GET  /api/industry-schemas                       — list enabled (any auth)
  GET  /api/industry-schemas/{code_or_id}          — detail
  POST /api/business/select-industry               — onboarding self-assign
  GET  /auth/admin/industry-schemas                — list incl. disabled
  POST /auth/admin/industry-schemas                — create
  PATCH /auth/admin/industry-schemas/{id}          — update
  DELETE /auth/admin/industry-schemas/{id}         — soft delete (enabled=false)
  PUT  /auth/admin/industry-schemas/{id}/doc-types — bulk replace doc_types
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

log = logging.getLogger("aminra.industry_schema")

router = APIRouter()         # mounted at /api/industry-schemas + /api/business
admin_router = APIRouter()   # mounted at /auth/admin/industry-schemas


# ── Pydantic schemas ────────────────────────────────────────────────────────


class DocTypeAssoc(BaseModel):
    doc_type: str
    required: bool = True
    display_order: int = 0


class StandardSummary(BaseModel):
    id: str
    code: str
    name_vi: str
    is_default: bool


class IndustrySchemaPublic(BaseModel):
    id: str
    code: str
    name_vi: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    jakim_scheme: Optional[str] = None  # DEPRECATED — use available_standards
    icon: Optional[str] = None
    enabled: bool
    display_order: int
    doc_types: List[DocTypeAssoc] = []  # DEPRECATED — use standard.doc_types per chosen standard
    available_standards: List[StandardSummary] = []


class IndustrySchemaCreate(BaseModel):
    code: str = Field(..., pattern=r"^[a-z][a-z0-9_]{2,49}$",
                      description="Slug: lowercase letters/digits/underscore, 3-50 chars")
    name_vi: str = Field(..., min_length=1, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    jakim_scheme: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    enabled: bool = True
    display_order: int = 0


class IndustrySchemaUpdate(BaseModel):
    name_vi: Optional[str] = Field(None, min_length=1, max_length=255)
    name_en: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    jakim_scheme: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    enabled: Optional[bool] = None
    display_order: Optional[int] = None


class DocTypesBulkReplace(BaseModel):
    doc_types: List[DocTypeAssoc]


class SelectIndustryRequest(BaseModel):
    schema_id: UUID


# ── Helpers ─────────────────────────────────────────────────────────────────


def _require_admin(user: dict) -> None:
    role = user.get("role")
    if role not in ("admin", "platform_admin", "provider"):
        # 'provider' = legacy admin role; 'admin'/'platform_admin' = Keycloak roles
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    # Require company_name match admin sentinel OR explicit admin flag
    if role == "provider" and user.get("email") != "admin@aminra.com":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")


async def _fetch_doc_types(db, schema_id: UUID) -> List[DocTypeAssoc]:
    rows = await db.fetch(
        "SELECT doc_type, required, display_order FROM schema_doc_types "
        "WHERE schema_id = $1 ORDER BY display_order, doc_type",
        schema_id,
    )
    return [DocTypeAssoc(**dict(r)) for r in rows]


async def _fetch_available_standards(db, industry_id: UUID) -> List[StandardSummary]:
    rows = await db.fetch(
        """SELECT st.id, st.code, st.name_vi, ins.is_default
           FROM industry_standards ins
           JOIN standard_types st ON st.id = ins.standard_type_id
           WHERE ins.industry_schema_id = $1 AND st.enabled = true
           ORDER BY ins.display_order, st.display_order""",
        industry_id,
    )
    return [
        StandardSummary(id=str(r["id"]), code=r["code"], name_vi=r["name_vi"],
                        is_default=r["is_default"])
        for r in rows
    ]


async def _row_to_public(db, row) -> IndustrySchemaPublic:
    doc_types = await _fetch_doc_types(db, row["id"])
    available_standards = await _fetch_available_standards(db, row["id"])
    return IndustrySchemaPublic(
        id=str(row["id"]),
        code=row["code"],
        name_vi=row["name_vi"],
        name_en=row["name_en"],
        description=row["description"],
        jakim_scheme=row["jakim_scheme"],
        icon=row["icon"],
        enabled=row["enabled"],
        display_order=row["display_order"],
        doc_types=doc_types,
        available_standards=available_standards,
    )


# ── Public endpoints ────────────────────────────────────────────────────────


@router.get("", response_model=List[IndustrySchemaPublic])
async def list_industry_schemas(
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List enabled industry schemas (any authenticated user)."""
    rows = await db.fetch(
        "SELECT id, code, name_vi, name_en, description, jakim_scheme, "
        "icon, enabled, display_order FROM industry_schemas "
        "WHERE enabled = true ORDER BY display_order, name_vi"
    )
    return [await _row_to_public(db, r) for r in rows]


@router.get("/{code_or_id}", response_model=IndustrySchemaPublic)
async def get_industry_schema(
    code_or_id: str,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Detail by code (slug) or UUID."""
    # Try UUID first
    try:
        sid = UUID(code_or_id)
        row = await db.fetchrow(
            "SELECT * FROM industry_schemas WHERE id = $1", sid,
        )
    except ValueError:
        row = await db.fetchrow(
            "SELECT * FROM industry_schemas WHERE code = $1", code_or_id,
        )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Industry schema not found")
    return await _row_to_public(db, row)


# ── Business onboarding self-assign ─────────────────────────────────────────


@router.post("/business-select")
async def select_industry(
    req: SelectIndustryRequest,
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Tenant owner assign their tenant to an industry schema during onboarding.

    Locked after first cert issued (admin-only override). Currently only
    business-role users can self-assign; they assign for their own tenant.
    """
    if user.get("role") != "business":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business users can self-select industry")
    if not user.get("is_owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only business owner can select industry")

    # Keycloak `sub` is the Keycloak UUID, not AMINRA DB user id.
    # `tenant_id` from JWT mapper may be a slug (e.g. "demo-biz"), not UUID.
    # Resolve DB user row by email — guaranteed unique + matches /auth/me
    # auto-provision pattern.
    db_user = await db.fetchrow(
        "SELECT id, tenant_id, industry_schema_id FROM users WHERE email = $1",
        user["email"],
    )
    if not db_user:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "User row not found in DB. Call /auth/me first to auto-provision.",
        )

    target_user_id = db_user["id"]
    if db_user["industry_schema_id"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Industry already assigned. Contact admin to change.",
        )

    # Validate schema exists + enabled
    schema_row = await db.fetchrow(
        "SELECT id, code, name_vi FROM industry_schemas WHERE id = $1 AND enabled = true",
        req.schema_id,
    )
    if not schema_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Industry schema not found or disabled")

    # Check no cert issued yet (lock policy)
    if await _table_exists(db, "certificates"):
        cert_count = await db.fetchval(
            "SELECT COUNT(*) FROM certificates WHERE business_tenant = $1",
            db_user["tenant_id"] or target_user_id,
        )
        if cert_count and cert_count > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Industry locked after cert issued. Contact admin for override.",
            )

    # Assign
    await db.execute(
        "UPDATE users SET industry_schema_id = $1 WHERE id = $2",
        req.schema_id, target_user_id,
    )
    log.info("[industry] user %s (%s) assigned to %s",
             target_user_id, user["email"], schema_row["code"])

    # Audit log — `target_user_id` (AMINRA users.id) already resolved above,
    # so reuse it. user["sub"] is the Keycloak UUID and would FK-violate.
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, 'tenant_industry_assigned', 'tenant_industry_schema', $2, $3::jsonb)",
        target_user_id, req.schema_id,
        f'{{"schema_code":"{schema_row["code"]}","schema_name":"{schema_row["name_vi"]}"}}',
    )

    return {
        "ok": True,
        "schema_id": str(req.schema_id),
        "schema_code": schema_row["code"],
    }


async def _table_exists(db, table_name: str) -> bool:
    r = await db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_name = $1)", table_name,
    )
    return bool(r)


# ── Admin endpoints ─────────────────────────────────────────────────────────


@admin_router.get("", response_model=List[IndustrySchemaPublic])
async def admin_list_all(
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """Admin sees all schemas including disabled."""
    rows = await db.fetch(
        "SELECT * FROM industry_schemas ORDER BY display_order, name_vi"
    )
    return [await _row_to_public(db, r) for r in rows]


@admin_router.post("", response_model=IndustrySchemaPublic, status_code=201)
async def admin_create(
    req: IndustrySchemaCreate,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    # Check uniqueness
    existing = await db.fetchval(
        "SELECT 1 FROM industry_schemas WHERE code = $1", req.code,
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Code '{req.code}' already exists")

    actor_id = await resolve_canonical_user_id(user, db)

    row = await db.fetchrow(
        """INSERT INTO industry_schemas
           (code, name_vi, name_en, description, jakim_scheme, icon,
            enabled, display_order, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           RETURNING *""",
        req.code, req.name_vi, req.name_en, req.description,
        req.jakim_scheme, req.icon, req.enabled, req.display_order,
        actor_id,
    )
    log.info("[industry] admin %s created schema %s", user["email"], req.code)

    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, 'industry_schema_created', 'industry_schema', $2, $3::jsonb)",
        actor_id, row["id"], f'{{"code":"{req.code}"}}',
    )
    return await _row_to_public(db, row)


@admin_router.patch("/{schema_id}", response_model=IndustrySchemaPublic)
async def admin_update(
    schema_id: UUID,
    req: IndustrySchemaUpdate,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    sets = []
    params = []
    idx = 1
    for field, val in req.model_dump(exclude_unset=True).items():
        sets.append(f"{field} = ${idx}")
        params.append(val)
        idx += 1
    if not sets:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
    sets.append(f"updated_at = NOW()")
    params.append(schema_id)
    row = await db.fetchrow(
        f"UPDATE industry_schemas SET {', '.join(sets)} "
        f"WHERE id = ${idx} RETURNING *",
        *params,
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found")

    actor_id = await resolve_canonical_user_id(user, db)
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, 'industry_schema_updated', 'industry_schema', $2, $3::jsonb)",
        actor_id, schema_id,
        '{"fields":' + str(list(req.model_dump(exclude_unset=True).keys())).replace("'", '"') + '}',
    )
    return await _row_to_public(db, row)


@admin_router.delete("/{schema_id}", status_code=204)
async def admin_disable(
    schema_id: UUID,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """Soft delete — set enabled=false. Tenants already assigned remain;
    only blocks new tenant onboarding to this schema."""
    result = await db.execute(
        "UPDATE industry_schemas SET enabled = false, updated_at = NOW() "
        "WHERE id = $1",
        schema_id,
    )
    if result.endswith("0"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found")

    actor_id = await resolve_canonical_user_id(user, db)
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id) "
        "VALUES ($1, 'industry_schema_disabled', 'industry_schema', $2)",
        actor_id, schema_id,
    )


@admin_router.put("/{schema_id}/doc-types")
async def admin_replace_doc_types(
    schema_id: UUID,
    req: DocTypesBulkReplace,
    user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """Bulk replace doc_type list for schema. Atomic."""

    exists = await db.fetchval(
        "SELECT 1 FROM industry_schemas WHERE id = $1", schema_id,
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found")

    async with db.transaction():
        await db.execute(
            "DELETE FROM schema_doc_types WHERE schema_id = $1", schema_id,
        )
        for dt in req.doc_types:
            await db.execute(
                "INSERT INTO schema_doc_types (schema_id, doc_type, required, display_order) "
                "VALUES ($1, $2, $3, $4)",
                schema_id, dt.doc_type, dt.required, dt.display_order,
            )

    actor_id = await resolve_canonical_user_id(user, db)
    await db.execute(
        "INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata) "
        "VALUES ($1, 'industry_schema_doc_types_replaced', 'industry_schema', $2, $3::jsonb)",
        actor_id, schema_id,
        f'{{"count":{len(req.doc_types)}}}',
    )
    return {"ok": True, "count": len(req.doc_types)}
