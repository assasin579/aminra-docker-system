from uuid import UUID
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from auth.identity import get_or_reconcile_user_from_keycloak_claims
A,B,S=[UUID(int=n) for n in range(1,4)]
def principal(**kw):return {'_keycloak':True,'keycloak_sub':str(S),'sub':str(S),'email':'new@example.invalid','role':'business','is_owner':True,'status':'active','tenant_id':str(B),**kw}
def row(**kw):return {'id':A,'keycloak_sub':S,'email':'new@example.invalid','role':'business','is_owner':True,'status':'active','tenant_id':None,**kw}

@pytest.mark.asyncio
async def test_owner_bootstrap_cannot_claim_an_existing_tenant_from_token_attributes():
 db=AsyncMock();db.fetchrow.side_effect=[None,None,row(),row(tenant_id=A)]
 actual=await get_or_reconcile_user_from_keycloak_claims(principal(),db)
 insert=db.fetchrow.call_args_list[2]
 assert insert.args[-1] is None
 assert actual['tenant_id']==A

@pytest.mark.asyncio
async def test_missing_member_projection_requires_real_invitation_not_claimed_tenant():
 db=AsyncMock();db.fetchrow.side_effect=[None,None,row(is_owner=False,tenant_id=B)]
 with pytest.raises(HTTPException) as exc:await get_or_reconcile_user_from_keycloak_claims(principal(is_owner=False),db)
 assert exc.value.status_code==403
 assert len(db.fetchrow.call_args_list)==2

@pytest.mark.asyncio
async def test_email_reuse_cannot_rebind_an_existing_subject():
 db=AsyncMock();db.fetchrow.side_effect=[None,row(keycloak_sub=B),row(),row(tenant_id=A)]
 with pytest.raises(HTTPException) as exc:await get_or_reconcile_user_from_keycloak_claims(principal(),db)
 assert exc.value.status_code==409
 assert len(db.fetchrow.call_args_list)==2
