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
    # Phase 2 — add stubs that point to NotImplementedError until schema is
    # finalised so the registry endpoint can advertise the full list while
    # /render-pdf returns 501 for not-yet-implemented types.
    "halal_policy": None,
    "has_manual": None,
    "halal_manual": None,
    "sop_raw_material_receiving": None,
    "sop_storage_segregation": None,
    "sop_production_operation": None,
    "sop_cleaning_sanitation": None,
    "sop_handling_nonconformances": None,
    "sop_complaint_recall": None,
    "internal_halal_committee": None,
    "ingredient_raw_material": None,
    "process_flow_chart": None,
}


def get_schema(doc_type: str) -> Optional[type[BaseModel]]:
    """Return the Pydantic model class for `doc_type`, or None if not yet implemented."""
    return SUPPORTED_DOC_TYPES.get(doc_type)
