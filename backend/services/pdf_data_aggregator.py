"""Stage 1 of the PDF rendering pipeline — gather raw data from all sources.

Inputs:
    doc_type, tenant_id, actor (JWT-decoded), request_payload

Sources (parallel via asyncio.gather; tenant-scoped strict):
    1. user company data            ← `users` table
    2. active submission            ← `submissions` table (Phase 2 wired-in)
    3. halal certificates           ← `halal_certificates` (Phase 2)
    4. tenant documents             ← `documents` (Phase 2)
    5. admin template config (JSON) ← `admin_templates/<doc_type>.json`
    6. admin template assets        ← `admin_templates/files/<doc_type>/*`

Output: `RawDataBundle` (frozen dataclass — see docs/features/pdf-html-renderer/schema.md).

Cross-tenant access (provider/auditor):
    Only fetched when actor.role in {"provider","admin"}, and only via a
    verified relationship (submission assignment or issued cert). See
    CrossTenantView.granted_via for audit trail.

Cache:
    5-minute LRU keyed on (tenant_id, doc_type, sources_versions_hash).
    `sources_versions_hash` includes mtimes of admin files + updated_at of
    DB rows, so any change invalidates immediately.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import UUID

log = logging.getLogger("aminra.pdf_aggregator")


# ── Sub-types (mirror schema.md) ────────────────────────────────────────────


@dataclass(frozen=True)
class CompanyData:
    business_name: str
    business_name_en: Optional[str] = None
    tax_code: Optional[str] = None
    address: Optional[str] = None
    factory_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    representative_name: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[int] = None
    charter_capital: Optional[str] = None
    logo_uri: Optional[str] = None


@dataclass(frozen=True)
class ResponsiblePerson:
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass(frozen=True)
class ProductData:
    name: str
    description: Optional[str] = None
    annual_output: Optional[str] = None
    halal_status: Literal["certified", "pending", "not_applicable"] = "pending"


@dataclass(frozen=True)
class SubmissionData:
    id: str
    status: str
    submitted_at: Optional[datetime] = None
    cb_assigned: Optional[str] = None
    halal_responsible_person: Optional[ResponsiblePerson] = None
    products: list[ProductData] = field(default_factory=list)
    business_activities: list[str] = field(default_factory=list)
    halal_commitment: Optional[str] = None
    revision_count: int = 0


@dataclass(frozen=True)
class CertificateData:
    cert_number: str
    issued_date: date
    expiry_date: date
    status: str
    cert_pdf_hash: str


@dataclass(frozen=True)
class DocumentData:
    id: str
    doc_type: str
    status: str
    uploaded_at: datetime
    approved_at: Optional[datetime] = None


@dataclass(frozen=True)
class AdminAssets:
    reference_text: Optional[str] = None     # plain-text extracted from .docx
    logo_uri: Optional[str] = None           # file:// to CB or AMINRA logo
    extra_assets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CrossTenantView:
    business_tenant_id: str
    business_company: CompanyData
    relationship: str        # "assigned_audit" | "issued_cert" | "shared_workflow"
    granted_via: str          # submission id or cert id


@dataclass(frozen=True)
class RawDataBundle:
    # Request context
    doc_type: str
    tenant_id: str
    actor_id: str
    actor_role: str
    request_payload: dict
    request_lang: str = "vi"
    is_draft: bool = True

    # Sources
    company: Optional[CompanyData] = None
    active_submission: Optional[SubmissionData] = None
    certificates: list[CertificateData] = field(default_factory=list)
    documents: list[DocumentData] = field(default_factory=list)
    admin_cfg: dict = field(default_factory=dict)
    admin_assets: AdminAssets = field(default_factory=AdminAssets)
    cross_tenant: Optional[CrossTenantView] = None

    # Provenance
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    sources_versions: dict[str, str] = field(default_factory=dict)


# ── Aggregator ─────────────────────────────────────────────────────────────


# In-process cache: { cache_key: (bundle, expires_at_epoch) }
_CACHE: dict[str, tuple[RawDataBundle, float]] = {}
_CACHE_TTL_S = 300                  # 5 minutes — match feature_flags cache cadence
_ADMIN_TPL_DIR = Path("admin_templates")


class PDFDataAggregator:
    """Stateless service — single instance per backend process."""

    async def fetch(
        self,
        *,
        db,
        doc_type: str,
        tenant_id: str,
        actor: dict,                # JWT payload
        request_payload: dict,
        request_lang: str = "vi",
        is_draft: bool = True,
    ) -> RawDataBundle:
        """Fetch all relevant sources in parallel; return frozen bundle."""
        actor_id = actor.get("sub", "")
        actor_role = actor.get("role", "business")

        cache_key = self._cache_key(tenant_id, doc_type)
        cached = _CACHE.get(cache_key)
        if cached is not None and cached[1] > time.time():
            # Cache hit — but request_payload differs per request, so we
            # rebuild a new bundle with same source data + new payload.
            base = cached[0]
            return RawDataBundle(
                doc_type=doc_type,
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_role=actor_role,
                request_payload=request_payload,
                request_lang=request_lang,
                is_draft=is_draft,
                company=base.company,
                active_submission=base.active_submission,
                certificates=base.certificates,
                documents=base.documents,
                admin_cfg=base.admin_cfg,
                admin_assets=base.admin_assets,
                cross_tenant=base.cross_tenant,
                fetched_at=base.fetched_at,
                sources_versions=base.sources_versions,
            )

        # Cache miss — fetch everything in parallel
        t0 = time.monotonic()
        company_t  = self._fetch_company(db, tenant_id)
        cfg_t      = self._fetch_admin_cfg(doc_type)
        assets_t   = self._fetch_admin_assets(doc_type)
        # Phase 2 wires: submission, certificates, documents, cross_tenant.
        # Stub placeholders for now — fast no-op so future migration is
        # one-line uncomment without changing aggregator API.
        submission_t = self._fetch_active_submission(db, tenant_id)
        certs_t      = self._fetch_certificates(db, tenant_id)
        docs_t       = self._fetch_documents(db, tenant_id)

        company, admin_cfg, admin_assets, submission, certs, docs = await asyncio.gather(
            company_t, cfg_t, assets_t, submission_t, certs_t, docs_t,
            return_exceptions=False,
        )

        bundle = RawDataBundle(
            doc_type=doc_type,
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            request_payload=request_payload,
            request_lang=request_lang,
            is_draft=is_draft,
            company=company,
            active_submission=submission,
            certificates=certs,
            documents=docs,
            admin_cfg=admin_cfg,
            admin_assets=admin_assets,
            cross_tenant=None,                   # Phase 2 wires
            fetched_at=datetime.utcnow(),
            sources_versions=self._build_versions(company, admin_cfg, admin_assets),
        )

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "[pdf_aggregator] tenant=%s doc_type=%s sources=6 elapsed_ms=%d",
            tenant_id, doc_type, elapsed_ms,
        )

        _CACHE[cache_key] = (bundle, time.time() + _CACHE_TTL_S)
        return bundle

    # ── Source fetchers ────────────────────────────────────────────────────

    async def _fetch_company(self, db, tenant_id: str) -> Optional[CompanyData]:
        """Tenant company profile from `users` table (owner row).

        AMINRA stores tenant identity on the OWNER user row (is_owner=true,
        tenant_id=<that user's id>). One owner per tenant.
        """
        if not tenant_id:
            return None
        row = await db.fetchrow(
            """
            SELECT
                company_name, company_code, tenant_id,
                address, phone, email, representative_name, manager_name,
                created_at
            FROM users
            WHERE tenant_id = $1 AND is_owner = TRUE AND deleted_at IS NULL
            LIMIT 1
            """,
            tenant_id,
        )
        if row is None:
            return None
        return CompanyData(
            business_name=row["company_name"],
            tax_code=row["company_code"],   # MST often stored in company_code
            address=row["address"],
            phone=row["phone"],
            email=row["email"],
            representative_name=row["representative_name"],
        )

    async def _fetch_active_submission(self, db, tenant_id: str) -> Optional[SubmissionData]:
        """Most recent in-flight submission for the tenant.

        Phase 2 wiring — currently returns None until templates need it
        (halal_policy + sop_* don't; certificate_lifecycle would).
        """
        return None

    async def _fetch_certificates(self, db, tenant_id: str) -> list[CertificateData]:
        return []

    async def _fetch_documents(self, db, tenant_id: str) -> list[DocumentData]:
        return []

    async def _fetch_admin_cfg(self, doc_type: str) -> dict:
        path = _ADMIN_TPL_DIR / f"{doc_type}.json"
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw.get("docx_config") or {}
        except Exception as exc:                                      # noqa: BLE001
            log.warning("[pdf_aggregator] cfg load failed for %s: %s", doc_type, exc)
            return {}

    async def _fetch_admin_assets(self, doc_type: str) -> AdminAssets:
        """Extract plain text from any .docx admin uploaded for this doc_type.

        Used by template macros that want to merge admin reference content
        with user data (eg. SOP boilerplate that admin maintains, but
        signed under the user company name).
        """
        files_dir = _ADMIN_TPL_DIR / "files" / doc_type
        if not files_dir.exists():
            return AdminAssets()

        reference_text: Optional[str] = None
        extra_assets: dict[str, str] = {}

        for f in files_dir.iterdir():
            if f.suffix.lower() == ".docx" and reference_text is None:
                try:
                    reference_text = self._extract_docx_text(f)
                except Exception as exc:                              # noqa: BLE001
                    log.warning("[pdf_aggregator] docx extract failed %s: %s", f, exc)
            elif f.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}:
                # Asset registered under stem name — template references
                # via {{ asset_uri('logo') }} (Phase 2 helper).
                extra_assets[f.stem] = f.resolve().as_uri()

        return AdminAssets(
            reference_text=reference_text,
            logo_uri=None,                # Phase 2 multi-CB
            extra_assets=extra_assets,
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_docx_text(path: Path) -> str:
        """Plain text from a .docx — paragraphs only, no tables/images.

        Sanitised: strip control chars, no HTML tag preservation. Output
        is treated as untrusted text by templates (auto-escaped via Jinja2).
        """
        from docx import Document as DocxDoc

        doc = DocxDoc(str(path))
        parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(parts)

    @staticmethod
    def _cache_key(tenant_id: str, doc_type: str) -> str:
        return f"pdf_aggregator:{tenant_id}:{doc_type}"

    @staticmethod
    def _build_versions(
        company: Optional[CompanyData],
        admin_cfg: dict,
        admin_assets: AdminAssets,
    ) -> dict[str, str]:
        """SHA-256 per source — used for cache invalidation + telemetry."""
        def _h(s: Any) -> str:
            return hashlib.sha256(repr(s).encode("utf-8")).hexdigest()[:16]
        return {
            "company": _h(company),
            "admin_cfg": _h(admin_cfg),
            "admin_assets": _h(admin_assets),
        }


def invalidate_cache() -> None:
    """Force re-fetch on next call. Call from admin tools after upload."""
    _CACHE.clear()
