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
            INSERT INTO tenant_modules (tenant_id, module_id, status, source, config)
            SELECT $1,
                   bmm.module_id,
                   CASE WHEN bmm.default_enabled THEN 'enabled' ELSE 'disabled' END,
                   'business_model_default',
                   COALESCE(bmm.config_schema, '{}'::jsonb)
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
               tm.config
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
            }
            for row in rows
        ],
    }
