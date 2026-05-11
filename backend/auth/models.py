import re

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime

MAX_MEMBERS = 7


# ── Request models ─────────────────────────────────────────────────────────────


class BusinessRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    # min_length=1: empty name was being accepted (UAT-A-23 gap)
    # max_length=255: oversize input was crashing backend with 500 (UAT-A-22 DoS gap)
    company_name: str = Field(..., min_length=1, max_length=255)
    company_code: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


class ProviderRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    company_name: str = Field(..., min_length=1, max_length=255)
    company_code: Optional[str] = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 10:
            raise ValueError("Password must be at least 10 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = None  # 'business' or 'provider' — for per-role email lookup


class InviteMemberRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str  # Stored in company_name for the member row
    ihc_role: str = ""  # Chairman, Halal Executive, Dept Head, etc.
    department: str = ""  # Bộ phận / phòng ban


# ── Response models ────────────────────────────────────────────────────────────


class UserProfile(BaseModel):
    id: str
    email: str
    role: str
    status: str
    company_name: str
    company_code: Optional[str]
    is_owner: bool
    tenant_id: Optional[str]
    member_count: Optional[int] = None  # filled for business owners
    address: Optional[str] = None
    phone: Optional[str] = None
    representative_name: Optional[str] = None
    permissions: Optional[dict] = None
    industry_schema_id: Optional[str] = None
    industry_schema_code: Optional[str] = None
    # Phase 1 rich-data fields (Section: Halal Compliance + Products + IHC + Production)
    founded_year: Optional[int] = None
    halal_commitment_statement: Optional[str] = None
    total_employees: Optional[int] = None
    najis_handling_policy: Optional[str] = None
    cross_contamination_controls: Optional[str] = None
    product_categories: Optional[str] = None
    primary_suppliers: Optional[str] = None
    ingredient_origin_countries: Optional[str] = None
    packaging_materials_brief: Optional[str] = None
    ihc_chairman_name: Optional[str] = None
    ihc_chairman_title: Optional[str] = None
    ihc_inception_date: Optional[str] = None  # ISO date string in API
    ihc_members_brief: Optional[str] = None
    ihc_meeting_frequency: Optional[str] = None
    production_capacity_brief: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CompanyProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    representative_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    manager_name: Optional[str] = None
    # Phase 1 rich-data fields
    founded_year: Optional[int] = None
    halal_commitment_statement: Optional[str] = None
    total_employees: Optional[int] = None
    najis_handling_policy: Optional[str] = None
    cross_contamination_controls: Optional[str] = None
    product_categories: Optional[str] = None
    primary_suppliers: Optional[str] = None
    ingredient_origin_countries: Optional[str] = None
    packaging_materials_brief: Optional[str] = None
    ihc_chairman_name: Optional[str] = None
    ihc_chairman_title: Optional[str] = None
    ihc_inception_date: Optional[str] = None  # ISO date "YYYY-MM-DD"
    ihc_members_brief: Optional[str] = None
    ihc_meeting_frequency: Optional[str] = None
    production_capacity_brief: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserProfile


class RegisterBusinessResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserProfile


class RegisterProviderResponse(BaseModel):
    user_id: str
    email: str
    status: str
    message: str


class UpdateMemberRequest(BaseModel):
    ihc_role: Optional[str] = None
    department: Optional[str] = None
    display_name: Optional[str] = None


class MemberItem(BaseModel):
    id: str
    email: str
    display_name: str
    ihc_role: Optional[str] = None
    department: Optional[str] = None
    status: str
    created_at: datetime


class MembersResponse(BaseModel):
    members: list[MemberItem]
    count: int
    max_allowed: int = MAX_MEMBERS


class InviteAuditorRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    specialty: str = ""  # Chuyên môn: food safety, halal compliance, etc.


class AuditorItem(BaseModel):
    id: str
    email: str
    display_name: str
    specialty: Optional[str] = None
    status: str
    created_at: datetime


class AuditorsResponse(BaseModel):
    auditors: list[AuditorItem]
    count: int


class PendingProviderItem(BaseModel):
    id: str
    email: str
    company_name: str
    company_code: Optional[str]
    created_at: datetime


class PendingProvidersResponse(BaseModel):
    providers: list[PendingProviderItem]
    count: int
