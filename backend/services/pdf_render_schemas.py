"""Pydantic input schemas for /api/templates/{doc_type}/render-pdf.

One model per doc_type. The router selects the model from `_REGISTRY` and
calls `Model.model_validate(body['data'])` before passing to the renderer,
so any field-level constraint (max_length, regex, range) is enforced at
the API boundary — never in the template.

Threat-model R2 / R3: every str MUST have max_length; URL/email-style
fields MUST be typed (HttpUrl, EmailStr) — no free-form strings that
could land inside `<img src>` or `<a href>`.

Phase 1 ships only `CompanyProfileData`; Phase 2 adds the other 12
doc_types reusing the same field validators where shape overlaps.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ── Shared sub-models ───────────────────────────────────────────────────────


class HalalResponsiblePerson(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=100)
    title: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None


class CompanyProduct(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    annual_output: Optional[str] = Field(None, max_length=80)


# ── company_profile ────────────────────────────────────────────────────────


_VN_TAX_CODE_RE = r"^[0-9]{10}(-[0-9]{3})?$"


class CompanyProfileData(BaseModel):
    """Input shape for `company_profile` template render.

    Only `business_name` and `issued_date` are required so the renderer
    can degrade gracefully when the frontend has a sparse CompanyProfile
    (initial onboarding) — the template inserts "—" for missing fields.
    Strict shapes (tax_code regex, year ranges) still apply when present.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Identity
    business_name: str = Field(..., min_length=1, max_length=200)
    business_name_en: Optional[str] = Field(None, max_length=200)
    tax_code: Optional[str] = Field(None, pattern=_VN_TAX_CODE_RE)
    address: Optional[str] = Field(None, max_length=300)
    factory_address: Optional[str] = Field(None, max_length=300)
    representative: Optional[str] = Field(None, max_length=100)

    # Scale
    founded_year: Optional[int] = Field(None, ge=1900, le=2100)
    employee_count: Optional[int] = Field(None, ge=0, le=100_000)
    charter_capital: Optional[str] = Field(None, max_length=100)

    # Contact (typed fields → no free-form URL injection)
    phone: Optional[str] = Field(None, max_length=30, pattern=r"^[0-9+\-\s().]{6,30}$")
    email: Optional[EmailStr] = None
    website: Optional[str] = Field(
        None, max_length=200,
        # Plain string — rendered as text only, never as <a href>; we DO NOT use HttpUrl
        # because templates must not turn it into a clickable link (CSP + threat-model R3).
    )

    # Halal
    halal_commitment: Optional[str] = Field(None, max_length=2000)
    halal_responsible_person: Optional[HalalResponsiblePerson] = None

    # Activity
    business_activities: List[str] = Field(default_factory=list, max_length=50)
    products: List[CompanyProduct] = Field(default_factory=list, max_length=100)

    # Render
    issued_date: date

    @field_validator("business_activities")
    @classmethod
    def _check_activity_length(cls, v: List[str]) -> List[str]:
        for a in v:
            if len(a) > 200:
                raise ValueError("each business activity must be ≤ 200 chars")
        return v


# ── Registry of supported doc_types (Phase 1: only company_profile) ────────


# ── SOP (shared by 6 sop_* doc_types) ───────────────────────────────────────


class ResponsibilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: str = Field(..., min_length=1, max_length=120)
    duties: str = Field(..., min_length=1, max_length=600)


class DefinitionRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    term: str = Field(..., min_length=1, max_length=120)
    definition: str = Field(..., min_length=1, max_length=600)


class ProcedureStep(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    step_no: int = Field(..., ge=1, le=999)
    action: str = Field(..., min_length=1, max_length=600)
    responsible_role: Optional[str] = Field(None, max_length=120)
    records: Optional[str] = Field(None, max_length=200)
    criteria: Optional[str] = Field(None, max_length=300)


class SopData(BaseModel):
    """Shared input for every `sop_*` doc_type.

    Per-variant differences (title, scope defaults, procedure step examples)
    come from admin_templates/<sop_type>.json cfg, not from this schema.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Identity
    business_name: str = Field(..., min_length=1, max_length=200)
    sop_id: Optional[str] = Field(None, max_length=40, pattern=r"^[A-Z0-9\-]+$")
    title: Optional[str] = Field(None, max_length=200)
    version: Optional[str] = Field(None, max_length=20)

    # Body
    purpose: Optional[str] = Field(None, max_length=1500)
    scope: Optional[str] = Field(None, max_length=1500)
    responsibilities: List[ResponsibilityRow] = Field(default_factory=list, max_length=20)
    references: List[str] = Field(default_factory=list, max_length=30)
    definitions: List[DefinitionRow] = Field(default_factory=list, max_length=30)
    procedure_steps: List[ProcedureStep] = Field(default_factory=list, max_length=50)
    records: List[str] = Field(default_factory=list, max_length=20)
    appendices: List[str] = Field(default_factory=list, max_length=10)

    # Approval / lifecycle
    effective_date: date
    review_date: Optional[date] = None
    approved_by: Optional[str] = Field(None, max_length=200)

    # Render
    issued_date: date


# ── Halal Policy + HAS Manual (Group 2 — share committee + signatory shapes) ─


class HalalCommitteeMember(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., min_length=1, max_length=120)              # Chairperson, Secretary, Member
    department: Optional[str] = Field(None, max_length=120)
    appointed_date: Optional[date] = None


class Signatory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=1, max_length=120)
    signature_date: Optional[date] = None


class CommitmentClause(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    clause_no: int = Field(..., ge=1, le=30)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=2000)


class HalalPolicyData(BaseModel):
    """Halal Policy Statement — official commitment from leadership.

    Distinct from SopData by intent: this is the company-level pledge,
    not an operational procedure. Renders as a cover + numbered clauses
    + signatory block — feels like an internal regulation.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    business_name: str = Field(..., min_length=1, max_length=200)
    policy_id: Optional[str] = Field(None, max_length=40, pattern=r"^[A-Z0-9\-]+$")
    version: Optional[str] = Field(None, max_length=20)

    mission_statement: Optional[str] = Field(None, max_length=1500)
    vision_statement: Optional[str] = Field(None, max_length=1500)

    halal_commitment: str = Field(..., min_length=1, max_length=2500)         # marquee pull-quote
    scope_of_application: Optional[str] = Field(None, max_length=2000)

    commitment_clauses: List[CommitmentClause] = Field(default_factory=list, max_length=30)
    halal_committee: List[HalalCommitteeMember] = Field(default_factory=list, max_length=20)
    references: List[str] = Field(default_factory=list, max_length=30)

    effective_date: date
    review_date: Optional[date] = None
    signatories: List[Signatory] = Field(default_factory=list, max_length=5)

    issued_date: date


class HasChapter(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    chapter_no: int = Field(..., ge=1, le=30)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=4000)
    cross_refs: List[str] = Field(default_factory=list, max_length=20)        # SOP-XYZ-NNN


class AbbreviationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    abbr: str = Field(..., min_length=1, max_length=20)
    meaning: str = Field(..., min_length=1, max_length=300)


class RevisionHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: str = Field(..., max_length=20)
    revision_date: date
    change_summary: str = Field(..., min_length=1, max_length=600)
    approver: str = Field(..., min_length=1, max_length=120)


class HasManualData(BaseModel):
    """HAS (Halal Assurance System) Manual — top-level operating manual.

    Aliased by both `has_manual` and `halal_manual` doc_types. Structured
    by chapters; each chapter cross-references the SOPs that implement it
    so a JAKIM auditor can navigate the document tree top-down.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    business_name: str = Field(..., min_length=1, max_length=200)
    manual_id: Optional[str] = Field(None, max_length=40, pattern=r"^[A-Z0-9\-]+$")
    version: Optional[str] = Field(None, max_length=20)

    introduction: Optional[str] = Field(None, max_length=2500)
    abbreviations: List[AbbreviationEntry] = Field(default_factory=list, max_length=40)

    halal_policy_summary: Optional[str] = Field(None, max_length=2500)
    halal_committee: List[HalalCommitteeMember] = Field(default_factory=list, max_length=20)

    chapters: List[HasChapter] = Field(default_factory=list, max_length=30)

    governing_documents: List[str] = Field(default_factory=list, max_length=30)
    referenced_sops: List[str] = Field(default_factory=list, max_length=30)

    revision_history: List[RevisionHistoryEntry] = Field(default_factory=list, max_length=20)

    effective_date: date
    review_date: Optional[date] = None
    signatories: List[Signatory] = Field(default_factory=list, max_length=5)

    issued_date: date


# ── Style guide (kitchen sink — internal) ───────────────────────────────────


class StyleGuideData(BaseModel):
    """Trivial schema for the kitchen-sink style guide template.

    The style guide doesn't accept user input — it renders fixture data
    only — but having a model lets it pass through the standard router
    validation pipeline without a special-case branch.
    """
    model_config = ConfigDict(extra="allow")
    last_updated: Optional[str] = Field(None, max_length=20)


SUPPORTED_DOC_TYPES = {
    "_style_guide": StyleGuideData,
    "company_profile": CompanyProfileData,

    # All 6 SOP variants share SopData — they differ only in admin cfg
    # (title, scope_default, procedure step examples).
    "sop_raw_material_receiving": SopData,
    "sop_storage_segregation": SopData,
    "sop_production_operation": SopData,
    "sop_cleaning_sanitation": SopData,
    "sop_handling_nonconformances": SopData,
    "sop_complaint_recall": SopData,

    # Group 2 — Halal Policy + HAS Manual (halal_manual aliases has_manual)
    "halal_policy": HalalPolicyData,
    "has_manual": HasManualData,
    "halal_manual": HasManualData,

    # Phase 2 remaining (Group 3-5)
    "internal_halal_committee": None,
    "ingredient_raw_material": None,
    "process_flow_chart": None,
}


def get_schema(doc_type: str) -> Optional[type[BaseModel]]:
    """Return the Pydantic model class for `doc_type`, or None if not yet implemented."""
    return SUPPORTED_DOC_TYPES.get(doc_type)
