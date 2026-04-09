"""Pydantic models for Supply Chain modules."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


# ── Suppliers ────────────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    supplier_type: Optional[str] = None
    tax_code: Optional[str] = None
    notes: Optional[str] = None

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_person: Optional[str] = None
    supplier_type: Optional[str] = None
    tax_code: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

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


# ── Materials ────────────────────────────────────────────────────────────────

class MaterialCreate(BaseModel):
    name: str
    supplier_id: str
    sku: Optional[str] = None
    category: Optional[str] = None
    halal_risk: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None

class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    supplier_id: Optional[str] = None
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
    name: str
    description: Optional[str] = None
    flowchart: Optional[dict] = None

class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    flowchart: Optional[dict] = None
    is_active: Optional[bool] = None

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
    product_name: str
    process_template_id: Optional[str] = None
    notes: Optional[str] = None
    materials: Optional[List[dict]] = None  # [{"material_id": "...", "quantity": 10, "unit": "kg"}]

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
