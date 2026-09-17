import pytest
from pydantic import ValidationError

from auth.models import BusinessRegisterRequest, ProviderRegisterRequest


@pytest.mark.parametrize("model", [BusinessRegisterRequest, ProviderRegisterRequest])
def test_registration_password_requires_special_character(model):
    with pytest.raises(ValidationError) as exc:
        model(
            email="new-user@example.com",
            password="DebugPass123",
            company_name="Debug Company",
        )

    assert "Password must contain at least one special character" in str(exc.value)


@pytest.mark.parametrize("model", [BusinessRegisterRequest, ProviderRegisterRequest])
def test_registration_password_accepts_keycloak_policy_shape(model):
    req = model(
        email="new-user@example.com",
        password="DebugPass123!",
        company_name="Debug Company",
    )

    assert req.password == "DebugPass123!"
