# API Error Codes

---

## Error response shape

```json
{
  "detail": "Human-readable message",
  "code": "MACHINE_READABLE_CODE",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Nguyên tắc:**
- `detail` cho user/developer đọc hiểu
- `code` để frontend handle programmatically
- Không bao giờ leak stack trace, file path, hay DB error message trong production

---

## HTTP Status codes

| Status | Khi nào dùng |
|---|---|
| `200 OK` | Request thành công, có body |
| `201 Created` | Tạo resource thành công |
| `204 No Content` | Thành công, không có body (ví dụ: DELETE) |
| `400 Bad Request` | Input không hợp lệ (logic business, không phải schema) |
| `401 Unauthorized` | Không có hoặc token invalid/expire |
| `403 Forbidden` | Có token nhưng không đủ quyền |
| `404 Not Found` | Resource không tồn tại HOẶC không thuộc tenant này |
| `409 Conflict` | Duplicate (cert number, email đã đăng ký) |
| `422 Unprocessable Entity` | Pydantic validation fail |
| `429 Too Many Requests` | Rate limit exceeded |
| `500 Internal Server Error` | Lỗi không expected — log và alert |

**⚠️ Lưu ý 404 vs 403:** Khi user query resource của tenant khác, trả `404` (không phải `403`) để không leak sự tồn tại của resource.

---

## Error codes tùy chỉnh

| Code | HTTP | Mô tả |
|---|---|---|
| `AUTH_TOKEN_EXPIRED` | 401 | JWT đã hết hạn |
| `AUTH_TOKEN_INVALID` | 401 | JWT không hợp lệ (sai secret, sai format) |
| `AUTH_INSUFFICIENT_ROLE` | 403 | Role không đủ quyền cho action này |
| `SUBMISSION_INVALID_TRANSITION` | 400 | Status transition không hợp lệ theo state machine |
| `SUBMISSION_LOCKED` | 400 | Submission đã approved/finalized — không thể thay đổi |
| `DOCUMENT_HASH_MISMATCH` | 400 | Document hash không khớp — file bị tamper |
| `CERT_NUMBER_CONFLICT` | 409 | Cert number đã tồn tại (race condition) |
| `FILE_TOO_LARGE` | 400 | File vượt quá giới hạn (20MB FE / 50MB BE) |
| `FILE_TYPE_INVALID` | 400 | MIME type không được chấp nhận |
| `TENANT_NOT_FOUND` | 404 | Tenant không tồn tại hoặc không active |
| `RATE_LIMIT_EXCEEDED` | 429 | Quá nhiều request |
| `LLM_EVALUATION_FAILED` | 500 | AI evaluation thất bại (có retry) |
