import ast
from pathlib import Path
import time
import httpx
import pytest
import respx
from fastapi import HTTPException
from auth import live_authority as guard

@pytest.fixture(autouse=True)
def setup(monkeypatch):
    guard._cache.clear()
    monkeypatch.setattr(guard.admin,'KEYCLOAK_ADMIN_URL','https://identity.example.invalid')
    monkeypatch.setattr(guard.admin,'KEYCLOAK_REALM','aminra')
    monkeypatch.setattr(guard.admin,'ADMIN_CLI_SECRET','synthetic-service-secret')
    monkeypatch.setattr(guard,'_TTL',2)
    monkeypatch.delenv('KEYCLOAK_AUTHZ_CLIENT_SECRET',raising=False)
    yield
    guard._cache.clear()

def claims(sub='subject-a'):
    return {'iss':'https://identity.example.invalid/realms/aminra','sub':sub,'exp':time.time()+300,'realm_access':{'roles':['platform_admin']}}

def routes(mock,sub='subject-a',roles=('business',)):
    base='https://identity.example.invalid'
    introspect=mock.post(base+'/realms/aminra/protocol/openid-connect/token/introspect',content__contains=('token=synthetic-'+sub.rsplit('-',1)[-1]).encode()).mock(return_value=httpx.Response(200,json={'active':True,'sub':sub}))
    mock.post(base+'/realms/aminra/protocol/openid-connect/token').mock(return_value=httpx.Response(200,json={'access_token':'synthetic-service-token'}))
    account=mock.get(base+'/admin/realms/aminra/users/'+sub).mock(return_value=httpx.Response(200,json={'id':sub,'enabled':True}))
    effective=mock.get(base+'/admin/realms/aminra/users/'+sub+'/role-mappings/realm/composite').mock(return_value=httpx.Response(200,json=[{'name':role} for role in roles]))
    return introspect,account,effective

@pytest.mark.asyncio
async def test_current_roles_override_stale_token_roles_and_cache_expires(monkeypatch):
    now=[1.0];monkeypatch.setattr(guard.time,'monotonic',lambda:now[0])
    with respx.mock as mock:
        _,_,effective=routes(mock,roles=('platform_admin',))
        assert await guard.current_realm_roles('synthetic-a',claims())==('platform_admin',)
        effective.mock(return_value=httpx.Response(200,json=[{'name':'cb_admin'}]))
        assert await guard.current_realm_roles('synthetic-a',claims())==('platform_admin',)
        now[0]+=3
        assert await guard.current_realm_roles('synthetic-a',claims())==('cb_admin',)
        assert effective.call_count==2

@pytest.mark.asyncio
async def test_concurrent_identity_cache_never_returns_another_subjects_roles():
    import asyncio
    with respx.mock as mock:
        routes(mock,'subject-a',('business',));routes(mock,'subject-b',('auditor',))
        results=await asyncio.gather(guard.current_realm_roles('synthetic-a',claims()),guard.current_realm_roles('synthetic-b',claims('subject-b')))
        assert results==[('business',),('auditor',)]
        assert await guard.current_realm_roles('synthetic-a',claims())==('business',)

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['inactive','wrong-subject','disabled','reader-denied','outage'])
async def test_revoked_or_unverifiable_identity_never_falls_back_to_jwt_authority(failure):
    with respx.mock as mock:
        introspect,account,effective=routes(mock)
        if failure=='inactive':introspect.mock(return_value=httpx.Response(200,json={'active':False}))
        if failure=='wrong-subject':introspect.mock(return_value=httpx.Response(200,json={'active':True,'sub':'foreign'}))
        if failure=='disabled':account.mock(return_value=httpx.Response(200,json={'id':'subject-a','enabled':False}))
        if failure=='reader-denied':effective.mock(return_value=httpx.Response(403))
        if failure=='outage':introspect.mock(side_effect=httpx.ConnectError('synthetic outage'))
        with pytest.raises(HTTPException) as exc:await guard.current_realm_roles('synthetic-a',claims())
        assert exc.value.status_code==(503 if failure in ('reader-denied','outage') else 401)
        assert not guard._cache

@pytest.mark.asyncio
async def test_missing_runtime_reader_credential_fails_closed(monkeypatch):
    monkeypatch.setattr(guard.admin,'ADMIN_CLI_SECRET','')
    with pytest.raises(HTTPException) as exc:await guard.current_realm_roles('synthetic-a',claims())
    assert exc.value.status_code==503

def test_raw_token_decode_is_not_used_as_resource_or_admin_authority():
    root=Path(__file__).parents[1]
    violations=[]
    for source in root.rglob('*.py'):
        if 'tests' in source.parts or source.relative_to(root).parts[0] not in ('auth','supply_chain') and source.name!='app.py':continue
        if source.relative_to(root).as_posix() in ('auth/jwt_utils.py','auth/rate_limit.py'):continue
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='decode_token':violations.append(str(source.relative_to(root))+':'+str(node.lineno))
    assert violations==[]

@pytest.mark.asyncio
async def test_overall_authority_budget_bounds_multiple_individually_valid_steps(monkeypatch, caplog):
    import asyncio
    monkeypatch.setattr(guard, '_VERIFY_BUDGET_SECONDS', 0.04)
    async def delayed_introspection(request):
        await asyncio.sleep(0.025)
        return httpx.Response(200, json={'active': True, 'sub': 'subject-a'})
    async def delayed_service(request):
        await asyncio.sleep(0.025)
        return httpx.Response(200, json={'access_token': 'synthetic-service-token'})
    with respx.mock as mock:
        introspect, _, _ = routes(mock)
        introspect.mock(side_effect=delayed_introspection)
        mock.post('https://identity.example.invalid/realms/aminra/protocol/openid-connect/token').mock(side_effect=delayed_service)
        with pytest.raises(HTTPException) as exc:
            await guard.current_realm_roles('synthetic-a', claims())
    assert exc.value.status_code == 503
    assert exc.value.headers['X-Aminra-Auth-Error'] == 'authority_unavailable'
    assert len(exc.value.headers['X-Aminra-Auth-Trace']) == 32
    assert 'reason=TimeoutError' in caplog.text
    assert not guard._cache

@pytest.mark.asyncio
async def test_failure_attribution_records_step_but_never_credentials_or_exception_text(caplog):
    with respx.mock as mock:
        _, _, effective = routes(mock)
        effective.mock(side_effect=httpx.ConnectError('DO-NOT-LOG synthetic-service-secret synthetic-a subject-a'))
        with pytest.raises(HTTPException) as exc:
            await guard.current_realm_roles('synthetic-a', claims())
    assert exc.value.status_code == 503
    assert 'stage=effective_roles' in caplog.text
    assert 'reason=ConnectError' in caplog.text
    for private in ['DO-NOT-LOG', 'synthetic-service-secret', 'synthetic-a', 'subject-a', 'identity.example.invalid']:
        assert private not in caplog.text
    assert exc.value.headers['X-Aminra-Auth-Trace'] in caplog.text
    assert not guard._cache
