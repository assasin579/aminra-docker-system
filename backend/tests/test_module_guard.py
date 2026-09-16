from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from auth.module_guard import MODULE_GUARDS_ENV, require_module


class Row(dict):
    def __getattr__(self, item):
        return self[item]


async def test_require_module_allows_when_feature_flag_disabled(monkeypatch):
    monkeypatch.setenv(MODULE_GUARDS_ENV, "false")
    db = AsyncMock()

    await require_module("traceability")({"tenant_id": "tenant-1"}, db)

    db.fetchrow.assert_not_called()


async def test_require_module_allows_enabled_and_trial_modules(monkeypatch):
    monkeypatch.setenv(MODULE_GUARDS_ENV, "true")
    db = AsyncMock()
    guard = require_module("traceability")

    for status in ("enabled", "trial"):
        db.fetchrow = AsyncMock(return_value=Row(status=status))
        await guard({"tenant_id": "tenant-1"}, db)


async def test_require_module_blocks_disabled_module_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv(MODULE_GUARDS_ENV, "true")
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=Row(status="disabled"))

    with pytest.raises(HTTPException) as exc:
        await require_module("traceability")({"tenant_id": "tenant-1"}, db)

    assert exc.value.status_code == 403
    assert exc.value.detail == "MODULE_DISABLED:traceability"


async def test_require_module_blocks_missing_module_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv(MODULE_GUARDS_ENV, "true")
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await require_module("traceability")({"tenant_id": "tenant-1"}, db)

    assert exc.value.status_code == 403
    assert exc.value.detail == "MODULE_DISABLED:traceability"


async def test_require_module_requires_tenant_when_feature_flag_enabled(monkeypatch):
    monkeypatch.setenv(MODULE_GUARDS_ENV, "true")
    db = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await require_module("traceability")({"role": "business"}, db)

    assert exc.value.status_code == 403
    assert exc.value.detail == "TENANT_REQUIRED"
    db.fetchrow.assert_not_called()
