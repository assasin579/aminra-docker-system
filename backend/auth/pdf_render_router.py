"""POST /api/templates/{doc_type}/render-pdf — HTML/CSS Playwright route.

Sibling of legacy `templates_docx` + libreoffice DOCX→PDF route. Rollout
gated per-doc_type by feature flag `pdf_html_renderer_v1.{doc_type}` so
the new route can be enabled tenant-by-tenant before full cutover.

Audit log written for every render (success OR failure) so regulators can
prove which actor rendered what document at what time — even when the
render itself failed (admission control reject, browser crash).
"""

from __future__ import annotations

import json
import logging
import time
import unicodedata
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from auth.jwt_utils import get_current_user
from auth.rate_limit import rate_limit_pdf_render
from services import feature_flags
from services.audit_log import log_audit
from services.pdf_data_aggregator import PDFDataAggregator
from services.pdf_filter_pipeline import FilterPipeline
from services.pdf_render_schemas import get_schema
from services.pdf_renderer import (
    RenderConcurrencyError,
    RenderHTMLTooLargeError,
    RenderTimeoutError,
    TemplateNotFoundError,
    TemplateNotImplementedError,
    etag_for,
)
from templates_html._registry import get_entry, list_supported

from auth.db import get_db
from pydantic import ValidationError as _PydValidationError

log = logging.getLogger("aminra.pdf_render_router")

router = APIRouter()

# ── Request body ────────────────────────────────────────────────────────────


class RenderPDFBody(BaseModel):
    data: dict[str, Any] = Field(
        ...,
        description="Doc-type-specific input. Validated against pdf_render_schemas.<DocType>Data.",
    )
    title: Optional[str] = Field(
        None,
        max_length=200,
        description="Document title shown on cover. Falls back to registry default.",
    )
    cfg_override: Optional[dict[str, Any]] = Field(
        None,
        description="Admin-only override for cfg JSON. Non-admins MUST omit (else 403).",
    )
    is_draft: bool = Field(
        True,
        description=(
            "Render with DRAFT watermark (default true for tenant-rendered docs). "
            "Set false only for CB-issued documents — currently not gated; will be "
            "tightened in Phase 2 multi-CB rollout."
        ),
    )
    lang: str = Field("vi", pattern=r"^(vi|en)$")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _canonical_json(payload: dict[str, Any]) -> bytes:
    """Stable bytes for ETag: sorted keys, no spaces, ensure_ascii false."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


async def _load_cfg(db, doc_type: str) -> dict[str, Any]:
    """Load cfg JSON from admin_templates/<doc_type>.json (filesystem).

    The legacy `templates_docx/_registry.py:_load_docx_config` reads the
    same file; we reuse that exact path so admin UI changes apply to both
    DOCX + HTML routes simultaneously.
    """
    from pathlib import Path
    cfg_path = Path("admin_templates") / f"{doc_type}.json"
    if not cfg_path.exists():
        return {}
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        return raw.get("docx_config") or {}
    except Exception as exc:                                         # noqa: BLE001
        log.warning("[pdf_render] cfg load failed for %s: %s", doc_type, exc)
        return {}


def _is_platform_admin(user: dict) -> bool:
    return user.get("role") == "admin" or bool(user.get("is_platform_admin"))


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/render-pdf/health", tags=["pdf-render"])
async def health(request: Request) -> dict:
    """Liveness probe for the renderer browser pool."""
    renderer = request.app.state.pdf_renderer
    info = renderer.health()
    if info.get("browser") != "ok":
        return Response(
            content=json.dumps(info), media_type="application/json", status_code=503
        )
    return info


@router.get("/render-pdf/registry", tags=["pdf-render"])
async def registry(user: dict = Depends(get_current_user)) -> list[dict]:
    """List all known doc_types and whether each has a shipped HTML template."""
    return list_supported()


@router.get("/{doc_type}/placeholder-coverage", tags=["pdf-render"])
async def placeholder_coverage(
    doc_type: str = Path(..., min_length=1, max_length=64),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    """Return per-field coverage map for a doc_type given the caller's
    company data.

    Used by FE create-document page to display "% real data" badge before
    user commits to generate. Helps user understand which company fields
    they should fill (in Settings/Company) to reduce placeholder fill.
    """
    from services.template_field_coverage import calculate_coverage

    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    # Resolve canonical tenant UUID. JWT tenant_id may be:
    #   - valid UUID (legacy JWT path) → use directly
    #   - Keycloak slug like "demo-biz" → fall through to DB email lookup
    #   - None (Keycloak before /auth/me provisioned) → DB email lookup
    import uuid as _uuid
    tenant_id = None
    raw_tenant = user.get("tenant_id")
    if raw_tenant:
        try:
            _uuid.UUID(str(raw_tenant))
            tenant_id = raw_tenant
        except (ValueError, TypeError):
            tenant_id = None
    if not tenant_id:
        row = await db.fetchrow(
            "SELECT id, tenant_id FROM users WHERE email = $1", user["email"],
        )
        if not row:
            raise HTTPException(404, "User row not found. Call /auth/me first.")
        tenant_id = row["tenant_id"] or row["id"]

    user_row = await db.fetchrow(
        """SELECT company_name, address, phone, email, representative_name,
                  founded_year, total_employees, halal_commitment_statement,
                  najis_handling_policy, cross_contamination_controls,
                  product_categories, primary_suppliers,
                  ingredient_origin_countries, packaging_materials_brief,
                  ihc_chairman_name, ihc_chairman_title, ihc_inception_date,
                  ihc_members_brief, ihc_meeting_frequency,
                  production_capacity_brief
           FROM users WHERE id = $1 AND is_owner = true""",
        tenant_id,
    )
    if not user_row:
        raise HTTPException(404, "Tenant owner row not found")

    # Convert ihc_inception_date (date) to iso string for display preview
    row_dict = dict(user_row)
    if row_dict.get("ihc_inception_date"):
        row_dict["ihc_inception_date"] = row_dict["ihc_inception_date"].isoformat()

    return calculate_coverage(row_dict, doc_type)


@router.post(
    "/{doc_type}/render-pdf",
    tags=["pdf-render"],
    responses={
        200: {"content": {"application/pdf": {}}},
        400: {"description": "data fails Pydantic validation"},
        403: {"description": "RBAC fail or non-admin set cfg_override"},
        404: {"description": "doc_type unknown to registry"},
        408: {"description": "render exceeded timeout"},
        413: {"description": "rendered HTML exceeded size budget"},
        501: {"description": "doc_type known but HTML template not yet implemented"},
        503: {"description": "renderer queue full or browser down"},
    },
)
async def render_pdf(
    request: Request,
    body: RenderPDFBody,
    doc_type: str = Path(..., pattern=r"^[a-z_][a-z0-9_]{1,40}$"),
    user: dict = Depends(get_current_user),
    db=Depends(get_db),
    _rl: None = Depends(rate_limit_pdf_render),
) -> Response:
    started = time.monotonic()
    tenant_id = user.get("tenant_id")
    actor_id = user.get("sub")

    # ── 1. cfg_override is admin-only ──────────────────────────────────────
    if body.cfg_override is not None and not _is_platform_admin(user):
        await log_audit(
            db, action="document.pdf_render_denied", entity_type="pdf_template",
            user=user, entity_id=None,
            metadata={"doc_type": doc_type, "reason": "cfg_override_non_admin"}, request=request,
        )
        raise HTTPException(status_code=403, detail="cfg_override is admin-only")

    # ── 2. Feature flag gate (per doc_type) ────────────────────────────────
    flag_name = f"pdf_html_renderer_v1.{doc_type}"
    if not await feature_flags.is_feature_enabled(db, tenant_id, flag_name):
        # Surfaced as 404 so the frontend treats it like "no HTML template
        # for this doc_type" and falls back to the DOCX route. Not 403,
        # which would imply auth failure.
        raise HTTPException(status_code=404, detail=f"feature {flag_name} disabled")

    # ── 3. Resolve template + schema ───────────────────────────────────────
    entry = get_entry(doc_type)
    if entry is None:
        # Either unknown doc_type → 404, or known-but-not-implemented → 501.
        from templates_html._registry import is_known_doc_type
        if is_known_doc_type(doc_type):
            raise HTTPException(status_code=501, detail=f"{doc_type} HTML template not implemented")
        raise HTTPException(status_code=404, detail=f"unknown doc_type: {doc_type}")

    schema = get_schema(doc_type)
    if schema is None:
        raise HTTPException(status_code=501, detail=f"{doc_type} schema not implemented")

    title = body.title or entry.title_default

    # ── 4. Stage 1 — aggregate raw data (DB + admin files + payload) ──────
    aggregator: PDFDataAggregator = request.app.state.pdf_aggregator
    bundle = await aggregator.fetch(
        db=db,
        doc_type=doc_type,
        tenant_id=str(tenant_id) if tenant_id else "",
        actor=user,
        request_payload=dict(body.data),
        request_lang=body.lang,
        is_draft=body.is_draft,
    )

    # ── 5. Stage 2 — filter pipeline (validate + merge + format + truncate) ─
    filter_pipeline: FilterPipeline = request.app.state.pdf_filter_pipeline
    try:
        ctx = filter_pipeline.run(bundle, title=title, title_default=entry.title_default)
    except _PydValidationError as exc:
        await log_audit(
            db, action="document.pdf_render_invalid", entity_type="pdf_template",
            user=user, entity_id=None,
            metadata={"doc_type": doc_type, "errors_count": len(exc.errors())}, request=request,
        )
        raise HTTPException(status_code=400, detail=exc.errors())

    # cfg_override merge (admin-only) — applied AFTER filters so admin
    # truly overrides the merged context (defence in depth).
    if body.cfg_override and _is_platform_admin(user):
        ctx.cfg = {**ctx.cfg, **body.cfg_override}

    # ── 6. ETag from filtered context (deterministic per input) ────────────
    canonical = _canonical_json(ctx.data)
    etag = etag_for(entry.version, canonical)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    # ── 7. Stage 3 — render (Playwright unchanged) ─────────────────────────
    renderer = request.app.state.pdf_renderer
    try:
        pdf_bytes = await renderer.render(
            doc_type=doc_type,
            data=ctx.data,
            cfg=ctx.cfg,
            title=ctx.title,
            is_draft=ctx.is_draft,
            content="",
            lang=ctx.lang,
        )
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown doc_type: {doc_type}")
    except TemplateNotImplementedError:
        raise HTTPException(status_code=501, detail=f"{doc_type} HTML template not implemented")
    except RenderHTMLTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except RenderTimeoutError as exc:
        await log_audit(
            db, action="document.pdf_render_timeout", entity_type="pdf_template",
            user=user, entity_id=None,
            metadata={"doc_type": doc_type}, request=request,
        )
        raise HTTPException(status_code=408, detail=str(exc))
    except RenderConcurrencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc),
                            headers={"Retry-After": "5"})
    except Exception as exc:                                          # noqa: BLE001
        log.exception("[pdf_render] unexpected failure for %s", doc_type)
        await log_audit(
            db, action="document.pdf_render_failed", entity_type="pdf_template",
            user=user, entity_id=None,
            metadata={"doc_type": doc_type, "error": str(exc)[:200]}, request=request,
        )
        raise HTTPException(status_code=500, detail="internal renderer error")

    duration_ms = int((time.monotonic() - started) * 1000)

    await log_audit(
        db, action="document.pdf_rendered", entity_type="pdf_template",
        user=user, entity_id=None,
        metadata={
            "doc_type": doc_type,
            "byte_size": len(pdf_bytes),
            "duration_ms": duration_ms,
            "template_version": entry.version,
            "is_draft": body.is_draft,
            "filters_applied": ctx.filters_applied,
            "filter_durations_ms": ctx.filter_durations_ms,
            "sources_versions": bundle.sources_versions,
            # Surfaces gaps in tenant data — operators monitor this metric
            # to nudge incomplete profiles toward completion.
            "placeholder_filled_fields": ctx.cfg.get("_placeholder_filled_fields", []),
        }, request=request,
    )

    # Filename must be ASCII for legacy `filename=` (RFC 6266 §4.1) and
    # also exposed as UTF-8 via filename*= for modern clients.
    raw_name = title.replace('"', "").replace("\n", " ")[:120]
    ascii_name = (
        unicodedata.normalize("NFKD", raw_name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    ) or "document"
    utf8_name = quote(raw_name.encode("utf-8"))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}.pdf"; '
                f"filename*=UTF-8''{utf8_name}.pdf"
            ),
            "ETag": etag,
            "Cache-Control": "private, max-age=0, must-revalidate",
            "X-Render-Duration-Ms": str(duration_ms),
            "X-Template-Version": entry.version,
        },
    )
