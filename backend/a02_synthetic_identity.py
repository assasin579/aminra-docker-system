"""Strict actor resolver for isolated A02 synthetic test harnesses only."""
from __future__ import annotations

import base64
import binascii
import json
import uuid
from typing import Any


def resolve_synthetic_actor(token: str, actors: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve a harness-only bearer marker to an explicit actor allowlist entry."""
    parts = token.split(".") if isinstance(token, str) else []
    if len(parts) != 3 or parts[2] != "synthetic-signature" or not parts[1]:
        raise ValueError("synthetic bearer marker required")
    try:
        raw = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(raw.encode("ascii")))
    except (ValueError, UnicodeError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("invalid synthetic bearer claims") from exc
    if not isinstance(claims, dict):
        raise ValueError("synthetic bearer claims must be an object")
    try:
        subject = uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("synthetic subject must be a canonical user UUID") from exc

    for actor in actors:
        try:
            actor_id = uuid.UUID(str(actor["id"]))
            tenant_id = uuid.UUID(str(actor["tenant_id"]))
            role = actor["role"]
            email = actor["email"]
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValueError("invalid synthetic actor mapping") from exc
        realm_roles = actor.get("realm_roles", [])
        if (
            role not in {"business", "provider", "admin"}
            or not isinstance(email, str)
            or not email
            or not isinstance(realm_roles, list)
            or any(not isinstance(item, str) for item in realm_roles)
        ):
            raise ValueError("invalid synthetic actor role or email")
        if actor_id == subject:
            return {
                "id": actor_id,
                "sub": str(actor_id),
                "tenant_id": tenant_id,
                "role": role,
                "email": email,
                "status": "active",
                "is_owner": True,
                "realm_roles": realm_roles,
                "_keycloak": True,
            }
    raise ValueError("synthetic subject is not allowlisted")
