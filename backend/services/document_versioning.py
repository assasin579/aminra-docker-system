"""Document version control state machine + helpers (Tier-1 #24).

Pure logic — no DB, no FastAPI. Imported by `auth/document_router.py` for
endpoint handlers and `tests/test_document_versioning_unit.py` for UNIT
test coverage. Spec: `docs/features/document-version-control/spec.md`.

State machine:
   draft ─submit→ pending_approval ─approve→ approved ─supersede→ obsolete
                       │             ─reject→ draft
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

# ── Constants ───────────────────────────────────────────────────────────────

VALID_STATES: tuple[str, ...] = ("draft", "pending_approval", "approved", "obsolete")

# Minimum retention per JAKIM/BPJPH audit-grade compliance (5 years)
RETENTION_FLOOR_DAYS = 1825

# Maximum recursion depth for /versions to defend against malformed chains
MAX_CHAIN_DEPTH = 10

# Audit log event names emitted on each transition
AUDIT_EVENT_SUBMITTED = "document.submitted_for_approval"
AUDIT_EVENT_APPROVED = "document.approved"
AUDIT_EVENT_REJECTED = "document.approval_rejected"
AUDIT_EVENT_SUPERSEDED = "document.superseded"

# Transitions that require a textual reason in metadata
TRANSITIONS_REQUIRING_REASON: frozenset[tuple[str, str]] = frozenset(
    {
        ("pending_approval", "draft"),  # rejection
    }
)


# ── State machine ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TransitionRule:
    from_state: str
    to_state: str
    requires: str  # 'can_edit' | 'can_approve_documents' | 'owner_or_ihc'
    audit_event: str


# Authoritative table of allowed transitions. Anything NOT here is forbidden.
ALLOWED_TRANSITIONS: tuple[TransitionRule, ...] = (
    TransitionRule("draft", "pending_approval", "can_edit", AUDIT_EVENT_SUBMITTED),
    TransitionRule("pending_approval", "approved", "can_approve_documents", AUDIT_EVENT_APPROVED),
    TransitionRule("pending_approval", "draft", "can_approve_documents", AUDIT_EVENT_REJECTED),
    TransitionRule("approved", "obsolete", "owner_or_ihc", AUDIT_EVENT_SUPERSEDED),
)


def transition_allowed(from_state: str, to_state: str, perms: dict) -> bool:
    """True iff the (from, to) pair exists in ALLOWED_TRANSITIONS AND `perms`
    grants the required capability. Closed-default: unknown states return False.

    `perms` is the user-permission dict from `get_user_permissions()`.
    """
    if from_state not in VALID_STATES or to_state not in VALID_STATES:
        return False
    rule = _find_rule(from_state, to_state)
    if rule is None:
        return False
    return _has_capability(perms, rule.requires)


def transition_audit_event(from_state: str, to_state: str) -> Optional[str]:
    """Audit event name for a valid transition; None for invalid pair."""
    rule = _find_rule(from_state, to_state)
    return rule.audit_event if rule else None


def transition_reason_required(from_state: str, to_state: str) -> bool:
    """True if the API caller must supply a reason in body."""
    return (from_state, to_state) in TRANSITIONS_REQUIRING_REASON


def _find_rule(from_state: str, to_state: str) -> Optional[TransitionRule]:
    for rule in ALLOWED_TRANSITIONS:
        if rule.from_state == from_state and rule.to_state == to_state:
            return rule
    return None


def _has_capability(perms: dict, requires: str) -> bool:
    if requires == "can_edit":
        return bool(perms.get("can_edit"))
    if requires == "can_approve_documents":
        return bool(perms.get("can_approve_documents"))
    if requires == "owner_or_ihc":
        # Owner always has can_approve_documents True; IHC also gets True via
        # auto-grant. So checking that flag covers both.
        return bool(perms.get("can_approve_documents"))
    return False


# ── Retention computation ───────────────────────────────────────────────────


def compute_retention_expires(
    *,
    approved_at: Optional[datetime],
    effective_date: Optional[date],
    days: int,
) -> datetime:
    """Compute when retention period expires.

    Base date preference: effective_date (operational truth) > approved_at.
    Raises ValueError if neither is provided or if days < floor.
    """
    if days < RETENTION_FLOOR_DAYS:
        raise ValueError(f"retention_period_days must be >= {RETENTION_FLOOR_DAYS} (5 years, JAKIM audit-grade)")
    if effective_date is None and approved_at is None:
        raise ValueError("retention requires either effective_date or approved_at as base")

    if effective_date is not None:
        base = datetime.combine(effective_date, datetime.min.time(), tzinfo=timezone.utc)
    else:
        base = approved_at if approved_at.tzinfo else approved_at.replace(tzinfo=timezone.utc)

    return base + timedelta(days=days)


# ── Version chain helpers ───────────────────────────────────────────────────


def chain_depth(parent_chain: Iterable[dict]) -> int:
    """Depth = number of ancestor docs above current. parent_chain is the
    list returned by recursive query, oldest-first."""
    return len(list(parent_chain))


def next_version_number(parent: Optional[dict]) -> int:
    """Compute version_number for a child of parent. None parent → 1."""
    if parent is None:
        return 1
    current = parent.get("version_number") or 0
    return current + 1


def validate_chain_links(*, version_parent_id: Optional[str], superseded_by_id: Optional[str]) -> None:
    """Constraints on chain pointers at INSERT time:
    - parent and supersede must NOT both be set on the same row
      (a doc is either a NEW version of something, OR an obsolete root,
      not both during creation).
    Raises ValueError.
    """
    if version_parent_id is not None and superseded_by_id is not None:
        raise ValueError("version_parent_id and superseded_by_id are mutually exclusive on insert")


def chain_is_obsolete(doc: dict) -> bool:
    """Doc is obsolete iff it has been superseded."""
    return bool(doc.get("superseded_by_id"))


def chain_root_id(parent_chain: Iterable[dict], current_id: str) -> str:
    """Root = oldest ancestor. Returns own id if no ancestors."""
    chain = list(parent_chain)
    if not chain:
        return current_id
    return chain[0].get("id") or current_id


# ── Self-link guard (separate so router can return 422 with friendly msg) ──


def reject_self_supersede(current_id: str, new_document_id: str) -> None:
    """Cannot supersede a doc with itself."""
    if current_id == new_document_id:
        raise ValueError("cannot supersede a document with itself")


__all__ = [
    "VALID_STATES",
    "RETENTION_FLOOR_DAYS",
    "MAX_CHAIN_DEPTH",
    "AUDIT_EVENT_SUBMITTED",
    "AUDIT_EVENT_APPROVED",
    "AUDIT_EVENT_REJECTED",
    "AUDIT_EVENT_SUPERSEDED",
    "transition_allowed",
    "transition_audit_event",
    "transition_reason_required",
    "compute_retention_expires",
    "chain_depth",
    "next_version_number",
    "validate_chain_links",
    "chain_is_obsolete",
    "chain_root_id",
    "reject_self_supersede",
]
