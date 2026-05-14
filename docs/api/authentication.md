# API Authentication & Authorization

---

## 1. Token flow

```
POST /auth/business/login   (hoặc /auth/provider/login)
Body: { "email": "...", "password": "..." }

Response:
{
  "access_token": "eyJ...",      ← JWT HS256, expire 8h
  "refresh_token": "eyJ...",     ← JWT, expire 7d
  "token_type": "bearer"
}
```

**Sử dụng:**
```http
Authorization: Bearer eyJ...
```

**⚠️ Không được phép:** Đặt token trong URL querystring, localStorage, hay Cookie không httpOnly. Đây là security bug C5 đang được fix.

---

## 2. Refresh token

```
POST /auth/refresh
Body: { "refresh_token": "eyJ..." }

Response: { "access_token": "eyJ...", "token_type": "bearer" }
```

Refresh token không được refresh lại — khi refresh token expire, user phải login lại.

---

## 3. JWT Claims

```json
{
  "sub": "user_uuid",
  "tenant_id": "tenant_uuid",
  "role": "BusinessOwner",
  "type": "business",         ← "business" | "provider" | "admin"
  "exp": 1746000000,
  "iat": 1745971200
}
```

**Backend sử dụng `tenant_id` từ JWT** — không nhận từ URL hay body. Đây là foundation của schema-per-tenant isolation.

---

## 4. RBAC — Roles và quyền

### Business Portal

| Role | Quyền |
|---|---|
| `BusinessOwner` | Tạo/xóa submission, upload/xóa document, invite member, xem cert |
| `BusinessMember` | Upload document, xem submission (không tạo, không xóa, không finalize) |

### Provider Portal (CB)

| Role | Quyền |
|---|---|
| `ProviderOwner` | Cấu hình CB, quản lý ProviderAdmin, approve cert cuối |
| `ProviderAdmin` | Gán auditor, xem hồ sơ, quản lý template |
| `Auditor` | Nhận assign, review hồ sơ, chấm điểm, request revision, recommend approve |
| `AdminIHCMember` | Xem cross-provider analytics (AMINRA internal) |

### Admin Portal

| Role | Quyền |
|---|---|
| `Admin` | Quản lý tất cả tenant, feature flags, audit logs platform, analytics |

---

## 5. Dependency functions (FastAPI)

```python
# Trong backend/auth/:

# Yêu cầu user đã đăng nhập (bất kỳ role):
Depends(get_current_user)

# Yêu cầu role cụ thể:
Depends(require_business_owner)
Depends(require_provider_owner)
Depends(require_auditor)
Depends(require_admin)
```

**⚠️ Lưu ý cho reviewer:** Mọi endpoint mới phải có ít nhất `Depends(get_current_user)`. Endpoint trả dữ liệu tenant phải có thêm ownership check.

---

## 6. Error responses

| HTTP | Tình huống |
|---|---|
| `401 Unauthorized` | Không có token, token expire, token invalid |
| `403 Forbidden` | Có token hợp lệ nhưng không đủ quyền |
| `422 Unprocessable Entity` | Request body không hợp lệ (Pydantic validation) |

---

## 7. Admin authentication

**Known issue (tech debt #5 từ phase-0-closeout):** Admin hiện dùng session token (khác với JWT của business/provider). Gây ra mismatch khi test. Fix pending.
