# Hướng dẫn: Platform Admin (AMINRA)

**Role:** Admin, AdminIHCMember

---

## Quản lý tenant

```
/admin/tenants

- Xem danh sách business và CB đã đăng ký
- Activate / deactivate tenant
- Xem quota usage (storage, API calls)
- Impersonate tenant (chỉ cho support, phải log action)
```

---

## Feature Flags

Feature flags cho phép bật/tắt tính năng theo tenant mà không cần redeploy.

```
/admin/feature-flags

Các flags hiện có:
- document_preview_enabled      ← Tắt khi phát hiện bug cross-tenant
- ai_evaluation_enabled         ← Tắt khi OpenRouter có vấn đề
- blockchain_anchor_enabled     ← Tắt khi node không sync
- web_push_enabled              ← Tắt khi VAPID cần rotate
- supply_chain_enabled          ← Tắt nếu module chưa stable
```

**Khi có security incident:** Tắt flag liên quan ngay để mitigate trong khi fix code.

---

## Audit Logs Platform

```
GET /auth/admin/audit-logs

Filter:
- Theo tenant_id
- Theo action type
- Theo time range
- Theo actor_id (user cụ thể)

Dùng cho:
- Điều tra incident
- Compliance audit
- Detect anomaly (user access bất thường)
```

---

## Analytics

```
/admin/analytics

- Số tenant active theo tháng
- Hồ sơ submitted / approved / rejected
- AI evaluation accuracy (nếu đo được)
- Revenue forecast (khi có billing)
```

---

## Chú ý bảo mật

- **Không impersonate** tenant nếu không có lý do support hợp lệ — mọi impersonation phải được log
- **Admin session** hiện dùng session token (khác JWT) — tech debt #5, đang fix
- **Không cấp Admin role** cho nhiều người — chỉ founder và 1 trusted person
