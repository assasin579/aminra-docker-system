# Feature — Test Plan (PDF HTML Renderer)

**Stage 4** · linked to `spec.md` + `threat-model.md`. Manual E2E test plan
covering Phase 1 (backend renderer + 1 template) + Phase 3 (frontend
integration). Use this as a checklist; tick each test ID after running.

> Run on `localhost:3100` to bypass Cloudflare cache (per project DoD).

---

## How to use this plan

- **Quick path** (5 min, smoke only): SETUP-* + SM-1 + SM-2 + F-1 + FE-1 → if all pass, demo-able.
- **Full E2E** (45-60 min): all sections in order.
- **Demo dress rehearsal** (10 min, before investor): SM-1 + F-1 + FE-1 + FE-3 + P-1.

For each test:
- ✅ = passed, ❌ = failed (capture output + screenshot)
- ⏭ = skipped (note reason)
- 🐛 = bug found (file in incidents/ + flag in test-report.md)

---

## A. Setup (one-time before any test)

### SETUP-1 — Download Inter font
**Goal:** 4 woff2 files present in `backend/templates_html/_shared/fonts/`.
**Steps:**
```bash
cd /home/user/Documents/aminra-docker-system
bash scripts/download_inter_font.sh
ls -lh backend/templates_html/_shared/fonts/*.woff2
```
**Expected:** 4 files (Regular, Medium, SemiBold, Bold), total ~150-250KB.
**Pass / Fail:** [ ]

### SETUP-2 — Build backend image
**Goal:** Backend Docker image rebuilt with Playwright + Chromium.
**Steps:**
```bash
docker compose build backend 2>&1 | tee /tmp/build.log
```
**Expected:** Build success in 10-20 min (first build downloads Chromium ~150MB).
**Watch out:** If `playwright install --with-deps chromium` fails on Debian slim, switch base image to `mcr.microsoft.com/playwright:v1.59.1-jammy` (note for later commit).
**Pass / Fail:** [ ]

### SETUP-3 — Run migration
**Goal:** 13 feature_flag rows seeded.
**Steps:**
```bash
bash scripts/db-migrate.sh upgrade head
docker compose exec postgres psql -U aminra -d aminra -c \
  "SELECT name, default_enabled FROM feature_flags WHERE name LIKE 'pdf_html_renderer_v1.%' ORDER BY name;"
```
**Expected:** 13 rows, all `default_enabled = f`.
**Pass / Fail:** [ ]

### SETUP-4 — Restart backend
**Goal:** Container running with new image + lifespan starts PDFRenderer.
**Steps:**
```bash
docker compose up -d backend
docker compose logs --tail=50 backend | grep -E "pdf_renderer|browser launched|ERROR"
```
**Expected:** `[pdf_renderer] browser launched, pool_size=3` line; no ERROR.
**Pass / Fail:** [ ]

### SETUP-5 — Capture test JWT + tenant_id
**Goal:** Have a valid business-owner JWT and tenant UUID for subsequent tests.
**Steps:**
1. Login at `http://localhost:3100/business/login` with test account
2. DevTools → Application → LocalStorage → copy `auth_token` value → save as `$JWT`
3. Decode at jwt.io → copy `tenant_id` claim → save as `$TENANT_ID`
**Expected:** JWT decodes with `role: "business"`, `is_owner: true`, `tenant_id: <uuid>`.
**Pass / Fail:** [ ]

### SETUP-6 — Enable feature flag for test tenant
**Goal:** `pdf_html_renderer_v1.company_profile` ON for `$TENANT_ID`.
**Steps:**
```bash
docker compose exec postgres psql -U aminra -d aminra -c "
INSERT INTO tenant_feature_overrides (tenant_id, feature_name, enabled)
VALUES ('$TENANT_ID', 'pdf_html_renderer_v1.company_profile', TRUE)
ON CONFLICT (tenant_id, feature_name) DO UPDATE SET enabled = TRUE;"
```
**Expected:** `INSERT 0 1` or `UPDATE 1`.
**Pass / Fail:** [ ]

---

## B. Smoke (cheapest sanity)

### SM-1 — Health endpoint
**Goal:** Renderer is up, browser pool initialized.
**Steps:**
```bash
curl -s http://localhost:8000/api/templates/render-pdf/health | jq
```
**Expected:**
```json
{
  "browser": "ok",
  "pool_size": 3,
  "contexts_idle": 3,
  "contexts_busy": 0,
  "queue_depth": 0,
  "queue_limit": 10
}
```
**Pass / Fail:** [ ]

### SM-2 — Registry list (auth required)
**Goal:** 13 doc_types listed; only `company_profile` `implemented: true`.
**Steps:**
```bash
curl -s -H "Authorization: Bearer $JWT" \
  http://localhost:8000/api/templates/render-pdf/registry | jq '. | length, .[] | select(.implemented==true)'
```
**Expected:** length=13; one entry with `doc_type: "company_profile", implemented: true, version: "v1"`.
**Pass / Fail:** [ ]

### SM-3 — Health requires no auth (public for monitoring)
**Steps:** `curl http://localhost:8000/api/templates/render-pdf/health` (no JWT).
**Expected:** 200 with same JSON. (If 401, route mistakenly auth-gated — bug.)
**Pass / Fail:** [ ]

---

## C. Functional — Backend API

### F-1 — Render company_profile with full fixture (golden path)
**Goal:** First end-to-end PDF render works.
**Steps:**
```bash
curl -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --argfile d backend/tests/fixtures/pdf_render/company_profile/sample.json \
       '{data: $d, is_draft: true, lang: "vi"}')" \
  -D /tmp/headers.txt \
  -o /tmp/company_profile.pdf
file /tmp/company_profile.pdf
ls -lh /tmp/company_profile.pdf
cat /tmp/headers.txt | grep -iE "content-type|etag|x-render|x-template"
xdg-open /tmp/company_profile.pdf
```
**Expected:**
- HTTP 200, `Content-Type: application/pdf`
- File size 100KB-1MB
- Headers: `ETag`, `X-Render-Duration-Ms`, `X-Template-Version: v1`
- PDF opens in viewer; cover page shows "Công ty TNHH Quế Thiên Lộc" in Inter font
- Watermark "DRAFT" diagonal across pages (light red)
- Section 1-3 with general info, products table, halal commitment
**Pass / Fail:** [ ]

### F-2 — Render with sparse data (only required fields)
**Goal:** Optional fields render as "—" without errors.
**Steps:**
```bash
curl -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "business_name": "Công ty Test ABC",
      "issued_date": "2026-05-05"
    },
    "is_draft": true
  }' \
  -o /tmp/sparse.pdf
xdg-open /tmp/sparse.pdf
```
**Expected:** 200, PDF renders; tax code, address, etc. show "—". No crash.
**Pass / Fail:** [ ]

### F-3 — ETag idempotency (deterministic output bytes)
**Goal:** Same input → same ETag + same SHA-256.
**Steps:**
```bash
for i in 1 2 3; do
  curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
    -H "Authorization: Bearer $JWT" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --argfile d backend/tests/fixtures/pdf_render/company_profile/sample.json \
         '{data: $d, is_draft: true, lang: "vi"}')" \
    -D /tmp/h_$i.txt \
    -o /tmp/det_$i.pdf
done
grep -i etag /tmp/h_1.txt /tmp/h_2.txt /tmp/h_3.txt
sha256sum /tmp/det_*.pdf
```
**Expected:** All 3 ETags identical; all 3 SHA-256 identical.
**Pass / Fail:** [ ]
**If fail:** pikepdf metadata strip not catching some field — bug, file as 🐛.

### F-4 — If-None-Match returns 304
**Goal:** Cache short-circuit works.
**Steps:**
```bash
ETAG=$(grep -i etag /tmp/h_1.txt | awk '{print $2}' | tr -d '\r')
curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -H "If-None-Match: $ETAG" \
  -d "$(jq -n --argfile d backend/tests/fixtures/pdf_render/company_profile/sample.json \
       '{data: $d, is_draft: true, lang: "vi"}')" \
  -w "%{http_code}\n" -o /dev/null
```
**Expected:** `304`.
**Pass / Fail:** [ ]

### F-5 — Schema validation rejects bad data
**Goal:** 400 with field errors when business_name missing.
**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"issued_date": "2026-05-05"}, "is_draft": true}' \
  -w "\nHTTP %{http_code}\n"
```
**Expected:** HTTP 400; body has errors mentioning `business_name`.
**Pass / Fail:** [ ]

### F-6 — Unknown doc_type → 404
**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/templates/totally_fake/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"}}' \
  -w "\nHTTP %{http_code}\n"
```
**Expected:** HTTP 404 (because regex `^[a-z][a-z0-9_]{1,40}$` accepts the name but registry doesn't, returns "unknown doc_type"; OR 422 from path-param validation if name has invalid chars).
**Pass / Fail:** [ ]

### F-7 — Known but not-implemented doc_type → 404 (flag default off) or 501
**Steps:**
1. With flag `pdf_html_renderer_v1.halal_policy` OFF (default): expect 404 (flag gate fires before template lookup).
2. Enable flag for that doc_type same way as SETUP-6, then retry: expect 501.
```bash
curl -s -X POST http://localhost:8000/api/templates/halal_policy/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"}}' \
  -w "\nHTTP %{http_code}\n"
```
**Expected:** 404 (flag off) or 501 (flag on, template not implemented).
**Pass / Fail:** [ ]

### F-8 — Auth required
**Steps:** Same as F-1 but drop `Authorization` header.
**Expected:** HTTP 401.
**Pass / Fail:** [ ]

---

## D. Frontend UI

### FE-1 — Toggle visible when flag ON + company_profile selected
**Goal:** Format toggle appears at Step 2.
**Steps:**
1. `cd frontend/aminra-web && npm run dev`
2. Browser → `http://localhost:3100/create-document` → login if needed
3. Step 1: select **Company Profile** only → click Tiếp theo
4. Step 2: scroll past language section
**Expected:** New section "Định dạng tài liệu" with two cards: DOCX (default selected) + PDF (đẹp).
**Pass / Fail:** [ ]
**If toggle missing:** verify SETUP-6 done; check `useFeature` hook returns true via DevTools React profiler.

### FE-2 — Toggle hidden when flag OFF
**Steps:**
1. Disable flag: `UPDATE tenant_feature_overrides SET enabled=FALSE WHERE tenant_id='$TENANT_ID' AND feature_name='pdf_html_renderer_v1.company_profile';`
2. Reload `/create-document`, repeat Step 1+2.
**Expected:** Toggle absent; fallback to original DOCX-only flow.
**Pass / Fail:** [ ]
**Cleanup:** re-enable flag for subsequent tests.

### FE-3 — Click PDF → file downloads
**Steps:**
1. Step 1 select Company Profile, Step 2 select PDF, click "Tạo 1 file PDF"
2. Browser download bar appears
3. Open downloaded `company_profile_<name>.pdf`
**Expected:** Same PDF as F-1 (cover page, Inter font, watermark, 3+ sections); file name has company name slug.
**Pass / Fail:** [ ]

### FE-4 — Mixed selection: company_profile + halal_policy + PDF chosen
**Goal:** Warning text shown; halal_policy silently downloads as DOCX.
**Steps:**
1. Step 1 select **Company Profile** AND **Halal Policy** (or any 2nd item) → Tiếp theo
2. Step 2 select PDF format
**Expected:**
- Amber notice: "Lưu ý: PDF mới hiện chỉ hỗ trợ Company Profile..."
- Click "Tạo 2 file" → 2 files: 1× PDF (company_profile), 1× DOCX (halal_policy)
**Pass / Fail:** [ ]

### FE-5 — Lang switch en
**Steps:** Step 2 lang = English, format = PDF, Tạo.
**Expected:** PDF renders with `<html lang="en">`; section heading text remains Vietnamese (template not yet i18n'd in Phase 1; this is documented Phase 2 deferral).
**Pass / Fail:** [ ]

### FE-6 — Fallback DOCX when backend disabled mid-session
**Steps:**
1. With flag ON, navigate to Step 2 (toggle visible)
2. Disable flag in DB (FE-2 cleanup style)
3. Click "Tạo 1 file PDF"
**Expected:** Backend returns 404 → frontend silent fallback DOCX → user gets `.docx`. No toast error.
**Pass / Fail:** [ ]
**Cleanup:** re-enable flag.

---

## E. Security

### SEC-1 — XSS payload escaped in PDF
**Goal:** Verify Jinja2 autoescape (threat-model R2).
**Steps:**
```bash
curl -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "<script>alert(1)</script>BadCo", "issued_date": "2026-05-05"}}' \
  -o /tmp/xss.pdf
pdftotext /tmp/xss.pdf - | grep -i "script\|alert"
```
**Expected:** Text shows literal `<script>alert(1)</script>BadCo` (escaped) in PDF; no execution side effect (would be invisible anyway since JS disabled, but verify text is preserved as-is).
**Pass / Fail:** [ ]

### SEC-2 — cfg_override rejected for non-admin
**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"},
       "cfg_override": {"confidential_label": "FAKE OFFICIAL"}}' \
  -w "\nHTTP %{http_code}\n"
```
**Expected:** HTTP 403; audit log row `document.pdf_render_denied` with reason `cfg_override_non_admin`.
**Verify audit log:**
```bash
docker compose exec postgres psql -U aminra -d aminra -c \
  "SELECT action, metadata FROM audit_logs WHERE action='document.pdf_render_denied' ORDER BY created_at DESC LIMIT 1;"
```
**Pass / Fail:** [ ]

### SEC-3 — Path traversal in doc_type → 422 / 404
**Steps:**
```bash
curl -s -X POST "http://localhost:8000/api/templates/..%2F..%2Fetc/render-pdf" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"}}' \
  -w "\nHTTP %{http_code}\n"
```
**Expected:** 422 (FastAPI Path regex rejects) or 404. Never 500 / file leak.
**Pass / Fail:** [ ]

### SEC-4 — Rate limit fires
**Goal:** 11th request in 60s window → 429.
**Steps:**
```bash
for i in $(seq 1 12); do
  echo -n "$i: "
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
    -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
    -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"}}'
done
```
**Expected:** First 10 → 200, 11+ → 429 with `Retry-After`.
**Pass / Fail:** [ ]

### SEC-5 — Audit log written for every successful render
**Steps (after F-1):**
```bash
docker compose exec postgres psql -U aminra -d aminra -c \
  "SELECT action, entity_id, metadata->'byte_size', metadata->'duration_ms'
   FROM audit_logs WHERE action='document.pdf_rendered'
   ORDER BY created_at DESC LIMIT 5;"
```
**Expected:** Row per render with byte_size + duration_ms populated.
**Pass / Fail:** [ ]

### SEC-6 — PDF metadata stripped (no Chrome version leak)
**Steps:**
```bash
pdfinfo /tmp/company_profile.pdf | grep -iE "creator|producer|created"
```
**Expected:**
- `Producer: AMINRA Halal Cert Platform`
- `CreationDate: D:00010101000000Z` or similar epoch
- No `Chrome` / `Chromium` / `Skia` strings
**Pass / Fail:** [ ]

### SEC-7 — Browser network outbound blocked at render time
**Goal:** Templates cannot fetch external URLs (R3 SSRF defence).
**Steps:**
```bash
docker compose exec backend bash -c \
  "curl -m 3 http://169.254.169.254/ 2>&1 | head -3; \
   curl -m 3 http://example.com/ 2>&1 | head -3"
```
**Expected:** Both timeout / network unreachable / DNS fail. (If unrestricted, document as known gap pending docker-compose network policy hardening — not a Phase 1 blocker but flag.)
**Pass / Fail:** [ ]
**Note:** If outbound is open, **CSP + offline=True browser context** still block fetches inside Chromium — defense in depth.

### SEC-8 — CSP header injected in rendered HTML
**Goal:** Verify the inline meta-CSP reaches the browser at render time.
**Steps:** Add temporary debug log in `pdf_renderer.py:_render_html` to print first 200 chars of HTML, OR run with breakpoint, OR test indirectly: payload in body that uses inline event handler shouldn't execute (already covered by SEC-1).
**Expected:** HTML output includes `Content-Security-Policy` meta tag.
**Pass / Fail:** [ ]

---

## F. Performance

### P-1 — Cold render (first request after restart)
**Steps:**
```bash
docker compose restart backend
sleep 5
time curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d "$(jq -n --argfile d backend/tests/fixtures/pdf_render/company_profile/sample.json \
       '{data: $d, is_draft: true}')" \
  -o /tmp/cold.pdf
```
**Expected:** Real time < 5s (target from spec §9).
**Pass / Fail:** [ ] — record actual: ___ s

### P-2 — Warm render (browser reused)
**Steps (immediately after P-1):** repeat the same curl, time it.
**Expected:** Real time < 1.5s.
**Pass / Fail:** [ ] — record actual: ___ s

### P-3 — Concurrent 5 renders
**Steps:**
```bash
seq 1 5 | xargs -P 5 -I{} bash -c '
  time curl -s -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
    -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
    -d "$(jq -n --argfile d backend/tests/fixtures/pdf_render/company_profile/sample.json \
         "{data: \$d, is_draft: true}")" \
    -o /tmp/conc_{}.pdf
'
ls -lh /tmp/conc_*.pdf
sha256sum /tmp/conc_*.pdf
```
**Expected:**
- All 5 succeed
- SHA-256 of all 5 identical (deterministic output)
- Total wall time < 8s (3 contexts × ~1.5s + 2 queued × ~1.5s)
- Health check during the run shows `contexts_busy: 3, queue_depth: 2`
**Pass / Fail:** [ ]

---

## G. Error / fallback behavior

### E-1 — Browser pool exhaust → 503
**Steps:**
```bash
seq 1 20 | xargs -P 20 -I{} curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://localhost:8000/api/templates/company_profile/render-pdf \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"data": {"business_name": "x", "issued_date": "2026-05-05"}}' \
  | sort | uniq -c
```
**Expected:** Mix of 200 (succeed) + 503 (queue full) + possibly 429 (rate limit). No 500.
**Note:** Rate limit may fire before queue exhaust — that's also acceptable.
**Pass / Fail:** [ ]

### E-2 — Render timeout (simulated by huge content)
**Steps:** POST with `business_name` of 10000 chars.
**Expected:** 400 (validation max_length 200) before reaching renderer.
**Pass / Fail:** [ ]

### E-3 — Renderer down → frontend graceful fallback
**Steps:**
1. `docker compose stop backend` (or break renderer by `kill` chromium PID inside container)
2. From frontend: click PDF generate
**Expected:** Fetch fails → frontend shows error toast / surfaces Error in UI. Does NOT silently send DOCX (user explicitly chose PDF).
**Pass / Fail:** [ ]
**Note:** Current `generatePdfFallbackDocx` only falls back on 404/501. Network failure throws. Acceptable behaviour — document.

### E-4 — Frontend with stale flag cache
**Steps:**
1. With flag OFF, load Step 2 — toggle absent
2. Enable flag in DB
3. Wait 60s+ (TTL_MS in featureFlags.tsx) OR call `invalidateFeatureFlagCache()`
4. Reload page
**Expected:** Toggle appears. (If not after 60s + reload, flag cache too aggressive — file as 🐛.)
**Pass / Fail:** [ ]

### E-5 — Migration 022 idempotency
**Steps:**
```bash
bash scripts/db-migrate.sh upgrade head    # already at head
bash scripts/db-migrate.sh downgrade -1
docker compose exec postgres psql -U aminra -d aminra -c \
  "SELECT count(*) FROM feature_flags WHERE name LIKE 'pdf_html_renderer_v1.%';"
bash scripts/db-migrate.sh upgrade head
docker compose exec postgres psql -U aminra -d aminra -c \
  "SELECT count(*) FROM feature_flags WHERE name LIKE 'pdf_html_renderer_v1.%';"
```
**Expected:** After downgrade: 0; after re-upgrade: 13.
**Pass / Fail:** [ ]

---

## H. Manual visual review (designer eye)

For F-1 output PDF, verify by eye:

- [ ] Inter font visible (not Times New Roman fallback) — bold weights distinct
- [ ] Cover page title legible at A4 print scale (preview at 100%)
- [ ] Watermark "DRAFT" visible but light, doesn't obscure text
- [ ] Tables: header row with subtle background, no overflow
- [ ] Footer page number visible bottom-right of every page (not first)
- [ ] No widow/orphan: section headings not orphaned at page bottom
- [ ] Vietnamese diacritics render correctly (`đ`, `ơ`, `ư`, tone marks)
- [ ] Brand color: navy `#0a1f44` for headings, halal-green `#16a34a` for accent
- [ ] Logo SVG sharp at any zoom level (vector, not raster)
- [ ] No console error in `docker compose logs backend` during render

**Pass / Fail:** [ ]

---

## I. Demo dress-rehearsal checklist (10 min before investor demo)

1. [ ] `docker compose ps` — all services `Up`
2. [ ] Health: SM-1 returns `browser: ok`
3. [ ] Open `localhost:3100/create-document` in fresh incognito → login
4. [ ] Select Company Profile → Tiếp theo → choose PDF → Tạo
5. [ ] PDF downloads, opens in PDF viewer with no error
6. [ ] Visual: 3 quick eyeballs (font, watermark, table)
7. [ ] Print 1 page on physical printer (catches color profile / margin issues)
8. [ ] Test on slowest demo laptop (founder's vs investor's screen)
9. [ ] Network DevTools: render call < 3s on warm path
10. [ ] Have backup ready: if PDF route fails mid-demo, switch toggle to DOCX (graceful fallback proves robustness)

---

## J. Test result tracking

After running, fill in:

| Section | Tests Run | Pass | Fail | Skip | Bugs Filed |
|---|---|---|---|---|---|
| A. Setup | 6 | | | | |
| B. Smoke | 3 | | | | |
| C. Functional API | 8 | | | | |
| D. Frontend UI | 6 | | | | |
| E. Security | 8 | | | | |
| F. Performance | 3 | | | | |
| G. Error/fallback | 5 | | | | |
| H. Visual | 1 | | | | |
| **Total** | **40** | | | | |

**Demo readiness gate:** Section A (all 6) + B (all 3) + C-1 + D-3 + H **all green** is the minimum. Sec/Perf failures should be triaged but don't block a controlled investor demo *if* documented as known caveats.

After all tests, copy outcomes into `test-report.md` (Phase 5 deliverable).
