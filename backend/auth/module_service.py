from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row[key]
    return row[key]


def _normalize_jsonb(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


async def provision_tenant_modules_for_industry(
    db: Any,
    tenant_id: Any,
    industry_schema_id: Any,
) -> int:
    """Provision tenant module rows from the selected business model defaults.

    Idempotent by `(tenant_id, module_id)`. Admin overrides are authoritative:
    if a row was manually changed with `source='admin_override'`, onboarding or
    re-provisioning must not silently overwrite its status/source/config.
    """
    if not tenant_id:
        raise HTTPException(status_code=403, detail="TENANT_REQUIRED")

    count = await db.fetchval(
        """
        WITH provisioned AS (
            INSERT INTO tenant_modules (
                tenant_id,
                module_id,
                status,
                source,
                config,
                enabled_at,
                disabled_at
            )
            SELECT $1,
                   bmm.module_id,
                   CASE WHEN bmm.default_enabled THEN 'enabled' ELSE 'disabled' END,
                   'business_model_default',
                   COALESCE(bmm.config_schema, '{}'::jsonb),
                   CASE WHEN bmm.default_enabled THEN NOW() ELSE NULL END,
                   CASE WHEN bmm.default_enabled THEN NULL ELSE NOW() END
            FROM business_model_modules bmm
            JOIN modules m ON m.id = bmm.module_id
            WHERE bmm.industry_schema_id = $2
              AND m.enabled = true
            ON CONFLICT (tenant_id, module_id) DO UPDATE SET
                status = CASE
                    WHEN tenant_modules.source = 'admin_override' THEN tenant_modules.status
                    ELSE EXCLUDED.status
                END,
                source = CASE
                    WHEN tenant_modules.source = 'admin_override' THEN tenant_modules.source
                    ELSE EXCLUDED.source
                END,
                config = CASE
                    WHEN tenant_modules.source = 'admin_override' THEN tenant_modules.config
                    ELSE EXCLUDED.config
                END,
                enabled_at = CASE
                    WHEN tenant_modules.source = 'admin_override' THEN tenant_modules.enabled_at
                    WHEN EXCLUDED.status IN ('enabled', 'trial') THEN COALESCE(tenant_modules.enabled_at, NOW())
                    ELSE NULL
                END,
                disabled_at = CASE
                    WHEN tenant_modules.source = 'admin_override' THEN tenant_modules.disabled_at
                    WHEN EXCLUDED.status IN ('disabled', 'locked') THEN COALESCE(tenant_modules.disabled_at, NOW())
                    ELSE NULL
                END,
                updated_at = NOW()
            RETURNING module_id
        )
        SELECT COUNT(*) FROM provisioned
        """,
        tenant_id,
        industry_schema_id,
    )
    return int(count or 0)


async def get_current_tenant_modules(db: Any, user: dict[str, Any]) -> dict[str, Any]:
    """Return the module registry view for the current user's tenant.

    This endpoint is read-only. Provisioning/backfill belongs to the migration
    and later onboarding service, not to GET /api/me/modules.
    """
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="TENANT_REQUIRED")

    business_model = await db.fetchrow(
        """
        SELECT i.code AS industry_code,
               i.name_vi AS industry_name_vi,
               i.name_en AS industry_name_en
        FROM users u
        LEFT JOIN industry_schemas i ON i.id = u.industry_schema_id
        WHERE u.tenant_id = $1 AND u.industry_schema_id IS NOT NULL
        ORDER BY u.is_owner DESC, u.created_at ASC
        LIMIT 1
        """,
        tenant_id,
    )

    rows = await db.fetch(
        """
        SELECT m.code,
               m.name_vi,
               m.name_en,
               m.category,
               tm.status,
               COALESCE(bmm.required, false) AS required,
               COALESCE(bmm.default_enabled, false) AS default_enabled,
               COALESCE(bmm.display_order, m.display_order) AS display_order,
               tm.config,
               tm.source,
               tm.updated_at
        FROM tenant_modules tm
        JOIN modules m ON m.id = tm.module_id
        LEFT JOIN users u
          ON u.tenant_id = tm.tenant_id
         AND u.industry_schema_id IS NOT NULL
         AND u.is_owner = true
        LEFT JOIN business_model_modules bmm
          ON bmm.industry_schema_id = u.industry_schema_id
         AND bmm.module_id = tm.module_id
        WHERE tm.tenant_id = $1
          AND m.enabled = true
        ORDER BY COALESCE(bmm.display_order, m.display_order), m.code
        """,
        tenant_id,
    )

    return {
        "business_model": None
        if not business_model
        else {
            "code": _row_value(business_model, "industry_code"),
            "name_vi": _row_value(business_model, "industry_name_vi"),
            "name_en": _row_value(business_model, "industry_name_en"),
        },
        "modules": [
            {
                "code": _row_value(row, "code"),
                "name_vi": _row_value(row, "name_vi"),
                "name_en": _row_value(row, "name_en"),
                "category": _row_value(row, "category"),
                "status": _row_value(row, "status"),
                "required": bool(_row_value(row, "required")),
                "default_enabled": bool(_row_value(row, "default_enabled")),
                "display_order": int(_row_value(row, "display_order")),
                "config": _normalize_jsonb(_row_value(row, "config")),
                "source": _row_value(row, "source"),
                "updated_at": _row_value(row, "updated_at"),
                "access_state": _access_state(_row_value(row, "status")),
                "access_label_vi": _access_label_vi(_row_value(row, "status")),
                "cta_label_vi": _cta_label_vi(_row_value(row, "status")),
                "route_path": _MODULE_ROUTE_PATHS.get(_row_value(row, "code")),
            }
            for row in rows
        ],
    }


_ADMIN_MUTABLE_STATUSES = {"enabled", "trial", "disabled", "locked"}
_ACTIVE_STATUSES = {"enabled", "trial"}
_MODULE_ROUTE_PATHS = {
    "certification_dossier": "/dossiers",
    "document_management": "/documents",
    "supplier_management": "/supply-chain/materials",
    "traceability": "/supply-chain/batches",
    "process_digitization": "/supply-chain/process",
    "workforce": "/members",
    "daily_operations": None,
    "audit_compliance": "/audits",
    "public_trace": "/trace",
    "notifications": None,
}


def _access_state(status: str) -> str:
    if status == "enabled":
        return "active"
    if status == "trial":
        return "trial"
    if status == "locked":
        return "locked"
    return "disabled"


def _access_label_vi(status: str) -> str:
    state = _access_state(status)
    return {
        "active": "Đang hoạt động",
        "trial": "Đang dùng thử",
        "locked": "Đang khóa",
        "disabled": "Chưa kích hoạt",
    }[state]


def _cta_label_vi(status: str) -> str:
    return "Mở module" if status in _ACTIVE_STATUSES else "Yêu cầu kích hoạt"


async def set_tenant_module_status(
    db: Any,
    tenant_id: Any,
    module_code: str,
    status: str,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Safely set one tenant module status as an admin override.

    This is the backend management-plane primitive for sandbox module toggles.
    It enforces required dependency invariants before writing so admin tooling
    cannot create a graph that the frontend/backend interpret inconsistently.
    """
    if not tenant_id:
        raise HTTPException(status_code=403, detail="TENANT_REQUIRED")
    if status not in _ADMIN_MUTABLE_STATUSES:
        raise HTTPException(status_code=422, detail="INVALID_MODULE_STATUS")

    module_row = await db.fetchrow(
        """
        SELECT m.id AS module_id,
               m.code,
               COALESCE(bmm.required, false) AS required
        FROM tenant_modules tm
        JOIN modules m ON m.id = tm.module_id
        LEFT JOIN users u
          ON u.tenant_id = tm.tenant_id
         AND u.industry_schema_id IS NOT NULL
         AND u.is_owner = true
        LEFT JOIN business_model_modules bmm
          ON bmm.industry_schema_id = u.industry_schema_id
         AND bmm.module_id = tm.module_id
        WHERE tm.tenant_id = $1
          AND m.code = $2
          AND m.enabled = true
        LIMIT 1
        """,
        tenant_id,
        module_code,
    )
    if not module_row:
        raise HTTPException(status_code=404, detail=f"MODULE_NOT_FOUND:{module_code}")

    required = bool(_row_value(module_row, "required"))
    if required and status not in _ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"MODULE_REQUIRED:{module_code}")

    missing_dependencies = await db.fetch(
        """
        SELECT dep.code
        FROM module_dependencies md
        JOIN modules target ON target.id = md.module_id
        JOIN modules dep ON dep.id = md.depends_on_module_id
        LEFT JOIN tenant_modules dep_tm
          ON dep_tm.tenant_id = $1
         AND dep_tm.module_id = dep.id
        WHERE target.code = $2
          AND md.dependency_type = 'requires'
          AND COALESCE(dep_tm.status, 'missing') NOT IN ('enabled', 'trial')
        ORDER BY dep.code
        """,
        tenant_id,
        module_code,
    )
    if status in _ACTIVE_STATUSES and missing_dependencies:
        code = _row_value(missing_dependencies[0], "code")
        raise HTTPException(status_code=409, detail=f"MODULE_DEPENDENCY_MISSING:{code}")

    enabled_dependents = await db.fetch(
        """
        SELECT dependent.code
        FROM module_dependencies md
        JOIN modules dep ON dep.id = md.depends_on_module_id
        JOIN modules dependent ON dependent.id = md.module_id
        JOIN tenant_modules tm
          ON tm.tenant_id = $1
         AND tm.module_id = dependent.id
        WHERE dep.code = $2
          AND md.dependency_type = 'requires'
          AND tm.status IN ('enabled', 'trial')
        ORDER BY dependent.code
        """,
        tenant_id,
        module_code,
    )
    if status not in _ACTIVE_STATUSES and enabled_dependents:
        code = _row_value(enabled_dependents[0], "code")
        raise HTTPException(status_code=409, detail=f"MODULE_DEPENDENT_ENABLED:{code}")

    normalized_config = config or {}
    await db.execute(
        """
        UPDATE tenant_modules
        SET status = $3,
            source = 'admin_override',
            config = $4::jsonb,
            updated_at = NOW()
        FROM modules m
        WHERE tenant_modules.module_id = m.id
          AND tenant_modules.tenant_id = $1
          AND m.code = $2
        """,
        tenant_id,
        module_code,
        status,
        json.dumps(normalized_config),
    )

    return {
        "tenant_id": str(tenant_id),
        "module_code": module_code,
        "status": status,
        "source": "admin_override",
        "config": normalized_config,
    }
