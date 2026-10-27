import pytest
from fastapi import HTTPException

from auth.requirements_authorization import require_platform_admin_capability


def test_verified_keycloak_platform_admin_capability_is_required():
    user = {"_keycloak": True, "realm_roles": ["platform_admin"], "role": "provider", "sub": "kc-admin"}
    assert require_platform_admin_capability(user) is user


@pytest.mark.parametrize("user", [
    {"_keycloak": True, "realm_roles": ["cb_admin"], "role": "provider"},
    {"_keycloak": True, "realm_roles": ["auditor"], "role": "provider"},
    {"_keycloak": True, "realm_roles": ["business"], "role": "business"},
    {"_keycloak": True, "realm_roles": [], "role": "platform_admin"},
    {"_keycloak": False, "realm_roles": ["platform_admin"], "role": "platform_admin"},
    {"role": "platform_admin"},
    {},
])
def test_missing_or_non_platform_capability_is_denied(user):
    with pytest.raises(HTTPException) as exc:
        require_platform_admin_capability(user)
    assert exc.value.status_code == 403
