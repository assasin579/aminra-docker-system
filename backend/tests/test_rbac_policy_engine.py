from __future__ import annotations

from uuid import uuid4

import pytest


def test_default_deny_unknown_role_and_action():
    from auth.policy_service import PolicyContext, PolicyService

    svc = PolicyService()
    provider = uuid4()
    user = uuid4()

    assert not svc.is_allowed(
        PolicyContext(role="mystery", canonical_user_id=user, canonical_tenant_id=provider),
        "submission.read",
        {"provider_id": provider},
    ).allowed
    assert not svc.is_allowed(
        PolicyContext(role="provider", is_owner=True, canonical_user_id=user, canonical_tenant_id=provider),
        "unknown.action",
        {"provider_id": provider},
    ).allowed


def test_missing_canonical_or_resource_scope_denies():
    from auth.policy_service import PolicyContext, PolicyService

    svc = PolicyService()
    assert not svc.is_allowed(
        PolicyContext(role="provider", is_owner=True, canonical_user_id=None, canonical_tenant_id=uuid4()),
        "certificate.issue",
        {"provider_id": uuid4()},
    ).allowed
    assert not svc.is_allowed(
        PolicyContext(role="provider", is_owner=True, canonical_user_id=uuid4(), canonical_tenant_id=uuid4()),
        "certificate.issue",
        {},
    ).allowed


def test_auditor_cannot_issue_certificate_but_can_perform_assigned_audit():
    from auth.policy_service import PolicyContext, PolicyService

    svc = PolicyService()
    auditor = uuid4()
    provider = uuid4()
    ctx = PolicyContext(role="provider", is_owner=False, canonical_user_id=auditor, canonical_tenant_id=provider)

    assert not svc.is_allowed(ctx, "certificate.issue", {"provider_id": provider}).allowed
    assert svc.is_allowed(ctx, "audit.perform", {"provider_id": provider, "auditor_id": auditor}).allowed


def test_business_cannot_access_provider_decision_queue():
    from auth.policy_service import PolicyContext, PolicyService

    svc = PolicyService()
    business = uuid4()
    ctx = PolicyContext(role="business", is_owner=True, canonical_user_id=uuid4(), canonical_tenant_id=business)

    assert not svc.is_allowed(ctx, "certification_decision.approve", {"business_tenant": business}).allowed
    assert not svc.is_allowed(ctx, "certification_decision.create", {"provider_id": uuid4()}).allowed
    assert svc.is_allowed(ctx, "submission.read", {"business_tenant": business}).allowed


def test_provider_owner_decision_and_certificate_scope():
    from auth.policy_service import PolicyContext, PolicyService

    svc = PolicyService()
    owner = uuid4()
    provider = uuid4()
    ctx = PolicyContext(role="provider", is_owner=True, canonical_user_id=owner, canonical_tenant_id=provider)

    assert svc.is_allowed(ctx, "certification_decision.create", {"provider_id": provider}).allowed
    assert svc.is_allowed(ctx, "certification_decision.approve", {"provider_id": provider}).allowed
    assert svc.is_allowed(ctx, "certificate.issue", {"provider_id": provider}).allowed
    assert not svc.is_allowed(ctx, "certificate.issue", {"provider_id": uuid4()}).allowed
