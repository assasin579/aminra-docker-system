import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import dossier_router
from auth.db import get_db
from auth.jwt_utils import get_current_user


def test_dashboard_route_registered_before_dynamic():
    paths = [route.path for route in dossier_router.router.routes]
    assert paths.index('/dashboard') < paths.index('/{dossier_id}')


def test_dashboard_router_authorizes_before_data_access_and_uses_resolved_tenant(monkeypatch):
    app = FastAPI()
    app.include_router(dossier_router.router, prefix='/dossiers')
    calls = []

    class DB:
        async def fetch(self, *args, **kwargs):
            calls.append(('fetch', args))
        async def fetchrow(self, *args, **kwargs):
            calls.append(('fetchrow', args))

    db = DB()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: {'role': 'member', 'tenant_id': 'tenant-a'}
    with TestClient(app) as client:
        denied = client.get('/dossiers/dashboard')
    assert denied.status_code == 403
    assert calls == []

    tenant_uuid = '11111111-1111-4111-8111-111111111111'

    async def resolve_tenant(_db, user):
        assert user['role'] == 'business'
        return tenant_uuid

    async def build(_db, tenant_id, page, page_size):
        calls.append(('dashboard', tenant_id, page, page_size))
        return {'schema_version': '1.0', 'state': 'ready', 'as_of': '2026-10-26T00:00:00Z', 'page': page, 'page_size': page_size, 'total_dossiers': 0, 'profiles': []}

    monkeypatch.setattr(dossier_router, '_resolve_tenant_id', resolve_tenant)
    monkeypatch.setattr('services.dossier_dashboard.build_dashboard', build)
    app.dependency_overrides[get_current_user] = lambda: {'role': 'business', 'tenant_id': 'untrusted-claim'}
    with TestClient(app) as client:
        response = client.get('/dossiers/dashboard?page=2&page_size=10')
    assert response.status_code == 200
    assert calls[-1] == ('dashboard', tenant_uuid, 2, 10)


def test_dashboard_route_uses_canonical_tenant_not_claim_and_checks_access_before_lookup(monkeypatch):
    app = FastAPI()
    app.include_router(dossier_router.router, prefix='/dossiers')
    canonical_tenant = '11111111-1111-4111-8111-111111111111'
    user_id = '22222222-2222-4222-8222-222222222222'
    queries = []

    class DB:
        async def fetchrow(self, query, *args):
            queries.append(query)
            if 'FROM users WHERE id' in query:
                return {'id': user_id, 'tenant_id': canonical_tenant, 'is_owner': True}
            return None
        async def fetch(self, *args, **kwargs):
            queries.append(args[0])

    app.dependency_overrides[get_db] = lambda: DB()
    app.dependency_overrides[get_current_user] = lambda: {'role': 'business', 'app_user_id': user_id, 'tenant_id': '99999999-9999-4999-8999-999999999999'}
    received = []
    async def build(_db, tenant_id, page, page_size):
        received.append((tenant_id, page, page_size))
        return {'schema_version': '1.0', 'state': 'first_use', 'as_of': '2026-10-26T00:00:00Z', 'page': page, 'page_size': page_size, 'total_dossiers': 0, 'profiles': []}
    monkeypatch.setattr('services.dossier_dashboard.build_dashboard', build)
    with TestClient(app) as client:
        response = client.get('/dossiers/dashboard?page=2&page_size=10')
    assert response.status_code == 200
    assert received == [(canonical_tenant, 2, 10)]
    assert len(queries) == 1 and 'FROM users' in queries[0]

    app.dependency_overrides[get_current_user] = lambda: {'role': 'member', 'app_user_id': user_id, 'tenant_id': canonical_tenant}
    queries.clear()
    with TestClient(app) as client:
        denied = client.get('/dossiers/dashboard')
    assert denied.status_code == 403
    assert queries == []


def test_dashboard_service_exists():
    from services.dossier_dashboard import build_dashboard
    assert callable(build_dashboard)


@pytest.mark.asyncio
async def test_dashboard_service_groups_page_rows_by_profile_and_keeps_population_count(monkeypatch):
    from datetime import datetime, timezone
    from services import dossier_dashboard

    tenant = '11111111-1111-4111-8111-111111111111'
    rows = [
        {'id': 'd1', 'tenant_id': tenant, 'standard_type_id': 's1', 'requirements_version_id': 'v1', 'requirements_binding_status': 'bound', 'title': 'one', 'status': 'in_progress', 'updated_at': datetime(2026, 10, 26, tzinfo=timezone.utc)},
        {'id': 'd2', 'tenant_id': tenant, 'standard_type_id': None, 'requirements_version_id': None, 'requirements_binding_status': 'unknown', 'title': 'legacy', 'status': 'draft', 'updated_at': datetime(2026, 10, 25, tzinfo=timezone.utc)},
    ]
    class Tx:
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): return False
    class DB:
        def transaction(self, **kwargs):
            assert kwargs == {'isolation': 'repeatable_read', 'readonly': True}
            return Tx()
        async def fetchval(self, query, *args):
            assert 'transaction_timestamp' in query or ('tenant_id = $1' in query and args == (tenant,))
            return datetime(2026, 10, 26, tzinfo=timezone.utc) if 'transaction_timestamp' in query else 7
        async def fetch(self, query, *args):
            assert 'tenant_id = $1' in query and args == (tenant, 0, 2)
            assert "status != 'cancelled'" in query
            assert 'ORDER BY updated_at DESC, id ASC' in query
            return rows
        async def fetchrow(self, query, *args):
            assert 'standard_types' in query and args == ('s1',)
            return {'id': 's1', 'code': 'HALAL', 'name_vi': 'Halal'}
    async def readiness(_db, *, dossier_id, tenant_id):
        assert tenant_id == tenant
        return {'dossier_id': dossier_id, 'state': 'requirements_pending', 'readiness_percent': None if dossier_id == 'd2' else 50}
    monkeypatch.setattr(dossier_dashboard, 'compute_dossier_readiness', readiness)
    result = await dossier_dashboard.build_dashboard(DB(), tenant, page=1, page_size=2)
    assert result['total_dossiers'] == 7
    assert result['state'] == 'ready'
    assert [(p['id'], [d['id'] for d in p['dossiers']]) for p in result['profiles']] == [('s1', ['d1']), (None, ['d2'])]
    assert result['profiles'][0]['dossiers'][0]['readiness']['readiness_percent'] == 50
    assert result['profiles'][1]['dossiers'][0]['requirements_binding_status'] == 'unknown'


def test_dashboard_pagination_rejects_unbounded_page_size():
    from fastapi import HTTPException
    from services.dossier_dashboard import build_dashboard
    import asyncio
    with pytest.raises(HTTPException) as exc:
        asyncio.run(build_dashboard(object(), 'tenant', page=1, page_size=51))
    assert exc.value.status_code == 422
