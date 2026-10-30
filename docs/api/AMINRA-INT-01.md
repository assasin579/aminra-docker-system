---
project: aminra
document_id: AMINRA-INT-01
version: 1.0.0
status: draft_for_review
last_updated: 2026-10-30
owner_role: "Integration Lead"
reviewer_role: "Tech Lead, Security, bên tích hợp"
approver: not_assigned
classification: internal_controlled
baseline: serving_source_snapshot_2026_10_30
---

# AMINRA INT-01 Hợp đồng API và liên thông hệ thống

**Phiên bản:** 1.0.0 | **Ngày:** 30/10/2026 | **Trạng thái:** Bản thảo trình duyệt.

**Chủ trì đề xuất:** Integration Lead. **Rà soát đề xuất:** Tech Lead, Security, bên tích hợp. Chưa phân công cá nhân hoặc ký duyệt. Các yêu cầu dưới đây là baseline đề xuất; mô tả hiện trạng được chỉ rõ riêng.

## 1. Analysis

Đây là hợp đồng nguyên tắc và catalog tham chiếu cho tích hợp. endpoint-inventory.csv được trích tĩnh từ app/router của snapshot; chưa là OpenAPI xác nhận trên runtime. Path nội bộ và path public qua proxy cần đối chiếu từng environment; baseline báo cáo có đường /api/api/submissions/cb-performance.

## 2. Solution

### Quy tắc hợp đồng

Mỗi operation phải mô tả method/path, auth, resource scope, request/response schema, lỗi, limit, side effect và tương thích. API không dùng token trong URL mới; legacy query-token cần đánh giá/rà soát trước khi tích hợp. Không đưa credential mẫu có thật vào hướng dẫn.

### Nhóm endpoint quan trọng

app.py include submission router tại /api/submissions và certificate router cùng prefix; decision router tại /api/certification-decisions; dossier router có hai mount /dossiers và /api/dossiers. Catalog ghi mount quan sát; reverse proxy có thể thêm prefix ngoài. Integration test phải chứng minh effective public URL, không tự loại một /api vì thấy trùng.

Xác thực dùng bearer/flow tương ứng đã được duyệt; client nhận 401 phải xử lý phiên đăng nhập và không lặp mutation vô hạn. 403 là thiếu quyền, 404 theo resource scope, 409 là xung đột, 422 là validation khi framework dùng. Mỗi route có thể có mã cụ thể khác; OpenAPI/runtime là hợp đồng phải chốt trước đối tác sử dụng.

### Retry và đồng bộ

Chỉ retry lỗi transient với backoff, jitter và deadline. Mutation phải có idempotency hoặc reconciliation key được operation hỗ trợ; không giả định mọi POST idempotent. Timeout sau request cần query trạng thái trước gửi lại. Webhook hoặc event liên thông phải có event_id, schema_version, occurred_at, chữ ký/xác thực, replay policy và DLQ nếu được triển khai; hiện chưa tuyên bố webhook dùng được.

### Dữ liệu chia sẻ

Mỗi đối tác có mục đích, danh mục trường, căn cứ, owner, tần suất, phương thức nhận/xóa, giới hạn lưu giữ và quy trình sự cố. Mặc định không chia sẻ công thức/SOP/audit đầy đủ qua public verify. Không tự mở kết nối cơ quan quản lý khi chưa có thỏa thuận.

### Versioning

Thay đổi phá vỡ schema/semantics cần version hoặc giai đoạn tương thích có lịch được duyệt. Nullable response phải được client chấp nhận khi schema cho phép; mock thiếu field không thay thế fixture có null thật.

## 3. Risks

Catalog tĩnh có thể chứa route không reachable do conditional imports hoặc prefix lồng. Xuất OpenAPI không được import app tùy tiện ở host vì có side effect/phụ thuộc. Không gọi endpoint mutation chỉ để chứng minh tài liệu.

## 4. Tests

Contract test xác thực route, prefix, request schema, nullability, validation và lỗi. Negative tests cho wrong tenant, wrong role, expired token. Tích hợp có retry phải kiểm tra cùng request hai lần và response timeout sau commit.

## 5. Improvements

Export OpenAPI từ artifact build đã chọn bằng quy trình read-only được Ops review. Lưu spec và breaking-change diff cùng release; chủ động retire legacy alias khi có kế hoạch tương thích được ký.

### Nguồn và hồ sơ liên quan

- [app.py](../../../../Downloads/aminra-dashboard-live-20261030/source/backend/app.py)
- [certificate_router.py](../../../../Downloads/aminra-dashboard-live-20261030/source/backend/auth/certificate_router.py)
- [authentication.md](authentication.md)

**Kiểm soát thay đổi:** 1.0.0, ngày 2026-10-30: lập baseline tài liệu; chưa thay đổi kiến trúc hay phê duyệt triển khai. Quyết định mở xem [sổ quyết định](../../../all-docs/02-Projects/aminra/architecture/software-documentation/decision-register.csv).
