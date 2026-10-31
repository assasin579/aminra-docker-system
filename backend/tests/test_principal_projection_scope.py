"""Current database authority must override stale mapper claims for every principal."""
from contextlib import asynccontextmanager
from uuid import UUID
import pytest
from fastapi import HTTPException
from auth.keycloak_validator import enrich_keycloak_claims

A,B,T=[UUID(int=n) for n in range(1,4)]
class Pool:
 def __init__(self,row):self.row=row;self.reads=0
 @asynccontextmanager
 async def acquire(self):yield self
 async def fetchrow(self,sql,*args):self.reads+=1;return self.row

def claims():return {'sub':str(A),'email':'scope@example.invalid','tenant_id':str(B),'is_owner':True,'status':'active','realm_access':{'roles':['business']}}
def row(**kw):return {'id':A,'keycloak_sub':A,'email':'scope@example.invalid','tenant_id':T,'is_owner':False,'status':'active','role':'business','company_name':'Synthetic',**kw}

@pytest.mark.asyncio
async def test_full_mapper_token_cannot_preserve_old_tenant_or_owner_authority():
 p=Pool(row());u=await enrich_keycloak_claims(claims(),p)
 assert p.reads>0
 assert u['tenant_id']==str(T) and u['is_owner'] is False and u['app_user_id']==str(A)

@pytest.mark.asyncio
async def test_suspended_account_cannot_use_an_older_active_mapper_token():
 with pytest.raises(HTTPException) as exc:await enrich_keycloak_claims(claims(),Pool(row(status='suspended')))
 assert exc.value.status_code==403

@pytest.mark.asyncio
async def test_same_email_bound_to_another_subject_is_not_an_account_transfer():
 with pytest.raises(HTTPException) as exc:await enrich_keycloak_claims(claims(),Pool(row(keycloak_sub=B)))
 assert exc.value.status_code==401

@pytest.mark.asyncio
async def test_missing_projection_does_not_grant_claimed_tenant_before_registration_reconciliation():
 u=await enrich_keycloak_claims(claims(),Pool(None))
 assert u['tenant_id'] is None


@pytest.mark.asyncio
async def test_identity_without_an_application_realm_role_cannot_bootstrap_business_authority():
 c=claims();c['realm_access']={'roles':['default-roles-aminra']}
 with pytest.raises(HTTPException) as exc:await enrich_keycloak_claims(c,Pool(None))
 assert exc.value.status_code==401

@pytest.mark.asyncio
async def test_email_change_cannot_hide_current_subject_suspension_or_recover_stale_owner_claims():
 class SubjectPool(Pool):
  async def fetchrow(self,sql,*args):
   self.reads+=1
   if 'keycloak_sub = $1' in sql:return row(email='renamed@example.invalid',status='suspended')
   return None
 with pytest.raises(HTTPException) as exc:await enrich_keycloak_claims(claims(),SubjectPool(None))
 assert exc.value.status_code==403

@pytest.mark.asyncio
async def test_subject_and_email_mapping_to_different_accounts_is_rejected():
 class ConflictPool(Pool):
  async def fetchrow(self,sql,*args):
   return row() if 'keycloak_sub = $1' in sql else row(id=B,keycloak_sub=B)
 with pytest.raises(HTTPException) as exc:await enrich_keycloak_claims(claims(),ConflictPool(None))
 assert exc.value.status_code==401
