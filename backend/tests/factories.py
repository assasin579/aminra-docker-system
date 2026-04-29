"""Persona factories for AMINRA tests (Phase 0 baseline, 2026-04-29).

Builds *plain dicts* (not ORM rows) — the project uses asyncpg with raw SQL,
not SQLAlchemy. Factories produce JWT-payload-shaped dicts + DB-row-shaped
dicts. Tests then either:

  - POST against live `client` to create the user via `/auth/*/register`
  - Or insert directly into `users` table via the in-test DB connection

Six personas covering the multi-tenant role matrix:

  business_owner   — root of business tenant, can_edit / can_invite / etc.
  business_member  — invited by owner, scoped permissions
  provider_admin   — root of CB tenant (provider with is_owner=true)
  auditor          — invited by provider admin (is_owner=false)
  ihc_member       — Internal Halal Committee role (Tier-1 #2 module)
  admin            — platform admin (no tenant)

All factories accept overrides via kwargs. Email + tenant_id are uuid-derived
so 100 calls won't collide.

Usage:
    from tests.factories import BusinessOwnerFactory
    payload = BusinessOwnerFactory.build()  # dict
    # POST to /auth/business/register with payload
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import factory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Base ────────────────────────────────────────────────────────────────────


class _UserBase(factory.Factory):
    """Common user-row fields. Subclass to specialise per role."""

    class Meta:
        model = dict

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    email = factory.Sequence(lambda n: f"test-user-{n}-{uuid.uuid4().hex[:6]}@aminra.test")
    company_name = factory.Faker("company")
    company_code = factory.Sequence(lambda n: f"BIZ-{n:06d}")
    status = "active"
    deleted_at = None
    address = None
    phone = None
    representative_name = None
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)
    # Plaintext password for register-flow tests; never stored in DB
    password = factory.LazyAttribute(lambda _: f"TestPass2026-{uuid.uuid4().hex[:8]}")


# ── Personas ────────────────────────────────────────────────────────────────


class BusinessOwnerFactory(_UserBase):
    """Root of a business tenant. tenant_id == own id (auto-set on register)."""

    role = "business"
    is_owner = True
    tenant_id = factory.SelfAttribute("id")
    ihc_role = None
    department = None


class BusinessMemberFactory(_UserBase):
    """Invited by a business owner; tenant_id matches owner's."""

    role = "business"
    is_owner = False
    tenant_id = factory.LazyFunction(lambda: str(uuid.uuid4()))  # override w/ owner's id in tests
    ihc_role = None
    department = factory.Faker("job")


class ProviderAdminFactory(_UserBase):
    """Root of a certification body (provider) tenant. status starts pending
    until admin approves; tests usually flip to active before login.
    """

    role = "provider"
    is_owner = True
    tenant_id = factory.SelfAttribute("id")
    status = "active"  # tests usually want active; override to "pending" for approval flow tests


class AuditorFactory(_UserBase):
    """Auditor invited under a provider tenant. is_owner=False."""

    role = "provider"
    is_owner = False
    tenant_id = factory.LazyFunction(lambda: str(uuid.uuid4()))  # override w/ provider's id


class IHCMemberFactory(_UserBase):
    """Internal Halal Committee member of a business tenant. Tier-1 #22 module
    will reference this. Member of business tenant with `ihc_role` populated.
    """

    role = "business"
    is_owner = False
    tenant_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    ihc_role = factory.Iterator(["chair", "secretary", "shariah_advisor", "qa_lead", "production_lead"])
    department = "Internal Halal Committee"


class AdminFactory(_UserBase):
    """Platform admin — no tenant, role=admin. Used for cross-tenant ops."""

    role = "admin"
    is_owner = False
    tenant_id = None
    company_name = "AMINRA Platform"
    company_code = None


# ── JWT payload helpers ─────────────────────────────────────────────────────


def jwt_payload(user: dict) -> dict:
    """Shape a user dict into a JWT `sub` claim payload — what the get_current_user
    dependency expects after token decode.
    """
    return {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "status": user["status"],
        "is_owner": user["is_owner"],
        "tenant_id": user.get("tenant_id"),
    }


# ── Convenience helpers for tenant-scoped fixtures ──────────────────────────


def make_business_tenant(member_count: int = 0) -> dict:
    """Generate a business owner + N members sharing the same tenant_id.

    Returns: {"owner": dict, "members": [dict, ...]}
    """
    owner = BusinessOwnerFactory.build()
    members = [BusinessMemberFactory.build(tenant_id=owner["tenant_id"]) for _ in range(member_count)]
    return {"owner": owner, "members": members}


def make_provider_tenant(auditor_count: int = 0) -> dict:
    """Generate a provider admin + N auditors sharing the same tenant_id."""
    admin = ProviderAdminFactory.build()
    auditors = [AuditorFactory.build(tenant_id=admin["tenant_id"]) for _ in range(auditor_count)]
    return {"admin": admin, "auditors": auditors}


__all__ = [
    "BusinessOwnerFactory",
    "BusinessMemberFactory",
    "ProviderAdminFactory",
    "AuditorFactory",
    "IHCMemberFactory",
    "AdminFactory",
    "jwt_payload",
    "make_business_tenant",
    "make_provider_tenant",
]
