"""Observe actual ASGI send ordering; buffered clients hide after-response commits."""
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import UUID
import pytest
from fastapi import FastAPI
from auth import audit_router as audit

PROVIDER=UUID(int=101);BUSINESS=UUID(int=102);VISIT=UUID(int=103)
class DB:
    def __init__(self,fail=False):self.committed=False;self.active=False;self.fail=fail
    @asynccontextmanager
    async def transaction(self):
        self.active=True
        try:
            yield self
            if self.fail:raise RuntimeError('synthetic commit failure')
            self.committed=True
        finally:self.active=False
    async def fetchrow(self,sql,*args):
        assert self.active and 'INSERT INTO audit_visits' in sql
        return {'id':VISIT}

def app_with_db(monkeypatch,db):
    app=FastAPI();app.include_router(audit.router,prefix='/audits')
    async def connection():yield db
    async def principal():return {'role':'provider','is_owner':True}
    app.dependency_overrides[audit.get_db]=connection
    app.dependency_overrides[audit.get_current_user]=principal
    monkeypatch.setattr(audit,'_require_audit_owner',AsyncMock(return_value=PROVIDER))
    monkeypatch.setattr(audit,'_require_business_relationship',AsyncMock())
    monkeypatch.setattr(audit,'resolve_canonical_tenant_id',AsyncMock(return_value=PROVIDER))
    return app

async def dispatch(app,db):
    messages=[];error=None
    body=json.dumps({'business_tenant':str(BUSINESS),'visit_type':'initial','scheduled_date':'2026-11-02'}).encode()
    scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/audits/','raw_path':b'/audits/','root_path':'','query_string':b'','headers':[(b'content-type',b'application/json')],'server':('test',80),'client':('test',123)}
    async def receive():return {'type':'http.request','body':body,'more_body':False}
    async def send(message):messages.append({**message,'committed_when_sent':db.committed})
    try:await app(scope,receive,send)
    except RuntimeError as exc:error=exc
    return messages,error

@pytest.mark.asyncio
async def test_audit_success_is_not_sent_until_its_transaction_commits(monkeypatch):
    db=DB();messages,error=await dispatch(app_with_db(monkeypatch,db),db)
    assert error is None
    start=next(m for m in messages if m['type']=='http.response.start')
    assert start['status']==200
    assert start['committed_when_sent'], 'Audit success escaped before commit'

@pytest.mark.asyncio
async def test_audit_commit_failure_never_reaches_client_as_success(monkeypatch):
    db=DB(fail=True);messages,error=await dispatch(app_with_db(monkeypatch,db),db)
    assert isinstance(error,RuntimeError)
    assert [m['status'] for m in messages if m['type']=='http.response.start']==[500]
    assert not db.committed


def test_all_scoped_audit_transactions_finish_before_response_send():
    import inspect
    checked=0
    for route in audit.router.routes:
        for parameter in inspect.signature(route.endpoint).parameters.values():
            dependency=parameter.default
            if getattr(dependency,'dependency',None) is audit.get_scoped_audit_db:
                assert dependency.scope=='function', route.path
                checked+=1
    assert checked>=22
