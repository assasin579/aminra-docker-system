# Template — Company Profile (v1)

Designer notes for `templates_html/company_profile/v1/`.

## Data shape

Defined by Pydantic schema `services.schemas.pdf_render.CompanyProfileData`. Contract:

- `business_name: str` (required, ≤ 200 chars)
- `business_name_en: str | None` (≤ 200)
- `tax_code: str` (required, regex `^[0-9]{10}(-[0-9]{3})?$` — VN MST format)
- `address: str` (required, ≤ 300)
- `factory_address: str | None` (≤ 300, defaults to `address` if missing)
- `representative: str | None` (≤ 100)
- `founded_year: int | None` (≥ 1900, ≤ current_year)
- `employee_count: int | None` (≥ 0, ≤ 100000)
- `charter_capital: str | None` (≤ 100, free-form string with currency)
- `phone, email, website: str | None`
- `issued_date: str` (required, ISO `YYYY-MM-DD` rendered locale)
- `business_activities: list[str]` (≤ 50 items, each ≤ 200 chars)
- `products: list[Product]` (≤ 100 items)
  - `Product = { name: str, description: str|None, annual_output: str|None }`
- `halal_commitment: str | None` (≤ 2000)
- `halal_responsible_person: { name, title, email } | None`

`cfg` shape (loaded from `admin_templates/company_profile.json`):
- `confidential_label: str | None` (e.g., "HỒ SƠ DOANH NGHIỆP")
- `doc_type_label: str` (default "Company Profile")
- `cover_meta: list[{key, value}]`
- `custom_sections: list[{title, content}]`
- `show_approval_block: bool`

`content: str | None` — free-form additional content from the form (rendered as paragraphs).

## Render command (local dev)

```bash
# From repo root, with backend dependencies installed:
cd backend
python -m services.pdf_renderer_cli company_profile \
  --fixture tests/fixtures/pdf_render/company_profile/sample.json \
  --out /tmp/company_profile.pdf
xdg-open /tmp/company_profile.pdf
```

## Layout invariants

| Element | Rule |
|---|---|
| Cover page | Always 1 full A4 page, ends with `page-break-after: always` |
| Section headings | `<h2>` with anchor `#section-1`, `#section-2`, ... |
| Tables | First column is the label (32% width on product table), bordered bottom only |
| Page break | Avoid inside `<tr>`, `<table>`, `.callout`, `.cover__approval` |

When updating layout, run visual regression suite (`pytest tests/visual/test_company_profile_pdf.py`)
and inspect diff against baseline. If intentional, update baseline + bump version (`v1` → `v2`)
and keep `v1` available via `?template_version=v1` for rollback.

## Anti-patterns (caught by linter)

- ❌ `<img src="https://...">` — external load disallowed (CSP + linter)
- ❌ `<script>` — CSP `script-src 'none'`
- ❌ `<link rel="stylesheet" href="https://...">` — only `{{ asset() }}` allowed
- ❌ Inline JavaScript event handlers (`onclick`, `onload`)
