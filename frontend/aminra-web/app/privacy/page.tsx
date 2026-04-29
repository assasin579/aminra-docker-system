import Link from "next/link";

export const metadata = {
  title: "Chính sách bảo mật — AMINRA",
  description:
    "Cách AMINRA thu thập, sử dụng và bảo vệ dữ liệu cá nhân của bạn.",
};

const LAST_UPDATED = "2026-04-25";

export default function PrivacyPage() {
  return (
    <article
      className="max-w-3xl mx-auto px-6 py-12 prose prose-slate"
      data-page
    >
      <header className="mb-8">
        <Link
          href="/"
          className="inline-block text-sm py-2 -my-2"
          style={{ color: "#0A1F44" }}
        >
          ← Về trang chủ
        </Link>
        <h1 className="text-3xl font-bold mt-4" style={{ color: "#0A1F44" }}>
          Chính sách bảo mật
        </h1>
        <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
          Cập nhật lần cuối: {LAST_UPDATED}
        </p>
      </header>

      <Section title="1. Phạm vi áp dụng">
        Chính sách này mô tả cách <strong>AMINRA</strong> (sau đây gọi là
        &quot;chúng tôi&quot;) thu thập, sử dụng, chia sẻ và bảo vệ thông tin cá
        nhân khi bạn sử dụng nền tảng chứng nhận Halal AMINRA tại{" "}
        <code>aminra.vn</code> và các sub-domain.
      </Section>

      <Section title="2. Thông tin chúng tôi thu thập">
        <ul>
          <li>
            <strong>Thông tin tài khoản:</strong> email, mật khẩu (đã hash bằng
            bcrypt), tên doanh nghiệp, mã số doanh nghiệp, vai trò (business /
            provider / admin).
          </li>
          <li>
            <strong>Thông tin hồ sơ chứng nhận:</strong> tài liệu sản phẩm, công
            thức, ảnh sản phẩm, báo cáo kiểm định, và các bằng chứng tuân thủ
            Halal được bạn tải lên.
          </li>
          <li>
            <strong>Dữ liệu hoạt động (audit log):</strong> IP, user-agent, thời
            gian các sự kiện đăng nhập, thay đổi trạng thái hồ sơ, cấp/thu hồi
            chứng nhận.
          </li>
          <li>
            <strong>Dữ liệu vận hành:</strong> log lỗi (thông qua Sentry),
            metric hệ thống, và backup định kỳ database.
          </li>
        </ul>
      </Section>

      <Section title="3. Mục đích sử dụng">
        <ul>
          <li>
            Cung cấp dịch vụ chứng nhận Halal: lưu trữ hồ sơ, phối hợp giữa
            doanh nghiệp và tổ chức cấp (CB), tạo và quản lý chứng chỉ.
          </li>
          <li>
            Vận hành tính năng AI tư vấn Halal (RAG) — câu hỏi của bạn được gửi
            tới mô hình ngôn ngữ bên thứ ba (OpenRouter / DeepSeek) để tạo câu
            trả lời. Câu hỏi không chứa dữ liệu cá nhân định danh được lưu vào
            kho dữ liệu huấn luyện.
          </li>
          <li>
            Tuân thủ nghĩa vụ pháp lý và bảo vệ tính toàn vẹn của hệ thống chứng
            nhận (audit log không thể chỉnh sửa, lưu giữ tối thiểu 5 năm).
          </li>
          <li>
            Cảnh báo bảo mật và liên lạc dịch vụ qua email (đặt lại mật khẩu,
            xác thực tài khoản, thông báo trạng thái hồ sơ).
          </li>
        </ul>
      </Section>

      <Section title="4. Chia sẻ dữ liệu với bên thứ ba">
        <p>
          AMINRA <strong>không bán</strong> dữ liệu cá nhân. Chúng tôi chỉ chia
          sẻ dữ liệu trong các trường hợp sau:
        </p>
        <ul>
          <li>
            <strong>Tổ chức cấp chứng nhận (CB):</strong> nhận hồ sơ doanh
            nghiệp đã chủ động gửi để đánh giá. Doanh nghiệp kiểm soát danh sách
            CB nhận hồ sơ.
          </li>
          <li>
            <strong>Nhà cung cấp hạ tầng kỹ thuật:</strong> dịch vụ email
            (SMTP), tracking lỗi (Sentry), CDN. Các đơn vị này chỉ nhận dữ liệu
            cần thiết để vận hành.
          </li>
          <li>
            <strong>Cơ quan có thẩm quyền:</strong> khi có yêu cầu hợp pháp bằng
            văn bản theo quy định của pháp luật Việt Nam.
          </li>
        </ul>
      </Section>

      <Section title="5. Lưu trữ và bảo mật">
        <ul>
          <li>
            Dữ liệu được lưu trên máy chủ tại Việt Nam, mã hóa tĩnh (encryption
            at rest) và mã hóa đường truyền (TLS 1.2+).
          </li>
          <li>Mật khẩu hashed bằng bcrypt, không bao giờ lưu plaintext.</li>
          <li>
            Quyền truy cập tới dữ liệu nội bộ: chỉ kỹ sư on-call có quyền hạn cụ
            thể, mọi truy cập đều ghi vào audit log.
          </li>
          <li>
            Chứng chỉ Halal có hash SHA-256 nhúng trong PDF — bạn có thể xác
            minh tính toàn vẹn ngay cả khi offline.
          </li>
        </ul>
      </Section>

      <Section title="6. Quyền của người dùng (PDPL)">
        <p>
          Theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân, bạn có các
          quyền sau:
        </p>
        <ul>
          <li>
            <strong>Quyền truy cập:</strong> xem dữ liệu cá nhân chúng tôi đang
            lưu trữ về bạn.
          </li>
          <li>
            <strong>Quyền chỉnh sửa:</strong> cập nhật thông tin sai lệch.
          </li>
          <li>
            <strong>Quyền xoá:</strong> yêu cầu xoá tài khoản và dữ liệu liên
            quan, trừ audit log và chứng chỉ đã cấp (lưu theo nghĩa vụ pháp lý).
          </li>
          <li>
            <strong>Quyền xuất dữ liệu:</strong> nhận bản sao dữ liệu ở định
            dạng JSON/CSV.
          </li>
          <li>
            <strong>Quyền phản đối:</strong> phản đối việc xử lý dữ liệu trong
            các trường hợp cụ thể.
          </li>
        </ul>
        <p>
          Quyền truy cập + xuất dữ liệu + xoá tài khoản đã được tự động hoá tại{" "}
          <a
            href="/settings/data-export"
            className="inline-block py-1.5 -my-1.5 underline"
            style={{ color: "#0A1F44" }}
          >
            Cài đặt → Quyền dữ liệu cá nhân
          </a>
          . Cho các yêu cầu khác, gửi email tới{" "}
          <a
            href="mailto:privacy@aminra.vn"
            className="inline-block py-1.5 -my-1.5 underline"
            style={{ color: "#0A1F44" }}
          >
            privacy@aminra.vn
          </a>
          . Chúng tôi cam kết phản hồi trong vòng 30 ngày (PDPL: 72 giờ cho yêu
          cầu khẩn).
        </p>
      </Section>

      <Section title="7. Thời gian lưu trữ">
        <ul>
          <li>
            Tài khoản và hồ sơ doanh nghiệp: lưu giữ trong suốt thời gian sử
            dụng dịch vụ, + 12 tháng sau khi xoá tài khoản.
          </li>
          <li>Audit log: tối thiểu 5 năm theo yêu cầu compliance.</li>
          <li>
            Chứng chỉ Halal đã cấp: lưu giữ vĩnh viễn để phục vụ xác minh công
            khai (public verify).
          </li>
          <li>Backup: 30 ngày rolling, sau đó tự động xoá.</li>
        </ul>
      </Section>

      <Section title="8. Cookies và lưu trữ trình duyệt">
        AMINRA sử dụng <code>localStorage</code> và <code>sessionStorage</code>{" "}
        để lưu JWT access token và refresh token. Không có cookies tracking từ
        bên thứ ba. Tắt localStorage có thể khiến bạn không đăng nhập được.
      </Section>

      <Section title="9. Thay đổi chính sách">
        Chúng tôi có thể cập nhật chính sách này khi luật thay đổi hoặc khi bổ
        sung tính năng mới. Phiên bản mới nhất luôn hiển thị tại trang này với
        ngày &quot;Cập nhật lần cuối&quot;. Thay đổi đáng kể sẽ được thông báo
        qua email.
      </Section>

      <Section title="10. Liên hệ">
        <p>Mọi thắc mắc về chính sách bảo mật, gửi tới:</p>
        <ul className="space-y-2">
          <li>
            Email:{" "}
            <a
              href="mailto:privacy@aminra.vn"
              className="inline-block py-1.5 -my-1.5 underline"
              style={{ color: "#0A1F44" }}
            >
              privacy@aminra.vn
            </a>
          </li>
          <li>Địa chỉ: AMINRA — Halal Certification Platform, Việt Nam</li>
        </ul>
      </Section>

      <footer
        className="mt-12 pt-6 border-t text-sm"
        style={{ borderColor: "#E2E8F0", color: "#94A3B8" }}
      >
        Xem thêm:{" "}
        <Link
          href="/terms"
          className="inline-flex items-center min-h-[32px] underline"
          style={{ color: "#0A1F44" }}
        >
          Điều khoản dịch vụ
        </Link>
      </footer>
    </article>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="text-xl font-bold mb-3" style={{ color: "#0A1F44" }}>
        {title}
      </h2>
      <div className="text-sm leading-relaxed" style={{ color: "#374151" }}>
        {children}
      </div>
    </section>
  );
}
