"""Pydantic models for Supply Chain modules."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any
from datetime import date, datetime
import re


# VN tax code format: 10 digits (cá nhân / chi nhánh độc lập) or
# 10 digits + "-" + 3 digits (doanh nghiệp với chi nhánh phụ thuộc).
_VN_TAX_CODE_RE = re.compile(r"^\d{10}(-\d{3})?$")


def _validate_tax_code(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return v
    if not _VN_TAX_CODE_RE.fullmatch(v):
        raise ValueError(
            "Mã số thuế không hợp lệ — phải là 10 chữ số, "
            "hoặc 10-3 chữ số (vd: 0312345678 hoặc 0312345678-001)"
        )
    return v


def _validate_non_blank(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Trường bắt buộc, không được để trống / chỉ khoảng trắng")
    return v


# ── Suppliers ────────────────────────────────────────────────────────────────


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_person: Optional[str] = None
    supplier_type: Optional[str] = None
    tax_code: Optional[str] = None
    notes: Optional[str] = None

    _name_nonblank = field_validator("name")(lambda cls, v: _validate_non_blank(v))
    _tax_format = field_validator("tax_code")(lambda cls, v: _validate_tax_code(v))


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_person: Optional[str] = None
    supplier_type: Optional[str] = None
    tax_code: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name_nb(cls, v):
        return _validate_non_blank(v) if v is not None else v

    _tax_format = field_validator("tax_code")(lambda cls, v: _validate_tax_code(v))


class SupplierOut(BaseModel):
    id: str
    name: str
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    contact_person: Optional[str]
    supplier_type: Optional[str]
    tax_code: Optional[str]
    status: str
    notes: Optional[str]
    material_count: int = 0
    cert_count: int = 0
    created_at: datetime


class CertificateOut(BaseModel):
    id: str
    cert_type: Optional[str]
    cert_number: Optional[str]
    issuing_body: Optional[str]
    issued_date: Optional[date]
    expiry_date: Optional[date]
    original_filename: Optional[str]
    file_size: Optional[int]
    created_at: datetime


class SupplierCertificateEligibilityUpsert(BaseModel):
    certificate_no: str = Field(..., min_length=1, max_length=255)
    issuer_name: str = Field(..., min_length=1, max_length=255)
    status: str = "pending_review"
    valid_from: date
    valid_until: date
    scope: dict[str, Any] = Field(default_factory=dict)
    source_of_truth: str = "cb"
    reason: Optional[str] = None

    _certificate_nonblank = field_validator("certificate_no")(lambda cls, v: _validate_non_blank(v))
    _issuer_nonblank = field_validator("issuer_name")(lambda cls, v: _validate_non_blank(v))

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        allowed = {"active", "expired", "suspended", "revoked", "pending_review"}
        if v not in allowed:
            raise ValueError("Trạng thái chứng nhận CB không hợp lệ")
        return v

    @field_validator("source_of_truth")
    @classmethod
    def _cb_only(cls, v: str) -> str:
        if v != "cb":
            raise ValueError("Chỉ CB/provider được là nguồn xác thực")
        return v


class SupplierCertificateEligibilityOut(BaseModel):
    id: str
    supplier_id: str
    tenant_id: str
    certificate_no: str
    issuer_name: str
    status: str
    valid_from: date
    valid_until: date
    scope: dict[str, Any]
    source_of_truth: str
    provider_id: Optional[str] = None
    source_certificate_id: Optional[str] = None
    changed_at: Optional[datetime]
    changed_by: Optional[str]
    reason: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None


class EligibleSupplierOut(SupplierOut):
    eligibility_id: str
    certificate_no: str
    issuer_name: str
    certificate_status: str
    valid_from: date
    valid_until: date
    eligibility_scope: dict[str, Any] = Field(default_factory=dict)
    provider_id: Optional[str] = None
    source_certificate_id: Optional[str] = None


class CertificateRiskAlertOut(BaseModel):
    id: str
    impacted_tenant_id: str
    supplier_id: str
    supplier_name: Optional[str] = None
    certificate_id: str
    event_type: str
    severity: str
    message: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class CertificateRiskAlertUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid_alert_status(cls, v: str) -> str:
        allowed = {"open", "acknowledged", "resolved"}
        if v not in allowed:
            raise ValueError("Trạng thái cảnh báo không hợp lệ")
        return v


# ── Materials ────────────────────────────────────────────────────────────────


class MaterialCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    supplier_id: str
    sku: Optional[str] = None
    category: Optional[str] = None
    halal_risk: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None

    _name_nb = field_validator("name")(lambda cls, v: _validate_non_blank(v))


class MaterialUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    supplier_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name_nb(cls, v):
        return _validate_non_blank(v) if v is not None else v

    sku: Optional[str] = None
    category: Optional[str] = None
    halal_risk: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None


class MaterialOut(BaseModel):
    id: str
    name: str
    sku: Optional[str]
    category: Optional[str]
    halal_risk: str
    description: Optional[str]
    unit: Optional[str]
    supplier_id: str
    supplier_name: Optional[str] = None
    created_at: datetime


# ── Process Templates ────────────────────────────────────────────────────────


class ProcessCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    flowchart: Optional[dict] = None

    _name_nb = field_validator("name")(lambda cls, v: _validate_non_blank(v))


class ProcessUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    flowchart: Optional[dict] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _name_nb(cls, v):
        return _validate_non_blank(v) if v is not None else v


class ProcessOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    flowchart: dict
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Production Batches ───────────────────────────────────────────────────────


class BatchCreate(BaseModel):
    batch_code: Optional[str] = None
    product_name: str = Field(..., min_length=1, max_length=255)
    process_template_id: Optional[str] = None
    notes: Optional[str] = None
    materials: Optional[List[dict]] = None  # [{"material_id": "...", "quantity": 10, "unit": "kg"}]

    _pn_nb = field_validator("product_name")(lambda cls, v: _validate_non_blank(v))


class BatchUpdate(BaseModel):
    product_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BatchStepUpdate(BaseModel):
    status: Optional[str] = None
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    checklist: Optional[list] = None


class BatchOut(BaseModel):
    id: str
    batch_code: str
    product_name: str
    process_template_id: Optional[str]
    process_name: Optional[str] = None
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    compliance_score: Optional[int]
    qr_code_url: Optional[str]
    notes: Optional[str]
    step_count: int = 0
    step_completed: int = 0
    material_count: int = 0
    created_at: datetime
