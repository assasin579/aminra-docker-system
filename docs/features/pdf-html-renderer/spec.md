# Feature — HTML/CSS PDF Renderer (Playwright)

**Status**: Stage 1 (Spec) · Started 2026-05-05
**Owner**: Halal MVP team
**Feature flag**: `pdf_html_renderer_v1` (rollout per doc_type)
**Priority**: P0 — block investor demo

## 1. Why this exists

Current pipeline: form data → `templates_docx/<doc_type>.py` → DOCX bytes → `libreoffice --headless --convert-to pdf` (5 call sites: `app.py:762`, `auth/router.py:990,1169`, `auth/document_router.py:479`, `supply_chain/supplier_router.py:351`).

**Pain points:**

| Issue | Impact |
|---|---|
| LibreOffice default styling: Times New Roman / Calibri, mặc định table border, không brand color | PDF trông như "thư hành chính", không đủ chuyên nghiệp cho investor demo + business user submission |
| LibreOffice convert lossy: spacing, page-break, font-fallback unpredictable trên Linux container | Output không deterministic — cùng DOCX khác máy ra khác PDF |
| Không control được footer, watermark, QR placement chuẩn brand | Mỗi doc_type cần variant layout; reportlab + libreoffice mỗi cái style theo cách khác |
| Không có visual regression test → designer thay đổi ngầm, không phát hiện | Drift dài hạn |

**Solution:** Render PDF qua HTML+CSS với Playwright Chromium headless. Designer/dev commit template `templates_html/<doc_type>/v1/{template.html, style.css, print.css, assets/}` vào codebase, renderer service inject data + emulate print + `page.pdf()`.

## 2. Scope (Phase 1 — demo)

**In scope:**
- 13 doc_type sống cùng `templates_docx/_registry.py`:
  `halal_policy`, `has_manual` (alias `halal_manual`), 6 `sop_*` variants, `company_profile`, `internal_halal_committee`, `ingredient_raw_material`, `process_flow_chart`
- Inter font (Latin Extended + Vietnamese subset) bundle local
- Vietnamese + English content (UTF-8, no special font handling beyond Inter)
- A4 portrait, có header/footer, page number, watermark optional theo cfg
- API endpoint POST `/api/templates/{doc_type}/render-pdf`
- Per-tenant scoping qua existing JWT + RBAC pattern
- Browser pool managed qua FastAPI lifespan (1 browser, N contexts)
- Streaming response + ETag cache header

**Out of scope (defer):**
- Arabic RTL rendering (Phase 2 — sau khi có business case)
- Multi-CB branding (mỗi tổ chức chứng nhận template riêng) — hiện shared layout
- Runtime template upload qua admin UI — chỉ commit-controlled
- A/B test framework giữa libreoffice route cũ vs HTML route mới (manual cutover per doc_type)
- Migrate `services/certificate_pdf.py` (reportlab) — KHÔNG đụng vì cert hash + QR public verifier đã live, đổi render sẽ phá invariance
- Migrate `audit_router.py:1064+` audit log PDF (reportlab) — sau demo
- Migrate `supply_chain/batch_router.py:760+` batch PDF (reportlab) — sau demo
- Render cache (R2 cache theo input hash) — sau demo
- Hot-reload preview cho designer — Phase 2 nice-to-have

## 3. Personas + permissions

Reuse existing RBAC. KHÔNG thêm permission mới.

| Persona | Trigger render | Cross-tenant render | Admin override |
|---|---|---|---|
| Business Owner | ✓ render doc của tenant mình | ✗ | ✗ |
| Business Member với `can_edit_documents` | ✓ | ✗ | ✗ |
| Provider/Auditor | ✓ render doc của submission họ assigned (READ-ONLY) | ✓ (assigned only) | ✗ |
| Platform Admin | ✓ READ-ONLY (debug audit) | ✓ | ✗ — không thể tạo doc cho tenant khác |
| Anonymous | ✗ 401 | — | — |

Cross-tenant check: reuse pattern từ `auth/document_router.py` — verify `tenant_id` từ JWT match `document.tenant_id` hoặc submission assignment.

## 4. Architecture

### 4.1 Layout

```
backend/
├── services/
│   └── pdf_renderer.py             # Playwright async + Jinja2 + browser pool
├── templates_html/
│   ├── _registry.py                # doc_type → template_path + Pydantic schema
│   ├── _base/
│   │   ├── base.html               # extends layout (header, footer, page number)
│   │   ├── base.css                # Reset + Inter @font-face + design tokens
│   │   └── print.css               # @page, page-break rules, A4
│   ├── _shared/
│   │   ├── fonts/Inter-{Regular,Medium,SemiBold,Bold}.woff2
│   │   ├── logo-aminra.svg
│   │   └── watermark-confidential.svg
│   ├── company_profile/v1/
│   │   ├── template.html           # Jinja2 extends base
│   │   ├── style.css               # doc-specific overrides
│   │   └── README.md               # designer notes (data shape, preview cmd)
│   ├── halal_policy/v1/
│   ├── has_manual/v1/
│   ├── sop/v1/                     # shared cho 6 sop_* variants (cfg controls header)
│   ├── internal_halal_committee/v1/
│   ├── ingredient_raw_material/v1/
│   ├── process_flow_chart/v1/
│   └── generic/v1/
└── auth/
    └── pdf_render_router.py        # FastAPI router, registered trong app.py
```

### 4.2 Renderer service contract

```python
# services/pdf_renderer.py

class PDFRenderer:
    """
    Browser pool managed lifespan.
    Singleton instance: app.state.pdf_renderer
    """

    async def startup(self) -> None: ...    # launch browser, create N contexts
    async def shutdown(self) -> None: ...   # close all contexts + browser

    async def render(
        self,
        doc_type: str,
        data: dict,                      # validated Pydantic model.dict()
        cfg: dict,                       # admin_templates JSON cfg merged
        title: str,
        tenant_id: str,                  # for audit log only, not for routing
    ) -> bytes:
        """
        Returns PDF bytes. Raises:
        - TemplateNotFoundError nếu doc_type không có template HTML
        - RenderTimeoutError nếu browser hang > 30s
        - RenderConcurrencyError nếu pool exhausted
        """

POOL_SIZE = 3            # tunable via env PDF_RENDERER_POOL_SIZE
RENDER_TIMEOUT_S = 30
JINJA_AUTOESCAPE = True  # XSS protection
```

### 4.3 Browser lifecycle

- **Startup**: `playwright.chromium.launch(args=['--font-render-hinting=none'])`. Mỗi context = isolated cookie/storage/cache, KHÔNG shared giữa requests.
- **Per-request**: acquire 1 context (semaphore-bound queue, max=POOL_SIZE), `context.new_page()`, set content, render, close page. Context reused cho request kế tiếp.
- **Shutdown**: drain queue, close browser, fail in-flight requests với 503.
- **Health**: nếu browser process die mid-render → restart browser, khi đó queue 503 cho 5s rồi resume.

### 4.4 Data flow

```
1. Frontend POST /api/templates/{doc_type}/render-pdf
   Body: { data: {...}, title?: string, cfg_override?: {...} }
   Header: Authorization: Bearer <jwt>

2. FastAPI route:
   a. Verify JWT, extract tenant_id + roles
   b. RBAC: check user can render this doc_type (reuse get_authorized_user_for_tenant)
   c. Lookup admin_templates/{doc_type}.json → cfg
   d. Merge cfg_override (admin only) hoặc reject (non-admin)
   e. Pydantic validate data theo schema per doc_type
   f. Call pdf_renderer.render(doc_type, data, cfg, title, tenant_id)
   g. Audit log: document.pdf_rendered { doc_type, tenant_id, byte_size, duration_ms }
   h. Return StreamingResponse(bytes, media_type='application/pdf')
      Headers: Content-Disposition: attachment; filename="{title}.pdf"
              ETag: sha256(template_version + data_canonical_json)
              Cache-Control: private, max-age=0, must-revalidate

3. Renderer service:
   a. Load template_html/{doc_type}/v1/template.html + style.css
   b. Jinja2 render với data + cfg → final HTML string
   c. context.new_page() → page.set_content(html, wait_until='networkidle')
   d. page.emulate_media(media='print')
   e. pdf_bytes = await page.pdf(
        format='A4', print_background=True,
        margin={top:'15mm', bottom:'20mm', left:'15mm', right:'15mm'},
        display_header_footer=True,
        header_template=base_header_html,
        footer_template=base_footer_html,
      )
   f. Strip metadata timestamp (deterministic output)
   g. Close page (NOT context — context reused)

4. Return PDF bytes
```

## 5. API contract

### 5.1 Render PDF

```
POST /api/templates/{doc_type}/render-pdf
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "data": { /* shape validated theo Pydantic schema per doc_type */ },
  "title": "Hồ sơ doanh nghiệp ABC Co.",      // optional; default từ doc_type
  "cfg_override": null                          // admin-only; reject otherwise
}

→ 200 OK
   Content-Type: application/pdf
   Content-Disposition: attachment; filename="<title>.pdf"
   Content-Length: <bytes>
   ETag: "<sha256>"
   X-Render-Duration-Ms: 1234
   X-Template-Version: v1

→ 400 Bad Request   (data schema invalid)
→ 401 Unauthorized  (missing/invalid JWT)
→ 403 Forbidden     (RBAC fail; cross-tenant; cfg_override non-admin)
→ 404 Not Found     (doc_type không có template HTML — fallback DOCX route)
→ 408 Request Timeout (render > 30s)
→ 503 Service Unavailable (browser pool exhausted; retry với backoff)
```

### 5.2 Health check

```
GET /api/templates/render-pdf/health
→ 200 { "browser": "ok", "contexts_idle": 2, "contexts_busy": 1, "pool_size": 3 }
→ 503 { "browser": "down", "last_error": "..." }
```

### 5.3 List supported doc_types

```
GET /api/templates/render-pdf/registry
→ 200 [
  { "doc_type": "company_profile", "template_version": "v1", "schema": {...JSON Schema...} },
  ...
]
```

## 6. Feature flag rollout

Per-doc_type flag in DB table `feature_flags`:
- `pdf_html_renderer_v1.company_profile` — default false
- `pdf_html_renderer_v1.halal_policy` — default false
- ... (one row per doc_type)

Frontend kiểm tra flag → show button "Download PDF (new)" nếu enabled, fallback DOCX→PDF cũ nếu disabled.

Rollout sequence khi đã code xong:
1. Enable `company_profile` cho founder tenant test 1 ngày
2. Enable cho 1 CB tenant beta test
3. Bật full sau 24h không có issue
4. Lặp với từng doc_type

## 7. Backwards compatibility

- `templates_docx/` KHÔNG đụng — DOCX export endpoint giữ nguyên (`POST /processes/{pid}/export-docx`)
- LibreOffice-based DOCX→PDF preview routes (`app.py:762`, etc.) giữ nguyên — đó là user-uploaded DOCX preview, không phải template render
- Frontend giữ button "Download DOCX" song song button mới "Download PDF"
- `services/certificate_pdf.py` (reportlab cert) — KHÔNG đụng (cert hash + QR public verifier live)

## 8. Acceptance criteria

PR merge khi đủ:

1. **Phase 1 (PoC):** company_profile render đúng với data fixture → PDF mở được trong Acrobat + Chrome PDF viewer + Linux `xdg-open`
2. **Inter font** load đúng — verify bằng `pdftotext` extract text + check không có font fallback warning trong stdout
3. **Tất cả 13 doc_type** có template HTML (Phase 2) + Pydantic schema + visual regression baseline
4. **Concurrent test pass:** 5 đồng thời render company_profile → tất cả < 5s mỗi cái, total < 15s, không browser crash
5. **Tenant isolation test:** Tenant A JWT request render với data có tenant_id = B → 403 (verify qua integration test)
6. **XSS test:** payload `<script>alert(1)</script>` trong field "company_name" → escape thành `&lt;script&gt;` trong PDF output, không execute
7. **Page-break test:** SOP với 50 procedures → không cắt giữa procedure (verify CSS `page-break-inside: avoid`)
8. **Manual QA on `localhost:3100`:** founder render 1 doc thật, in giấy A4, kiểm tra brand color + logo + Inter font + page number
9. **Coverage ≥ 80%** trên `services/pdf_renderer.py` + `auth/pdf_render_router.py`
10. **Security scan clean:** bandit, semgrep — không HIGH/CRITICAL trên code mới
11. **Schema migration**: feature_flags rows seed cho 13 doc_type (UP + DOWN migration)
12. **Conventional commit** + 5 doc files đầy đủ trong `docs/features/pdf-html-renderer/`

## 9. Performance targets

| Metric | Target |
|---|---|
| Cold render (first request after lifespan startup) | < 5s |
| Warm render (browser context reused) | < 1.5s |
| Concurrent throughput | 3 req/s sustained, pool=3 |
| PDF size cho 5-page company_profile | < 800KB (Inter subset + logo SVG) |
| Memory per browser context idle | < 50MB |
| Total backend container memory ceiling | + 400MB so với baseline (browser pool=3) |

## 10. Open questions deferred

- Phase 2: chart/diagram trong process_flow_chart — render qua client-side JS (Mermaid/D3) hay server-side SVG?
- Phase 2: localization vi/en — file riêng `template.vi.html` / `template.en.html` hay 1 file với Jinja2 conditional?
- Phase 3: A/B test framework giữa libreoffice route vs HTML route — log diff size + manual review để cutover
- Phase 4: cache strategy — R2 cache PDF theo hash(template_version + data_canonical_json), TTL 7d?
