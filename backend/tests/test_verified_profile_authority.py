from uuid import UUID
from auth.router import _row_to_profile

def test_verified_profile_exposes_current_subject_and_effective_roles_to_client():
    row={'id':UUID(int=1),'keycloak_sub':UUID(int=2),'email':'synthetic@example.invalid','role':'provider','status':'active','is_owner':True,'tenant_id':UUID(int=1),'company_name':'Synthetic','company_code':None}
    result=_row_to_profile(row,realm_roles=['cb_admin'])
    assert result.id==str(UUID(int=1))
    assert result.keycloak_sub==str(UUID(int=2))
    assert result.realm_roles==['cb_admin']
    assert 'platform_admin' not in result.realm_roles
