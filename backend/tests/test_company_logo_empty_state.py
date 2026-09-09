"""Regression tests for company-logo empty-state behavior."""
from __future__ import annotations

import pytest
from fastapi.responses import Response

from auth import router as auth_router


@pytest.mark.asyncio
async def test_missing_company_logo_is_empty_204_not_error_404(monkeypatch, tmp_path):
    """Seed fixtures often have no uploaded logo; sidebar/settings image fetches
    should be a quiet empty state, not a console/error-monitoring 404."""
    monkeypatch.setattr(auth_router, "LOGO_DIR", tmp_path)

    result = await auth_router.get_company_logo("missing-tenant")

    assert isinstance(result, Response)
    assert result.status_code == 204
    assert result.body == b""
