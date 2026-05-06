# SOP template (shared by 6 sop_* doc_types)

`sop_raw_material_receiving`, `sop_storage_segregation`,
`sop_production_operation`, `sop_cleaning_sanitation`,
`sop_handling_nonconformances`, `sop_complaint_recall` all render through
`sop/v1/template.html`. Per-variant differences live in
`admin_templates/<doc_type>.json` (`docx_config` block):

```json
{
  "docx_config": {
    "doc_type_label":  "SOP — Tiếp nhận nguyên liệu Halal",
    "sop_id_default":  "SOP-RAW-001",
    "purpose_default": "Quy định cách tiếp nhận nguyên liệu...",
    "scope_default":   "Áp dụng cho hoạt động kho nhập...",
    "approved_by_default": "Tổng giám đốc",
    "show_approval_block": true
  }
}
```

## Data shape (Pydantic `SopData`)

Required:
- `business_name` (≤ 200)
- `effective_date` — ISO date
- `issued_date` — ISO date

Optional (template renders `—` when absent):
- `sop_id` (regex `^[A-Z0-9\-]+$`), `title`, `version`
- `purpose`, `scope` (≤ 1500 chars each)
- `responsibilities[]` of `{role, duties}`
- `references[]` (free text bullets)
- `definitions[]` of `{term, definition}`
- `procedure_steps[]` of `{step_no, action, responsible_role?, records?, criteria?}`
- `records[]`, `appendices[]`
- `review_date`, `approved_by`

## Sections rendered

| # | Section | Source (data → cfg fallback) |
|---|---|---|
| 01 | Mục đích | `data.purpose` → `cfg.purpose_default` |
| 02 | Phạm vi áp dụng | `data.scope` → `cfg.scope_default` |
| 03 | Trách nhiệm | `data.responsibilities[]` (omitted if empty) |
| 04 | Tài liệu liên quan | `data.references[]` (omitted if empty) |
| 05 | Định nghĩa | `data.definitions[]` (omitted if empty) |
| 06 | Quy trình thực hiện | `data.procedure_steps[]` (omitted if empty) |
| 07 | Hồ sơ lưu trữ | `data.records[]` (omitted if empty) |
| 08 | Phụ lục | `data.appendices[]` (omitted if empty) |
| 09 | Phê duyệt | `data.{effective_date,review_date,approved_by,issued_date}` |

## Render command

```bash
make preview doc=sop_raw_material_receiving
```
