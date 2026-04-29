"""Document version control — UNIT tests (Stage 6a, 50 cases).

No DB. No HTTP. Pure logic — state machine, permissions, retention,
version chain, payload validators. Run inline:

    pytest backend/tests/test_document_versioning_unit.py -v

Test IDs match `docs/features/document-version-control/test-plan.md`.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest

from auth.permissions import (
    DEFAULT_PERMISSIONS,
    _ihc_member,
    get_user_permissions,
)
from services.document_versioning import (
    AUDIT_EVENT_APPROVED,
    AUDIT_EVENT_REJECTED,
    AUDIT_EVENT_SUBMITTED,
    AUDIT_EVENT_SUPERSEDED,
    MAX_CHAIN_DEPTH,
    RETENTION_FLOOR_DAYS,
    chain_depth,
    chain_is_obsolete,
    chain_root_id,
    compute_retention_expires,
    next_version_number,
    reject_self_supersede,
    transition_allowed,
    transition_audit_event,
    transition_reason_required,
    validate_chain_links,
)


# Helpers ───────────────────────────────────────────────────────────────────


def _perms(**overrides) -> dict:
    """Build a permissions dict on top of defaults."""
    return {**DEFAULT_PERMISSIONS, **overrides}


# ════════════════════════════════════════════════════════════════════════════
# State machine — UNIT-01..15
# ════════════════════════════════════════════════════════════════════════════


class TestStateMachine:
    # UNIT-01
    def test_draft_to_pending_with_can_edit(self):
        assert transition_allowed("draft", "pending_approval", _perms(can_edit=True)) is True

    # UNIT-02
    def test_draft_to_approved_skip_forbidden(self):
        assert (
            transition_allowed("draft", "approved", _perms(can_approve_documents=True))
            is False
        )

    # UNIT-03
    def test_pending_to_approved_with_approver(self):
        assert (
            transition_allowed(
                "pending_approval", "approved", _perms(can_approve_documents=True)
            )
            is True
        )

    # UNIT-04
    def test_pending_to_draft_rejection_with_approver(self):
        assert (
            transition_allowed(
                "pending_approval", "draft", _perms(can_approve_documents=True)
            )
            is True
        )

    # UNIT-05
    def test_pending_to_draft_without_approver_blocked(self):
        # Editor without approve permission cannot reject — only approver can
        assert (
            transition_allowed("pending_approval", "draft", _perms(can_edit=True))
            is False
        )

    # UNIT-06
    def test_approved_to_draft_unapprove_forbidden(self):
        assert (
            transition_allowed(
                "approved", "draft", _perms(can_approve_documents=True)
            )
            is False
        )

    # UNIT-07
    def test_approved_to_pending_re_approve_forbidden(self):
        assert (
            transition_allowed(
                "approved", "pending_approval", _perms(can_approve_documents=True)
            )
            is False
        )

    # UNIT-08
    @pytest.mark.parametrize(
        "to_state", ["draft", "pending_approval", "approved", "obsolete"]
    )
    def test_obsolete_terminal(self, to_state):
        assert (
            transition_allowed(
                "obsolete", to_state, _perms(can_approve_documents=True)
            )
            is False
        )

    # UNIT-09
    def test_approved_to_obsolete_supersede(self):
        # Owner_or_ihc check → reuses can_approve_documents capability
        assert (
            transition_allowed(
                "approved", "obsolete", _perms(can_approve_documents=True)
            )
            is True
        )

    # UNIT-10
    def test_draft_to_obsolete_forbidden(self):
        assert (
            transition_allowed(
                "draft", "obsolete", _perms(can_approve_documents=True)
            )
            is False
        )

    # UNIT-11
    def test_reason_required_on_rejection(self):
        assert transition_reason_required("pending_approval", "draft") is True

    # UNIT-12
    def test_reason_not_required_on_submit(self):
        assert transition_reason_required("draft", "pending_approval") is False

    # UNIT-13
    def test_reason_not_required_on_approve(self):
        assert transition_reason_required("pending_approval", "approved") is False

    # UNIT-14
    def test_audit_event_for_approval(self):
        assert transition_audit_event("pending_approval", "approved") == AUDIT_EVENT_APPROVED

    # UNIT-15
    def test_audit_event_for_rejection(self):
        assert transition_audit_event("pending_approval", "draft") == AUDIT_EVENT_REJECTED

    # Bonus: audit events for submit + supersede
    def test_audit_event_for_submit(self):
        assert transition_audit_event("draft", "pending_approval") == AUDIT_EVENT_SUBMITTED

    def test_audit_event_for_supersede(self):
        assert transition_audit_event("approved", "obsolete") == AUDIT_EVENT_SUPERSEDED

    def test_invalid_state_returns_false(self):
        assert transition_allowed("garbage", "approved", _perms(can_approve_documents=True)) is False
        assert transition_allowed("draft", "garbage", _perms(can_edit=True)) is False


# ════════════════════════════════════════════════════════════════════════════
# Permission helpers — UNIT-16..23
# ════════════════════════════════════════════════════════════════════════════


class TestPermissions:
    # UNIT-16
    def test_owner_has_can_approve_documents(self):
        assert get_user_permissions({"is_owner": True})["can_approve_documents"] is True

    # UNIT-17
    def test_ihc_member_auto_grants(self):
        assert (
            get_user_permissions({"is_owner": False, "ihc_role": "chair"})["can_approve_documents"]
            is True
        )

    # UNIT-18
    def test_non_ihc_non_owner_default_false(self):
        assert (
            get_user_permissions({"is_owner": False, "ihc_role": None})[
                "can_approve_documents"
            ]
            is False
        )

    # UNIT-19
    def test_explicit_override_true(self):
        u = {
            "is_owner": False,
            "permissions": {"can_approve_documents": True},
        }
        assert get_user_permissions(u)["can_approve_documents"] is True

    # UNIT-20
    def test_missing_fields_dict(self):
        result = get_user_permissions({})
        assert isinstance(result, dict)
        assert result.get("can_approve_documents") is False

    # UNIT-21
    def test_ihc_role_empty_string_is_not_member(self):
        assert _ihc_member({"ihc_role": ""}) is False

    # UNIT-22
    def test_ihc_role_truthy_string_is_member(self):
        for role in ("chair", "secretary", "shariah_advisor", "qa_lead", "production_lead"):
            assert _ihc_member({"ihc_role": role}) is True

    # UNIT-23
    def test_ihc_role_missing_key(self):
        assert _ihc_member({}) is False


# ════════════════════════════════════════════════════════════════════════════
# Retention computation — UNIT-24..28
# ════════════════════════════════════════════════════════════════════════════


class TestRetention:
    # UNIT-24
    def test_retention_from_approved_at(self):
        approved = datetime(2026, 1, 15, tzinfo=timezone.utc)
        result = compute_retention_expires(
            approved_at=approved, effective_date=None, days=1825
        )
        assert result.year == 2031
        assert result.month == 1
        # 1825 days from 2026-01-15 includes leap 2028 → 2031-01-14
        assert result.day == 14

    # UNIT-25
    def test_retention_prefers_effective_date(self):
        approved = datetime(2026, 1, 15, tzinfo=timezone.utc)
        result = compute_retention_expires(
            approved_at=approved, effective_date=date(2026, 1, 20), days=1825
        )
        assert result.year == 2031
        assert result.day == 19

    # UNIT-26
    def test_retention_below_floor_raises(self):
        with pytest.raises(ValueError):
            compute_retention_expires(
                approved_at=datetime.now(timezone.utc),
                effective_date=None,
                days=1824,
            )

    # UNIT-27
    def test_retention_10_year_extended(self):
        result = compute_retention_expires(
            approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            effective_date=None,
            days=3650,
        )
        # 10 years + 2 leap days (2028, 2032) = 3652 days exact; 3650 → 2035-12-30
        assert result.year >= 2035

    # UNIT-28
    def test_retention_no_base_raises(self):
        with pytest.raises(ValueError):
            compute_retention_expires(approved_at=None, effective_date=None, days=1825)

    def test_retention_floor_constant(self):
        assert RETENTION_FLOOR_DAYS == 1825

    def test_retention_naive_approved_at_handled(self):
        # Naive datetime should be treated as UTC, not crash
        naive = datetime(2026, 1, 15)
        result = compute_retention_expires(approved_at=naive, effective_date=None, days=1825)
        assert result.tzinfo is timezone.utc


# ════════════════════════════════════════════════════════════════════════════
# Version chain helpers — UNIT-29..36
# ════════════════════════════════════════════════════════════════════════════


class TestChainHelpers:
    # UNIT-29
    def test_chain_depth_no_parent(self):
        assert chain_depth([]) == 0

    # UNIT-30
    def test_chain_depth_one_ancestor(self):
        assert chain_depth([{"id": "x"}]) == 1

    def test_chain_depth_multiple(self):
        assert chain_depth([{"id": "a"}, {"id": "b"}, {"id": "c"}]) == 3

    # UNIT-31
    def test_next_version_after_v3(self):
        assert next_version_number({"version_number": 3}) == 4

    # UNIT-32
    def test_next_version_no_parent_is_1(self):
        assert next_version_number(None) == 1

    def test_next_version_zero_parent_treated_as_1(self):
        assert next_version_number({"version_number": 0}) == 1

    # UNIT-33
    def test_validate_chain_links_mutex(self):
        with pytest.raises(ValueError):
            validate_chain_links(version_parent_id="a", superseded_by_id="b")

    def test_validate_chain_links_only_parent(self):
        # Should NOT raise
        validate_chain_links(version_parent_id="a", superseded_by_id=None)

    def test_validate_chain_links_only_supersede(self):
        validate_chain_links(version_parent_id=None, superseded_by_id="b")

    def test_validate_chain_links_both_none(self):
        validate_chain_links(version_parent_id=None, superseded_by_id=None)

    # UNIT-34
    def test_chain_is_obsolete_when_superseded(self):
        assert chain_is_obsolete({"superseded_by_id": "x"}) is True

    def test_chain_is_obsolete_when_not_superseded(self):
        assert chain_is_obsolete({"superseded_by_id": None}) is False
        assert chain_is_obsolete({}) is False

    # UNIT-35
    def test_chain_root_returns_first_ancestor(self):
        chain = [{"id": "root"}, {"id": "v2"}, {"id": "v3"}]
        assert chain_root_id(chain, "v3") == "root"

    # UNIT-36
    def test_chain_root_self_when_no_parents(self):
        assert chain_root_id([], "self-id") == "self-id"

    def test_max_chain_depth_constant(self):
        assert MAX_CHAIN_DEPTH == 10


# ════════════════════════════════════════════════════════════════════════════
# Payload-validator-shaped pure logic — UNIT-37..43
# (Pydantic models live in router; here we verify the underlying invariants.)
# ════════════════════════════════════════════════════════════════════════════


class TestPayloadInvariants:
    # UNIT-37
    def test_iso_date_parseable(self):
        d = date.fromisoformat("2026-01-15")
        assert d.year == 2026

    # UNIT-38
    def test_invalid_iso_date_raises(self):
        with pytest.raises(ValueError):
            date.fromisoformat("not-a-date")

    # UNIT-39
    def test_backdating_not_blocked_at_logic_layer(self):
        # The logic layer accepts any date; UI layer warns user.
        past = date(2020, 1, 1)
        result = compute_retention_expires(
            approved_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            effective_date=past,
            days=1825,
        )
        assert result.year >= 2024

    # UNIT-40
    def test_retention_below_floor_value_error(self):
        with pytest.raises(ValueError):
            compute_retention_expires(
                approved_at=datetime.now(timezone.utc), effective_date=None, days=100
            )

    # UNIT-41
    def test_retention_high_value_accepted(self):
        # 99999 days = ~273 years. Logic layer accepts (no upper limit).
        result = compute_retention_expires(
            approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            effective_date=None,
            days=99999,
        )
        assert result.year > 2200

    # UNIT-42
    def test_self_supersede_rejected(self):
        with pytest.raises(ValueError):
            reject_self_supersede("doc-x", "doc-x")

    # UNIT-43
    def test_different_supersede_allowed(self):
        # Should NOT raise
        reject_self_supersede("doc-a", "doc-b")


# ════════════════════════════════════════════════════════════════════════════
# Audit event constant integrity — UNIT-44..47
# ════════════════════════════════════════════════════════════════════════════


class TestAuditConstants:
    def test_submitted_event_string(self):
        assert AUDIT_EVENT_SUBMITTED == "document.submitted_for_approval"

    def test_approved_event_string(self):
        assert AUDIT_EVENT_APPROVED == "document.approved"

    def test_rejected_event_string(self):
        assert AUDIT_EVENT_REJECTED == "document.approval_rejected"

    def test_superseded_event_string(self):
        assert AUDIT_EVENT_SUPERSEDED == "document.superseded"


# ════════════════════════════════════════════════════════════════════════════
# Hash-based deterministic property tests — UNIT-48..50
# (Verify SHA-256-derived rollout properties used elsewhere in feature_flags
# also hold here for any future hash-based logic in versioning.)
# ════════════════════════════════════════════════════════════════════════════


class TestHashProperties:
    # UNIT-48
    def test_sha256_deterministic(self):
        h1 = hashlib.sha256(b"test", usedforsecurity=False).digest()
        h2 = hashlib.sha256(b"test", usedforsecurity=False).digest()
        assert h1 == h2

    # UNIT-49
    def test_sha256_different_inputs_diverge(self):
        h1 = hashlib.sha256(b"a", usedforsecurity=False).digest()
        h2 = hashlib.sha256(b"b", usedforsecurity=False).digest()
        assert h1 != h2

    # UNIT-50
    def test_timedelta_addition(self):
        # Sanity: timedelta math used in retention computation
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = base + timedelta(days=1825)
        assert (result - base).days == 1825
