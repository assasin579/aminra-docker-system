# Certification Lifecycle

---

## 1. Trạng thái chứng nhận

```
          ┌─────────────────┐
          │    pending      │  ← Cert đang được tạo (PDF generation)
          └────────┬────────┘
                   │ issued
                   ▼
          ┌─────────────────┐
          │     active      │  ← Cert hợp lệ, QR verify = valid
          └────────┬────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
  expire()   revoke()    suspend()
       │           │           │
       ▼           ▼           ▼
  ┌─────────┐ ┌─────────┐ ┌──────────┐
  │ expired │ │ revoked │ │suspended │
  └─────────┘ └─────────┘ └────┬─────┘
                                │ reinstate()
                                ▼
                           ┌─────────┐
                           │  active │
                           └─────────┘
```

---

## 2. Cert number format

```
HALAL-{YYYY}-{NNNN}
Ví dụ: HALAL-2026-0001

YYYY: năm cấp
NNNN: số thứ tự 4 chữ số, bắt đầu từ 0001 mỗi năm
```

**⚠️ Bug C10:** Hiện tại cert number generation có race condition — 2 requests đồng thời có thể tạo cùng số. Fix: dùng PostgreSQL SEQUENCE hoặc SELECT FOR UPDATE.

---

## 3. Public verification

Bất kỳ ai cũng có thể verify cert qua QR code:

```
GET /auth/certificates/verify/{cert_id}

Response (valid):
{
  "cert_number": "HALAL-2026-0001",
  "business_name": "Công ty TNHH ABC",
  "product_scope": "Bánh kẹo, đồ uống",
  "issued_by": "HALCERT",
  "issued_date": "2026-01-15",
  "expiry_date": "2027-01-14",
  "status": "active",
  "hash_valid": true
}

Response (invalid / revoked):
{
  "status": "revoked",
  "revoked_date": "2026-03-01",
  "hash_valid": false    ← nếu cert bị tamper
}
```

---

## 4. Blockchain anchoring

Sau khi cert được issue, arq worker anchor cert hash lên blockchain:

```
1. Collect cert hashes (có thể batch nhiều cert)
2. Build Merkle tree từ hashes
3. Submit Merkle root lên:
   - Bitcoin (OP_RETURN transaction)
   - Polygon (smart contract)
4. Lưu txid + block_number vào cert record
```

Mục đích: bất kỳ ai cũng có thể độc lập verify cert không bị giả mạo bằng cách:
1. Hash cert document
2. Verify Merkle proof trên blockchain
3. So sánh với Merkle root trong blockchain tx

---

## 5. Cert renewal

```
Trước khi cert expire 60 ngày: hệ thống tự động gửi reminder
Business khởi tạo renewal submission → quy trình giống submission mới
CB có thể expedited review nếu không có thay đổi nguyên liệu/quy trình
```

---

## 6. Revocation

```
POST /auth/certificates/{cert_id}/revoke
Body: { "reason": "Phát hiện nguyên liệu không Halal" }

⚠️ Bug C4: Hiện tại cert_decision revoke đang revoke TẤT CẢ cert
của business đó across providers — cross-provider write leak.
Fix cần: chỉ revoke cert trong scope của provider đang thực hiện.
```
