import pytest

from auth import router
from auth.models import BusinessRegisterRequest, ProviderRegisterRequest


@pytest.mark.asyncio
async def test_business_registration_cleans_up_keycloak_user_when_verify_email_fails(monkeypatch):
    deleted = []

    monkeypatch.setattr(router.keycloak_admin, "create_user", lambda **kwargs: "kc-user-1")

    def fail_send_verify_email(user_id):
        raise router.keycloak_admin.KeycloakAdminError(status_code=502, detail="smtp down")

    monkeypatch.setattr(router.keycloak_admin, "send_verify_email", fail_send_verify_email)
    monkeypatch.setattr(router.keycloak_admin, "delete_user", lambda user_id: deleted.append(user_id))

    req = BusinessRegisterRequest(
        email="new-business@example.com",
        password="DebugPass123!",
        company_name="Debug Business",
        company_code=None,
    )

    with pytest.raises(router.keycloak_admin.KeycloakAdminError):
        await router.register_business(req, None)

    assert deleted == ["kc-user-1"]


@pytest.mark.asyncio
async def test_provider_registration_cleans_up_keycloak_user_when_verify_email_fails(monkeypatch):
    deleted = []

    monkeypatch.setattr(router.keycloak_admin, "create_user", lambda **kwargs: "kc-user-2")

    def fail_send_verify_email(user_id):
        raise router.keycloak_admin.KeycloakAdminError(status_code=502, detail="smtp down")

    monkeypatch.setattr(router.keycloak_admin, "send_verify_email", fail_send_verify_email)
    monkeypatch.setattr(router.keycloak_admin, "delete_user", lambda user_id: deleted.append(user_id))

    req = ProviderRegisterRequest(
        email="new-provider@example.com",
        password="DebugPass123!",
        company_name="Debug Provider",
        company_code=None,
    )

    with pytest.raises(router.keycloak_admin.KeycloakAdminError):
        await router.register_provider(req, None)

    assert deleted == ["kc-user-2"]
