from unittest.mock import AsyncMock
import pytest
from services import worker_readiness as probe


@pytest.mark.asyncio
async def test_probe_checks_real_connection_and_closes_its_own_pool(monkeypatch):
    pool = AsyncMock()
    pool.ping.return_value = True
    monkeypatch.setattr(probe, "get_pool", AsyncMock(return_value=pool))
    await probe.check_ready()
    pool.ping.assert_awaited_once()
    pool.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_unhealthy_connection_is_not_reported_as_ready(monkeypatch):
    pool = AsyncMock()
    pool.ping.return_value = False
    monkeypatch.setattr(probe, "get_pool", AsyncMock(return_value=pool))
    with pytest.raises(RuntimeError, match="Redis readiness failed"):
        await probe.check_ready()
    pool.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_wrong_worker_contract_fails_before_connecting(monkeypatch):
    monkeypatch.setattr(probe, "ingest_document", lambda context, path: None)
    connect = AsyncMock()
    monkeypatch.setattr(probe, "get_pool", connect)
    with pytest.raises(RuntimeError, match="shared-reference scope"):
        await probe.check_ready()
    connect.assert_not_awaited()
