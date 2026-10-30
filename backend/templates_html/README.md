# templates_html — design system + PDF renderer templates

> Đây là **single source of truth** cho mọi thiết kế PDF của AMINRA. README
> này viết cho bạn của 3 tháng sau khi đã quên context. Đọc TL;DR trước.

## TL;DR

1. **KHÔNG** paste raw hex / font-size vào doc-specific `style.css` — luôn dùng `var(--c-*)` hoặc `var(--fs-*)`. Linter (`scripts/lint-templates.sh`) sẽ block commit.
2. **KHÔNG** copy-paste section opener / cover / table — dùng macros từ `_base/macros.html`.
3. Mở `tests/visual/baselines/_style_guide/page-*.png` (hoặc `make style-guide`) trước khi design — biết platform có sẵn lego nào.
4. Sau khi sửa template: `make preview doc=<name>` → review PDF → commit.
5. Sau khi sửa `_base/`: `make visual-test` → fail = re-baseline có chủ đích bằng `make visual-baseline`.

---

## Cấu trúc

```
backend/templates_html/
├── _base/
│   ├── base.css         ← ALL design tokens (3 layers L1/L2/L3)
│   ├── base.html        ← Jinja2 layout + CSP meta + asset() helper hook
│   ├── macros.html      ← Reusable components (USE THESE, don't copy HTML)
│   └── print.css        ← @page A4 + page-break rules
├── _shared/
│   ├── fonts/           ← Inter woff2 (5 weights + italic)
│   ├── logo-aminra.svg
│   ├── cover-mark.svg
│   └── watermark-draft.svg
├── _style_guide/v1/     ← Kitchen sink — render to see all components
├── _registry.py         ← doc_type → template path mapping
└── <doc_type>/v1/
    ├── template.html    ← extends _base/base.html, imports macros
    ├── style.css        ← Doc-specific overrides (L3 tokens + layout only)
    └── README.md        ← Designer notes per doc
```

---

## Available macros (the lego pieces)

Import in any template:
```jinja
{% from "_base/macros.html" import doc_cover, section_opener, stat_grid,
                                    kv_block, data_table, pull_quote,
                                    callout, bullet_list, lede %}
```

| Macro | Use for |
|---|---|
| `doc_cover(title, eyebrow, subtitle, year, meta, approval_block)` | The full-bleed gradient cover. **Required** as page 1. |
| `section_opener(num, eyebrow, title)` | Start every content section. Auto-forces page-break + giant `01/02/…` watermark. |
| `lede(text)` | Larger first-paragraph after `section_opener`. |
| `stat_grid(items, columns=4)` | 2/3/4/6-col cards of key numbers. Items = `[{"value", "label", "unit"?, "hint"?}]`. |
| `kv_block(rows)` | Key-value list (vd "Mã số thuế · 0123456789"). Skips empty values by default. |
| `data_table(columns, rows, numeric_last=False)` | Brand-styled table. Columns = `[{"label", "width"?, "align"?}]`. |
| `pull_quote(text, cite=None)` | Italic emphasised quote. |
| `callout(label, body, variant)` | Boxed notice. Variants: `info`/`success`/`warning`/`danger`/`brand`. |
| `bullet_list(items)` | Brand-coloured pill markers. |

**Rule:** add a new macro ONLY if the pattern repeats in ≥2 doc_types. One-off layout stays in the doc-specific template.

---

## Design tokens (`_base/base.css`)

### Layer 1 — Raw primitives
`--raw-navy-900`, `--raw-emerald-600`, `--raw-cream-50`, …
**Never reference these directly in templates.** Only L2 / L3 should.

### Layer 2 — Semantic
`--c-brand-primary`, `--c-brand-accent`, `--c-text`, `--c-paper`, …
**Use these in templates.** Color, typography, spacing.

### Layer 3 — Component
`--cover-bg`, `--stat-bg`, `--table-head-bg`, `--cover-title-size`, …
**Override these per doc_type if you need a variant.**

#### Adding a new color
1. Add primitive in L1 (`--raw-amber-300: #fcd34d;`)
2. Expose in L2 (`--c-brand-warn-light: var(--raw-amber-300);`)
3. (Optional) bind to L3 component (`--callout-warn-bg: var(--c-brand-warn-light);`)
4. Document in style guide (`_style_guide/v1/template.html`)
5. Re-baseline: `make visual-baseline`

---

## Add a new doc_type — checklist

```
□ Create folder: backend/templates_html/<doc_type>/v1/
□ Copy company_profile/v1/template.html as starting point
□ Edit template.html:
    - extends "_base/base.html"
    - imports macros
    - call doc_cover() + section_opener() + components
□ (optional) Add doc-specific style.css with L3 token overrides only
□ Add Pydantic schema in services/pdf_render_schemas.py
□ Register entry in templates_html/_registry.py
□ Register in SUPPORTED_DOC_TYPES dict (pdf_render_schemas.py)
□ Add fixture: backend/tests/fixtures/pdf_render/<doc_type>/sample.json
□ Add migration row for feature flag (or insert directly into feature_flags table)
□ make preview doc=<doc_type>  → eyeball
□ make visual-baseline         → record baselines
□ Add (doc_type, fixture_path) tuple to tests/visual/test_pdf_baselines.py CASES
□ make visual-test             → green
□ make lint-templates          → green
□ Commit (pre-commit will re-run linter)
```

---

## Edit existing template

| What you touched | Run |
|---|---|
| doc-specific `style.css` | `make lint-templates` then `make preview doc=<name>` |
| doc-specific `template.html` | `make preview doc=<name>`; visual baseline if intentional layout change |
| `_base/base.css` (tokens) | `make visual-test` — IF FAIL: review diff, then `make visual-baseline` if intentional |
| `_base/macros.html` | `make visual-test` — affects ALL doc_types; re-baseline if intentional |
| `_shared/fonts/` | Re-run `bash scripts/download_inter_font.sh` to verify; re-baseline |

---

## Anti-patterns (DON'T)

- ❌ `<h2>` raw — drop the rhythm of section openers; use `section_opener()`.
- ❌ `style="color: #abc"` — linter will fail; use class + token.
- ❌ `<img src="https://…">` — CSP blocks; use `{{ asset('_shared/...') }}`.
- ❌ Inline `font-size: 14pt` — token only (`var(--fs-body)`).
- ❌ `<script>` / `onclick` — CSP `script-src 'none'`; templates run with JS disabled.
- ❌ `--no-verify` on commit — linter is your sober second-pair-of-eyes.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Toggle "Định dạng tài liệu" không hiện trong frontend | Feature flag `pdf_html_renderer_v1.<doc_type>` chưa enable cho tenant |
| `404 feature ... disabled` từ API | Same — check `feature_flags` table + `tenant_feature_overrides` |
| `500 internal renderer error` | Check `docker compose logs aminra-backend` — Jinja undefined / template syntax usual suspect |
| PDF font fallback Times New Roman | CSS file:// load failed — đảm bảo render qua tmp HTML file (`page.goto(file://…)`), KHÔNG `set_content` |
| `make visual-test` fail with pixel drift > 0.5% | Either real drift (review baselines side-by-side) or font-render jitter (loosen `DIFF_THRESHOLD` chỉ khi cần) |

---

## References

- `docs/features/pdf-html-renderer/spec.md` — full feature spec
- `docs/features/pdf-html-renderer/threat-model.md` — STRIDE + 7 mitigation gates
- `docs/features/pdf-html-renderer/test-plan.md` — manual E2E test scenarios
- `services/pdf_renderer.py` — Playwright + Jinja2 + pikepdf renderer
- `auth/pdf_render_router.py` — API endpoint
