# Hướng dẫn: CB Admin (Tổ chức chứng nhận)

**Roles:** ProviderOwner, ProviderAdmin

---

## Thiết lập CB trên AMINRA

1. Đăng ký tài khoản Provider
2. Điền thông tin CB: tên, giấy phép, logo, phạm vi chứng nhận
3. Thiết lập template tài liệu (yêu cầu riêng của CB)
4. Invite ProviderAdmin và Auditor
5. Cấu hình SLA (số ngày tối đa per giai đoạn)

---

## Quản lý Auditor

**ProviderAdmin có thể:**
- Invite auditor qua email
- Gán auditor vào hồ sơ cụ thể
- Theo dõi workload (số hồ sơ đang handle)
- Xem lịch sử quyết định của từng auditor

**Phân công hợp lý:**
- Không gán 1 auditor xử lý hồ sơ của business quen biết (conflict of interest)
- Phân công theo chuyên môn (food vs pharma vs cosmetics)

---

## Quyết định cuối (IHC)

Sau khi auditor recommend approve:
- `AdminIHCMember` hoặc `ProviderOwner` cần final approval
- Chỉ khi đủ IHC quorum mới cấp cert (tùy cấu hình CB)

---

## Quản lý template

CB có thể tạo template tài liệu riêng:
- Danh sách tài liệu bắt buộc theo tiêu chuẩn CB áp dụng
- Checklist evaluation cho auditor
- Template báo cáo audit

---

## Dashboard CB

- Tổng quan hồ sơ đang xử lý, overdue, pending IHC approval
- Workload auditor
- Cert sắp hết hạn (renewal pipeline)
- Analytics: approval rate, average processing time
