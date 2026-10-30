---
project: aminra
document_id: AMINRA-USR-01
version: 1.0.0
status: draft_for_review
last_updated: 2026-10-30
owner_role: "Product và Training Lead"
reviewer_role: "DN, CB, QA"
approver: not_assigned
classification: internal_controlled
baseline: serving_source_snapshot_2026_10_30
---

# AMINRA USR-01 Hướng dẫn sử dụng và kế hoạch đào tạo

**Phiên bản:** 1.0.0 | **Ngày:** 30/10/2026 | **Trạng thái:** Bản thảo trình duyệt.

**Chủ trì đề xuất:** Product và Training Lead. **Rà soát đề xuất:** DN, CB, QA. Chưa phân công cá nhân hoặc ký duyệt. Các yêu cầu dưới đây là baseline đề xuất; mô tả hiện trạng được chỉ rõ riêng.

## 1. Analysis

Hướng dẫn này mô tả tác vụ lõi và cách xử lý ngoại lệ theo vai trò. Các guide cũ có thể dùng chức danh/trạng thái khác code hiện hành; dùng thao tác và quyền thực tế của release được nghiệm thu làm chuẩn. Không khẳng định tính năng chỉ vì được nhắc trong guide.

## 2. Solution

### Doanh nghiệp

Đăng nhập qua cổng phù hợp và kiểm đúng tổ chức trước nhập dữ liệu. Mở dossier, kiểm tiêu chuẩn/phiên bản và danh mục tài liệu. Tải đúng tài liệu theo loại yêu cầu; kiểm trạng thái lưu sau reload. Chỉ nộp khi dữ liệu thuộc cùng dossier và các điều kiện được đáp ứng. Khi CB yêu cầu bổ sung, đọc phản hồi theo tài liệu, tạo bản bổ sung và nộp lại theo luồng được phép.

Điểm AI là gợi ý. UNKNOWN nghĩa là chưa đủ dữ liệu/binding để kết luận, không phải 0% đạt hoặc được miễn. Không sửa trực tiếp hồ sơ đã được khóa; liên hệ CB để mở quy trình thay đổi phù hợp.

### Auditor

Kiểm đúng CB và hồ sơ được phân công. Ghi review có lý do, tài liệu/version và bằng chứng liên quan. Khi dùng mobile offline, kiểm trạng thái chưa đồng bộ/đã server xác nhận; không coi dữ liệu chỉ có trên thiết bị là đã nộp. Hoàn tất và gửi báo cáo theo quy trình; không tự chấp nhận báo cáo của mình nếu không có quyền.

### CB Owner và người quyết định

Quản lý phân công và xung đột lợi ích; xác minh báo cáo trước acceptance. Team performance chỉ tính báo cáo được chấp nhận theo định nghĩa, không dựa completed. Kiểm tra đủ các gate độc lập trước cấp chứng chỉ. Thu hồi phải có lý do và kiểm lại public verify. Danh tính/role được cấp qua quy trình identity; không chia sẻ tài khoản owner.

### Platform Admin và công chúng

Admin công bố requirements version theo quyền; version mới không sửa binding dossier cũ. Admin vận hành không thay CB quyết định chuyên môn. Công chúng scan QR/tra cứu và đọc trạng thái hiện tại, issuer, phạm vi và hiệu lực được phép công khai; không suy từ hash proof rằng chứng chỉ còn hiệu lực.

### Hỗ trợ và đào tạo

Khi báo lỗi ghi thời điểm, màn hình, mã hồ sơ/request ID nếu có và bước thực hiện; che dữ liệu mật, không gửi mật khẩu/token. Đào tạo gồm bài tập riêng cho DN, auditor, owner và Admin, kèm revision/revoke/offline và nhận biết AI. Training Lead kiểm người học hoàn thành tác vụ bằng dữ liệu tổng hợp; lưu attendance và kết quả. Kênh hỗ trợ và lịch được chốt D15.

## 3. Risks

Screenshot phải khớp build và không lộ khách hàng/tài khoản thật. Quản trị viên không hướng dẫn workaround vượt quyền. Chưa có UAT thiết bị thật thì không công bố đầy đủ khả năng offline trên mọi thiết bị.

## 4. Tests

Người mới thực hiện bài tập không có tác giả hỗ trợ trực tiếp; QA kiểm kết quả và điểm mắc. Test bàn phím, ngôn ngữ, RTL và thông báo lỗi theo phạm vi D11. Screenshot chỉ bổ sung sau khi chốt release/UI.

## 5. Improvements

Duy trì guide cùng feature PR và dùng video/screenshot có build/date. Cập nhật guide cũ qua review riêng thay vì âm thầm thay đổi quyền hoặc quy trình đã được CB áp dụng.

### Nguồn và hồ sơ liên quan

- [business-user.md](business-user.md)
- [cb-admin.md](cb-admin.md)
- [auditor.md](auditor.md)
- [platform-admin.md](platform-admin.md)
- [report.txt](../../../../Downloads/aminra-dashboard-live-20261030/report.txt)

**Kiểm soát thay đổi:** 1.0.0, ngày 2026-10-30: lập baseline tài liệu; chưa thay đổi kiến trúc hay phê duyệt triển khai. Quyết định mở xem [sổ quyết định](../../../all-docs/02-Projects/aminra/architecture/software-documentation/decision-register.csv).
