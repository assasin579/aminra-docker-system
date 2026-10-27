import base64
import json
import uuid
from typing import Any

import pytest

from a02_synthetic_identity import resolve_synthetic_actor

BUSINESS_ID = "3a72ff20-f393-48cd-9ffc-87e4743d4c53"
BUSINESS_TENANT = "84a8a867-d66e-46b2-83a6-f90df9137ff6"
PROVIDER_ID = "c3250000-0000-4000-8000-000000000001"
PROVIDER_TENANT = "54180000-0000-4000-8000-000000000001"


def actor(user_id, tenant_id, role) -> dict[str, Any]:
    return {"id": user_id, "tenant_id": tenant_id, "role": role, "email": f"{role}@example.invalid"}


def token(subject):
    payload = base64.urlsafe_b64encode(json.dumps({"sub": subject}).encode()).decode().rstrip("=")
    return f"e30.{payload}.synthetic-signature"


def test_shared_harness_resolves_business_and_provider_by_canonical_subject():
    provider_actor = actor(PROVIDER_ID, PROVIDER_TENANT, "provider")
    provider_actor["realm_roles"] = ["platform_admin"]
    actors = [actor(BUSINESS_ID, BUSINESS_TENANT, "business"), provider_actor]

    business = resolve_synthetic_actor(token(BUSINESS_ID), actors)
    provider = resolve_synthetic_actor(token(PROVIDER_ID), actors)

    assert business["id"] == uuid.UUID(BUSINESS_ID)
    assert business["tenant_id"] == uuid.UUID(BUSINESS_TENANT)
    assert business["role"] == "business"
    assert provider["id"] == uuid.UUID(PROVIDER_ID)
    assert provider["tenant_id"] == uuid.UUID(PROVIDER_TENANT)
    assert provider["role"] == "provider"
    assert provider["realm_roles"] == ["platform_admin"]
    assert provider["_keycloak"] is True


def test_shared_harness_resolves_synthetic_platform_admin_capability_without_role_inference():
    admin_id = "c325bc0e-8e37-4f94-97a6-805111ac2d8f"
    admin = {"id": admin_id, "tenant_id": PROVIDER_TENANT, "role": "admin", "email": "admin@aminra.com", "realm_roles": ["platform_admin"]}

    resolved = resolve_synthetic_actor(token(admin_id), [admin])

    assert resolved["role"] == "admin"
    assert resolved["realm_roles"] == ["platform_admin"]
    assert resolved["_keycloak"] is True


@pytest.mark.parametrize("bad_token", ["", "bad.parts", "e30.e30.not-synthetic", "e30.%%%25.synthetic-signature"])
def test_shared_harness_rejects_malformed_or_non_synthetic_tokens(bad_token):
    with pytest.raises(ValueError):
        resolve_synthetic_actor(bad_token, [actor(BUSINESS_ID, BUSINESS_TENANT, "business")])


def test_shared_harness_rejects_unlisted_subject_and_invalid_actor_mapping():
    with pytest.raises(ValueError, match="not allowlisted"):
        resolve_synthetic_actor(token(str(uuid.uuid4())), [actor(BUSINESS_ID, BUSINESS_TENANT, "business")])
    with pytest.raises(ValueError):
        resolve_synthetic_actor(token(BUSINESS_ID), [actor(BUSINESS_ID, BUSINESS_TENANT, "platform_admin")])
    malformed = actor(PROVIDER_ID, PROVIDER_TENANT, "provider")
    malformed["realm_roles"] = "platform_admin"
    with pytest.raises(ValueError, match="invalid synthetic actor"):
        resolve_synthetic_actor(token(PROVIDER_ID), [malformed])
