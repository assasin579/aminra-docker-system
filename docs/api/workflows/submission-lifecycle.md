# Submission Lifecycle — State Machine

---

## 1. Sơ đồ trạng thái

```
                     ┌─────────┐
                     │  draft  │  ← Business tạo submission, chưa nộp
                     └────┬────┘
                          │ submit (Business)
                          ▼
                    ┌───────────┐
                    │ submitted │  ← Đã nộp, chờ CB nhận
                    └─────┬─────┘
                          │ assign_auditor (ProviderAdmin)
                          ▼
                    ┌──────────┐
                    │ assigned │  ← Đã gán auditor, chờ bắt đầu review
                    └────┬─────┘
                         │ start_review (Auditor)
                         ▼
                   ┌──────────────┐
                ┌──│  reviewing   │──────────────────────────┐
                │  └──────┬───────┘                          │
                │         │ request_revision (Auditor)        │ approve_conditional (Auditor)
                │         ▼                                   ▼
                │  ┌────────────────────┐          ┌──────────────────────┐
                │  │ revision_required  │          │ conditionally_approved│
                │  └──────────┬─────────┘          └──────────┬───────────┘
                │             │ resubmit (Business)            │ final_approval (IHC)
                │             └──────────────────┐             ▼
                │                                │   ┌──────────────┐
                │                                └──►│   approved   │
                │                                    └──────┬───────┘
                │                                           │ issue_certificate (ProviderOwner)
                │                                           ▼
                │                                   ┌──────────────┐
                │                                   │  finalized   │  ← Cert đã cấp
                │                                   └──────────────┘
                │
                │ reject (ProviderOwner / IHC)
                ▼
          ┌──────────┐
          │ rejected │
          └──────────┘
```

---

## 2. Transition matrix (49 cells — phần quan trọng)

| From \ To | submitted | assigned | reviewing | revision_required | conditionally_approved | approved | finalized | rejected |
|---|---|---|---|---|---|---|---|---|
| draft | ✅ Business | | | | | | | |
| submitted | | ✅ ProviderAdmin | | | | | | ✅ ProviderOwner |
| assigned | | | ✅ Auditor | | | | | |
| reviewing | | | | ✅ Auditor | ✅ Auditor | | | ✅ ProviderOwner |
| revision_required | ✅ Business | | | | | | | |
| conditionally_approved | | | | | | ✅ IHC | | ✅ IHC |
| approved | | | | | | | ✅ ProviderOwner | |

**⚠️ Bug W3-M2:** Transition matrix chưa được enforce ở tầng DB. Hiện tại backend kiểm tra trong code nhưng không có DB CHECK constraint → có thể bypass qua raw SQL.

**Fix cần làm:** Thêm DB trigger hoặc ENUM constraint để chỉ cho phép transition hợp lệ.

---

## 3. Business rules quan trọng

### Document lock khi approved
```
RULE: Khi submission.status = "approved" hoặc "finalized",
      KHÔNG được phép:
      - Upload document mới vào submission
      - Replace document hiện có
      - Xóa document

STATUS: ❌ Bug C1 — hiện tại vẫn cho phép replace-document
```

### Document ownership
```
RULE: Khi query document trong context của submission,
      PHẢI verify document.submission_id = submission.id
      VÀ submission.tenant_id = current_tenant.id

STATUS: ❌ Bug W3-M4 — replace_submission_document không validate
```

### Revision request
```
RULE: revision_required → submitted (resubmit) chỉ được phép khi:
      - Business đã upload ít nhất 1 document mới, hoặc
      - Business đã thay thế document bị yêu cầu sửa

STATUS: ⚠️ Không enforce — Business có thể resubmit mà không làm gì
```

### Scoring sau approve
```
RULE: compliance_score từ AI PHẢI được preserve khi CB approve
      CB có thể thêm comment nhưng KHÔNG ghi đè AI score bằng NULL

STATUS: ❌ Bug C2 — approve-final overwrite score với NULL
```

---

## 4. Audit log requirements

Mỗi transition phải tạo 1 record trong `audit_logs`:
```json
{
  "action": "submission.status_changed",
  "entity_type": "submission",
  "entity_id": "submission_uuid",
  "tenant_id": "tenant_uuid",
  "actor_id": "user_uuid",
  "actor_role": "Auditor",
  "details": {
    "from_status": "reviewing",
    "to_status": "revision_required",
    "reason": "Thiếu giấy tờ nhà máy"
  },
  "created_at": "2026-05-04T10:30:00Z"
}
```

---

## 5. APIs liên quan

| Action | Method | Endpoint |
|---|---|---|
| Tạo submission | POST | `/auth/submissions/` |
| Lấy danh sách | GET | `/auth/submissions/` |
| Nộp hồ sơ | PUT | `/auth/submissions/{id}/submit` |
| Gán auditor | PUT | `/auth/submissions/{id}/assign-auditor` |
| Bắt đầu review | PUT | `/auth/submissions/{id}/start-review` |
| Yêu cầu bổ sung | POST | `/auth/submissions/{id}/request-revision` |
| Phê duyệt | POST | `/auth/submissions/{id}/approve` |
| Từ chối | POST | `/auth/submissions/{id}/reject` |
| Finalize | POST | `/auth/submissions/{id}/finalize` |
