# Feature — Schema (PDF HTML Renderer 3-stage pipeline)

**Stage 3** · linked to `spec.md` + `threat-model.md`. Defines the data
contract between the three pipeline stages.

```
Frontend ──┐
            ▼
   ┌────────────────────────┐
   │ Stage 1: Aggregator    │  fetch from 6 sources in parallel
   │  + RawDataBundle       │  ↓ tenant-scoped, cached 5min
   └────────────────────────┘
            ▼
   ┌────────────────────────┐
   │ Stage 2: FilterPipeline│  validate → format → truncate → watermark
   │  + RenderContext       │  ↓ deterministic, ordered
   └────────────────────────┘
            ▼
   ┌────────────────────────┐
   │ Stage 3: PDFRenderer   │  Jinja2 (StrictUndefined) → Playwright → pikepdf
   │  + bytes               │  ↓ existing implementation
   └────────────────────────┘
            ▼
   PDF response
```

---

## A. Stage 1 — `RawDataBundle` (output of aggregator)

```python
@dataclass(frozen=True)
class RawDataBundle:
    # ── Request context ──
    doc_type: str                          # "company_profile", "halal_policy", ...
    tenant_id: UUID
    actor_id: UUID                         # who initiated render (audit trail)
    actor_role: Literal["business", "provider", "admin"]
    request_payload: dict                  # raw body.data from frontend (untrusted)
    request_lang: Literal["vi", "en"] = "vi"
    is_draft: bool = True

    # ── Source 1: User company data (DB: users, business_profiles) ──
    company: Optional[CompanyData] = None  # tenant's own profile

    # ── Source 2: Submission lifecycle (DB: submissions, evaluations, comments) ──
    active_submission: Optional[SubmissionData] = None

    # ── Source 3: Halal certificates (DB: halal_certificates, cert_anchor_proofs) ──
    certificates: list[CertificateData] = field(default_factory=list)

    # ── Source 4: Documents under this tenant (DB: documents, status) ──
    documents: list[DocumentData] = field(default_factory=list)

    # ── Source 5: Admin template config (FS: admin_templates/<doc_type>.json) ──
    admin_cfg: dict = field(default_factory=dict)
    # docx_config block — confidential_label, cover_meta, custom_sections,
    # show_approval_block, ... (already used by existing templates_docx route)

    # ── Source 6: Admin template assets ──
    admin_assets: AdminAssets = field(default_factory=AdminAssets)
    # - reference_text:   plain text extracted from admin_templates/files/<doc_type>/*.docx
    # - logo_uri:         file:// path to CB-specific logo (Phase 2 multi-CB; default AMINRA)
    # - extra_assets:     dict of {key: file_uri} for images/diagrams admin uploaded

    # ── Cross-tenant view (provider/auditor only) ──
    cross_tenant: Optional[CrossTenantView] = None
    # When actor_role == "provider", aggregator may pull data from a single
    # business tenant THE PROVIDER IS ASSIGNED TO (verified via submissions).
    # Strict: never returns data from tenants the actor has no relationship with.

    # ── Provenance (cache + telemetry) ──
    fetched_at: datetime
    sources_versions: dict[str, str]       # SHA-256 per source for cache key invalidation
```

### Sub-types

```python
@dataclass(frozen=True)
class CompanyData:
    business_name: str
    business_name_en: Optional[str]
    tax_code: Optional[str]
    address: Optional[str]
    factory_address: Optional[str]
    phone: Optional[str]                   # raw — formatted by FormatFilter
    email: Optional[str]
    website: Optional[str]
    representative_name: Optional[str]
    founded_year: Optional[int]
    employee_count: Optional[int]
    charter_capital: Optional[str]         # free-form (currency varies)
    logo_uri: Optional[str]                # file:// — uploaded by tenant

@dataclass(frozen=True)
class SubmissionData:
    id: UUID
    status: Literal["draft", "submitted", "evaluating", "approved", "rejected"]
    submitted_at: Optional[datetime]
    cb_assigned: Optional[str]             # CB tenant slug (HALCERT, HCA, ...)
    halal_responsible_person: Optional[ResponsiblePerson]
    products: list[ProductData]
    business_activities: list[str]
    halal_commitment: Optional[str]
    revision_count: int = 0

@dataclass(frozen=True)
class CertificateData:
    cert_number: str
    issued_date: date
    expiry_date: date
    status: Literal["active", "expired", "revoked"]
    cert_pdf_hash: str                     # SHA-256 (audit invariance)

@dataclass(frozen=True)
class DocumentData:
    id: UUID
    doc_type: str
    status: str
    uploaded_at: datetime
    approved_at: Optional[datetime]

@dataclass(frozen=True)
class AdminAssets:
    reference_text: Optional[str] = None
    logo_uri: Optional[str] = None
    extra_assets: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class ResponsiblePerson:
    name: str
    title: Optional[str]
    email: Optional[str]
    phone: Optional[str]

@dataclass(frozen=True)
class ProductData:
    name: str
    description: Optional[str]
    annual_output: Optional[str]
    halal_status: Literal["certified", "pending", "not_applicable"] = "pending"

@dataclass(frozen=True)
class CrossTenantView:
    business_tenant_id: UUID
    business_company: CompanyData
    relationship: Literal["assigned_audit", "issued_cert", "shared_workflow"]
    granted_via: UUID                      # submission id or cert id that grants access
```

---

## B. Stage 2 — `RenderContext` (output of FilterPipeline)

```python
@dataclass
class RenderContext:
    # Slimmed, formatted, validated. This is what reaches Jinja2 templates.
    # Field names match what current macros expect; new fields added per
    # template version migration.

    doc_type: str
    title: str
    title_default: str
    is_draft: bool
    lang: str

    # Validated payload (Pydantic-cleaned, defaults applied)
    data: dict                             # legacy shape compatible with current templates
    cfg: dict                              # admin_cfg with watermark + draft flags injected

    # Layout hints (set by filters, consumed by templates)
    layout: LayoutHints = field(default_factory=LayoutHints)

    # Diagnostics (telemetry only, NOT rendered)
    bundle_etag: str                       # hash of source RawDataBundle for cache key
    filters_applied: list[str] = field(default_factory=list)  # ordered names
    elapsed_ms_per_stage: dict[str, int] = field(default_factory=dict)


@dataclass
class LayoutHints:
    """Hints templates may consult; default = "auto" lets template decide."""
    products_layout: Literal["auto", "stat_grid_4", "kv_block"] = "auto"
    activities_layout: Literal["auto", "single_col", "two_col"] = "auto"
    commitment_render: Literal["auto", "lede", "pull_quote"] = "auto"
    show_watermark: bool = True
    # Q3=a: Phase 1 these stay "auto"; Phase 2+ rules engine sets explicit values.
```

---

## C. FilterPipeline — execution order

Order matters. Each filter mutates `RenderContext` in-place or returns new.

```python
DEFAULT_PIPELINE = [
    ValidationFilter(),       # 1. Pydantic validate request_payload → typed
    SourceMergeFilter(),      # 2. Merge company + submission + admin_cfg → ctx.data
    FormatFilter(),           # 3. date vi-VN, currency VND, phone, address split
    TruncationFilter(),       # 4. cover title ≤ 4 lines, eyebrow ≤ 30 chars, etc.
    WatermarkFilter(),        # 5. inject is_draft → cfg.watermark + body class
    # — Phase 2 (deferred): LayoutDecisionFilter (YAML rules engine)
]
```

### Filter contracts (Stage 2 detail)

```python
class DesignFilter(Protocol):
    name: str

    def apply(self, bundle: RawDataBundle, ctx: RenderContext) -> RenderContext:
        """Pure function — no I/O. Deterministic given (bundle, ctx)."""
```

#### `ValidationFilter`
- Input: `bundle.request_payload` (untrusted dict from frontend)
- Action: `schema.model_validate(payload)` from `pdf_render_schemas`
- Output: writes `ctx.data` with cleaned dict
- Failure: raises `ValidationError` → router converts to HTTP 400

#### `SourceMergeFilter`
- Input: `bundle.company`, `bundle.active_submission`, `bundle.admin_cfg`, `ctx.data`
- Action: merge precedence (later overrides earlier):
  1. admin defaults from `admin_cfg.defaults` if present
  2. tenant company from DB (`bundle.company`)
  3. submission data (`bundle.active_submission`)
  4. request payload (frontend overrides — admin only)
- Output: rewrites `ctx.data` to merged shape

#### `FormatFilter`
- Locale-aware formatters:
  - `issued_date: "2026-05-05"` → `"05/05/2026"` (lang=vi) or `"May 05, 2026"` (lang=en)
  - `charter_capital: "12000000000"` → `"12.000.000.000 VND"` (vi)
  - `phone: "+842381234567"` → `"+84 238 1234 567"` (split groups)
  - `address` → split into lines if comma-heavy (≥3 segments)
- Pure CSS-aside; only data string mutation.

#### `TruncationFilter`
- Length limits:
  - `title` ≤ 80 chars (truncate with ellipsis)
  - `business_name_en` ≤ 80 (cover layout breaks otherwise)
  - cover `meta[].value` ≤ 60 chars
- Logs truncation events to telemetry.

#### `WatermarkFilter`
- If `bundle.is_draft = True`:
  - `ctx.cfg["watermark"] = "DRAFT"`
  - `body class="is-draft"` already handled by template; filter just confirms flag.
- If `bundle.cross_tenant.relationship == "assigned_audit"` and actor is provider:
  - `ctx.cfg["watermark"] = "PROVIDER PREVIEW"` (Phase 2 marker)

---

## D. Migration plan from current 1-stage to 3-stage

Backward-compatibility path for `company_profile/v1/template.html`:

1. Aggregator + Pipeline ship; router calls them in sequence.
2. RenderContext.data shape **must remain identical** to current Jinja2 expectations
   (uses macros). No template rewrite needed.
3. Visual regression baseline UNCHANGED — bytes identical proof of correctness.
4. New schemas (Phase 2 templates) opt into richer RenderContext fields.

Concretely: existing template won't notice — `ctx.data["business_name"]` resolves
the same whether sourced from `bundle.request_payload` or `bundle.company`.
The merge happens silently in `SourceMergeFilter`.

---

## E. Cache + invalidation (Stage 1)

```
Cache key = (tenant_id, doc_type, sources_versions_hash)
TTL = 5 minutes
```

`sources_versions_hash` derived from:
- `users.updated_at` for tenant
- `submissions.updated_at` for the tenant's active submission (if any)
- `mtime(admin_templates/<doc_type>.json)` for admin cfg
- `mtime(admin_templates/files/<doc_type>/*)` for admin assets

If any source changed → key changes → cache miss → fresh fetch.

---

## F. Cross-tenant access rules (Stage 1)

| Actor role | What aggregator may fetch |
|---|---|
| business + is_owner | own tenant's company + submissions + certs + documents |
| business + member  | same scope (RBAC enforced by frontend; aggregator double-checks tenant_id match) |
| provider/auditor   | own tenant + **business tenants linked via submissions assigned to this provider** (CrossTenantView populated) |
| admin              | any tenant (read-only) — must be explicit query param `?on_behalf_of=<tenant>` |

**Strict invariants:**
- Every DB query in aggregator includes `WHERE tenant_id = ?` or join through a verified relationship.
- Cross-tenant access path requires a verified link (submission or cert) — never raw tenant_id from request.
- All cross-tenant fetches logged to audit_log with `action=document.cross_tenant_aggregate`.

---

## G. Schema versioning

- `RawDataBundle` and `RenderContext` are dataclasses — adding optional fields = non-breaking.
- Removing a field = breaking, requires bumping template versions:
  - `company_profile/v1/` keeps reading old field
  - `company_profile/v2/` reads new field
  - Migration: dual-render `v1` + `v2` for 1 release; deprecate `v1` after.
- Pydantic schemas (`pdf_render_schemas.py`) are the source of truth for `request_payload` shape; aggregator extends them with DB sources but never overrides.
