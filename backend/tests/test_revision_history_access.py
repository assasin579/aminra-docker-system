from uuid import UUID
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from auth import submission_router as router
from services import submission_revisions

B=UUID('10000000-0000-0000-0000-000000000001')
P=UUID('20000000-0000-0000-0000-000000000001')
A=UUID('30000000-0000-0000-0000-000000000001')
X=UUID('40000000-0000-0000-0000-000000000001')
S='50000000-0000-0000-0000-000000000001'

@pytest.mark.asyncio
@pytest.mark.parametrize('role,owner,tenant,actor,allowed',[
 ('business',True,B,B,True),('business',False,B,X,True),
 ('provider',True,P,P,True),('provider',False,P,A,True),
 ('business',True,X,X,False),('business',False,X,X,False),
 ('provider',True,X,X,False),('provider',False,P,X,False),
 ('provider',False,X,X,False),('platform_admin',True,P,P,False),
 ('business',True,None,B,False),('provider',True,None,P,False),
])
async def test_history_access_uses_uuid_identities(monkeypatch,role,owner,tenant,actor,allowed):
 db=AsyncMock(); db.fetchrow.return_value={'business_tenant':B,'provider_id':P,'auditor_id':A}
 monkeypatch.setattr(router,'resolve_canonical_tenant_id',AsyncMock(return_value=tenant))
 monkeypatch.setattr(router,'resolve_canonical_user_id',AsyncMock(return_value=actor))
 history=AsyncMock(return_value=[{'round':1,'feedback':'correct policy'}])
 monkeypatch.setattr(submission_revisions,'list_revision_history',history)
 user={'role':role,'is_owner':owner}
 if allowed:
  result=await router.get_revision_history(S,user,db)
  assert result=={'submission_id':S,'history':[{'round':1,'feedback':'correct policy'}]}
  history.assert_awaited_once_with(db,S)
 else:
  with pytest.raises(HTTPException) as exc: await router.get_revision_history(S,user,db)
  assert exc.value.status_code==403
  history.assert_not_awaited()

@pytest.mark.asyncio
async def test_missing_submission_does_not_resolve_or_read_history(monkeypatch):
 db=AsyncMock(); db.fetchrow.return_value=None
 resolve=AsyncMock();monkeypatch.setattr(router,'resolve_canonical_tenant_id',resolve)
 with pytest.raises(HTTPException) as exc:await router.get_revision_history(S,{'role':'business'},db)
 assert exc.value.status_code==404
 resolve.assert_not_awaited()

@pytest.mark.asyncio
async def test_unassigned_auditor_denied(monkeypatch):
 db=AsyncMock();db.fetchrow.return_value={'business_tenant':B,'provider_id':P,'auditor_id':None}
 with pytest.raises(HTTPException) as exc:await router.get_revision_history(S,{'role':'provider','is_owner':False},db)
 assert exc.value.status_code==403
