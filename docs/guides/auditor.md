# Hướng dẫn: Auditor

**Role:** Auditor (thuộc CB/Provider)

---

## Quy trình làm việc

```
1. Nhận thông báo được assign vào hồ sơ
        ↓
2. Xem xét hồ sơ và AI evaluation
        ↓
3. Kiểm tra từng tài liệu
        ↓
4. Ghi nhận checklist evaluation
        ↓
5a. Hồ sơ đạt → Recommend approve → IHC phê duyệt cuối
5b. Cần bổ sung → Gửi revision request cho business
5c. Không đạt → Recommend reject → ProviderOwner confirm
```

---

## Checklist đánh giá hồ sơ

**Tài liệu:**
- [ ] Đủ tài liệu theo danh sách yêu cầu
- [ ] Danh sách nguyên liệu đầy đủ, có CoA và Halal cert của supplier
- [ ] Flowchart quy trình rõ ràng, không có bước nghi ngờ nhiễm Haram
- [ ] Manual HAS đề cập đủ: chính sách, tanggung jawab, prosedur, rekam jejak

**Nguyên liệu:**
- [ ] Không có nguyên liệu Haram
- [ ] Nguyên liệu High Risk có Halal cert hợp lệ từ CB được công nhận
- [ ] Nguyên liệu từ heo/anjing = không được chấp nhận (Najis Mughallazah)

**Quy trình sản xuất:**
- [ ] Không có cross-contamination với nguyên liệu Haram
- [ ] Dụng cụ/thiết bị dùng riêng hoặc dicuci syariah
- [ ] Khu vực sản xuất không chia sẻ với sản phẩm Haram

---

## Sử dụng AI evaluation

- AI compliance score là **công cụ hỗ trợ**, không thay thế phán quyết của auditor
- Xem `red_flags[]` để biết điểm AI cho là rủi ro
- Auditor có thể agree hoặc override từng flag với comment
- Score sau cùng là của auditor — không phải AI

---

## Revision request

Khi cần business bổ sung:
- Ghi rõ: tài liệu nào cần bổ sung, lý do cụ thể
- Đặt deadline cụ thể
- Business sẽ nhận email + notification

---

## Không được phép

- Xem hồ sơ của CB khác (cross-provider isolation)
- Thay đổi compliance_score mà không có lý do documented
- Approve hồ sơ chưa đủ tài liệu (vi phạm quy trình CB)
