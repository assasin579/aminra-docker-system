from uuid import UUID
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from services.private_resources import PrivateScope, review_path, resolve_private_scope
A,B,T=[UUID(int=n) for n in range(1,4)]

def test_review_same_filename_never_shares_another_actor_tenant_or_legacy_file(tmp_path):
    scopes=[PrivateScope(A,T),PrivateScope(B,T),PrivateScope(A,B)]
    paths=[review_path(tmp_path,s,'../../résumé.pdf') for s in scopes]
    assert len(set(paths))==3
    assert all(p.is_relative_to(tmp_path) and p.parent.parent.parent==tmp_path for p in paths)
    assert review_path(tmp_path,scopes[0],'a:b.pdf')!=review_path(tmp_path,scopes[0],'a?b.pdf')
    legacy=tmp_path/'demo.pdf.json';legacy.write_text('synthetic other-tenant secret')
    assert not review_path(tmp_path,scopes[0],'demo.pdf').exists()

@pytest.mark.asyncio
async def test_private_scope_uses_database_tenant_instead_of_stale_token_mapper():
    db=AsyncMock();db.fetchrow.return_value={'id':A,'tenant_id':T,'status':'active'}
    scope=await resolve_private_scope({'app_user_id':str(A),'tenant_id':str(B)},db)
    assert scope==PrivateScope(A,T)

@pytest.mark.asyncio
@pytest.mark.parametrize('row',[None,{'id':A,'tenant_id':T,'status':'suspended'},{'id':A,'tenant_id':None,'status':'active'}])
async def test_private_scope_fails_closed_for_inactive_missing_or_unscoped_actor(row):
    db=AsyncMock();db.fetchrow.return_value=row
    with pytest.raises(HTTPException) as exc:await resolve_private_scope({'app_user_id':str(A)},db)
    assert exc.value.status_code==403

@pytest.mark.asyncio
async def test_job_owner_checked_before_payload_or_error_is_read(monkeypatch):
    import json
    from services import jobs
    pool=AsyncMock();pool.get.return_value=json.dumps([str(A),str(T)])
    monkeypatch.setattr(jobs,'get_pool',AsyncMock(return_value=pool))
    read=AsyncMock(return_value=jobs.JobView('synthetic','complete',{'private':'synthetic-a'},None))
    monkeypatch.setattr(jobs,'get_job_status',read)
    for scope in [PrivateScope(B,T),PrivateScope(A,B)]:
        with pytest.raises(HTTPException) as exc:await jobs.get_scoped_job_status('synthetic',scope)
        assert exc.value.status_code==404
    read.assert_not_awaited()
    assert (await jobs.get_scoped_job_status('synthetic',PrivateScope(A,T))).result=={'private':'synthetic-a'}

@pytest.mark.asyncio
@pytest.mark.parametrize('metadata',[None,b'not-json',b'null',b'[]'])
async def test_unbound_legacy_or_corrupted_job_metadata_is_not_public(monkeypatch,metadata):
    from services import jobs
    pool=AsyncMock();pool.get.return_value=metadata
    monkeypatch.setattr(jobs,'get_pool',AsyncMock(return_value=pool))
    read=AsyncMock();monkeypatch.setattr(jobs,'get_job_status',read)
    with pytest.raises(HTTPException) as exc:await jobs.get_scoped_job_status('synthetic',PrivateScope(A,T))
    assert exc.value.status_code==404;read.assert_not_awaited()

@pytest.mark.asyncio
async def test_job_owner_registration_failure_prevents_enqueue(monkeypatch):
    from services import jobs
    pool=AsyncMock();pool.set.side_effect=ConnectionError('synthetic Redis failure')
    monkeypatch.setattr(jobs,'get_pool',AsyncMock(return_value=pool))
    with pytest.raises(ConnectionError):await jobs.enqueue_scoped('ingest_document',PrivateScope(A,T),path='/tmp/synthetic')
    pool.enqueue_job.assert_not_awaited()
