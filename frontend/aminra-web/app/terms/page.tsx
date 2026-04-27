import Link from 'next/link';

export const metadata = {
  title: 'Điều khoản dịch vụ — AMINRA',
  description: 'Điều khoản sử dụng nền tảng chứng nhận Halal AMINRA.',
};

const LAST_UPDATED = '2026-04-25';

export default function TermsPage() {
  return (
    <article className="max-w-3xl mx-auto px-6 py-12 prose prose-slate" data-page>
      <header className="mb-8">
        <Link href="/" className="inline-block text-sm py-2 -my-2" style={{ color: '#0F5132' }}>← Về trang chủ</Link>
        <h1 className="text-3xl font-bold mt-4" style={{ color: '#0F5132' }}>
          Điều khoản dịch vụ
        </h1>
        <p className="text-sm mt-2" style={{ color: '#6B7280' }}>
          Cập nhật lần cuối: {LAST_UPDATED}
        </p>
      </header>

      <Section title="1. Chấp nhận điều khoản">
        Bằng việc đăng ký tài khoản hoặc sử dụng AMINRA, bạn xác nhận đã đọc, hiểu và đồng ý
        bị ràng buộc bởi các điều khoản trong tài liệu này. Nếu không đồng ý, vui lòng không
        sử dụng dịch vụ.
      </Section>

      <Section title="2. Mô tả dịch vụ">
        AMINRA là nền tảng SaaS hỗ trợ doanh nghiệp Việt Nam và quốc tế đăng ký, theo dõi,
        và xác minh chứng nhận Halal. Các tính năng chính bao gồm:
        <ul>
          <li>Quản lý hồ sơ chứng nhận và làm việc với tổ chức cấp (CB).</li>
          <li>Truy xuất nguồn gốc Halal từ nguyên liệu đến thành phẩm (supply chain trace).</li>
          <li>AI tư vấn quy trình Halal dựa trên kho kiến thức được kiểm duyệt.</li>
          <li>Xác minh chứng chỉ công khai qua mã số hoặc QR code.</li>
        </ul>
      </Section>

      <Section title="3. Trách nhiệm của người dùng">
        <ul>
          <li>Cung cấp thông tin chính xác khi đăng ký và giữ thông tin cập nhật.</li>
          <li>Bảo mật mật khẩu — không chia sẻ tài khoản với bên thứ ba.</li>
          <li>Chịu trách nhiệm về tính xác thực của tài liệu và thông tin tải lên.</li>
          <li>Không sử dụng dịch vụ cho mục đích bất hợp pháp, lừa đảo, hoặc giả mạo
            chứng nhận.</li>
          <li>Không cố gắng truy cập trái phép, đảo ngược kỹ thuật, hoặc làm gián đoạn
            hoạt động hệ thống.</li>
        </ul>
      </Section>

      <Section title="4. Vai trò của tổ chức cấp chứng nhận (CB)">
        AMINRA <strong>không</strong> trực tiếp cấp chứng nhận Halal. AMINRA là nền tảng kết
        nối doanh nghiệp với các tổ chức cấp chứng nhận đã được kiểm duyệt. Quyết định cấp,
        từ chối, đình chỉ, hoặc thu hồi chứng nhận hoàn toàn thuộc về CB tương ứng. Mọi tranh
        chấp về quyết định chứng nhận giải quyết trực tiếp với CB.
      </Section>

      <Section title="5. Quyền sở hữu trí tuệ">
        <ul>
          <li><strong>Mã nguồn, thiết kế, thương hiệu AMINRA:</strong> thuộc sở hữu của AMINRA.
            Không được sao chép hoặc sử dụng nếu không có văn bản uỷ quyền.</li>
          <li><strong>Nội dung do bạn tải lên</strong> (tài liệu, ảnh, công thức): vẫn thuộc
            sở hữu của bạn. Bạn cấp cho AMINRA giấy phép không độc quyền để lưu trữ, hiển
            thị và xử lý nội dung đó nhằm cung cấp dịch vụ.</li>
          <li><strong>Câu trả lời từ AI:</strong> được tạo từ kho dữ liệu Halal được kiểm
            duyệt. Câu trả lời có tính chất tham khảo, không thay thế kết luận chính thức từ
            CB hoặc cơ quan tôn giáo.</li>
        </ul>
      </Section>

      <Section title="6. Phí dịch vụ và thanh toán">
        Trong giai đoạn MVP, AMINRA cung cấp gói cơ bản miễn phí. Gói trả phí và các tính năng
        nâng cao sẽ được công bố trước ít nhất 30 ngày trước khi áp dụng. Bạn có quyền huỷ
        đăng ký bất kỳ lúc nào trước ngày tính phí.
      </Section>

      <Section title="7. Tính sẵn sàng và bảo trì">
        <ul>
          <li>Mục tiêu uptime: 99.5% mỗi tháng (không bao gồm thời gian bảo trì có thông báo
            trước).</li>
          <li>Bảo trì có kế hoạch sẽ được thông báo trước ít nhất 24 giờ qua email.</li>
          <li>Sự cố ngoài kế hoạch sẽ được khắc phục ưu tiên cao nhất; trạng thái cập nhật
            tại trang status.</li>
        </ul>
      </Section>

      <Section title="8. Giới hạn trách nhiệm">
        Trong phạm vi pháp luật cho phép, AMINRA không chịu trách nhiệm đối với:
        <ul>
          <li>Thiệt hại gián tiếp, ngẫu nhiên, hoặc do hậu quả phát sinh từ việc sử dụng
            dịch vụ.</li>
          <li>Mất dữ liệu do người dùng tự xoá, mất mật khẩu, hoặc tài khoản bị xâm nhập
            do người dùng không bảo mật.</li>
          <li>Quyết định cấp/từ chối chứng nhận của tổ chức cấp (CB).</li>
          <li>Thay đổi luật pháp Việt Nam, Malaysia, Indonesia, hoặc các quốc gia khác liên
            quan đến tiêu chuẩn Halal.</li>
        </ul>
        Trách nhiệm tối đa của AMINRA trong mọi trường hợp giới hạn ở số phí dịch vụ bạn đã
        thanh toán trong 12 tháng gần nhất.
      </Section>

      <Section title="9. Đình chỉ và chấm dứt">
        AMINRA có quyền đình chỉ hoặc chấm dứt tài khoản nếu bạn:
        <ul>
          <li>Vi phạm các điều khoản trong tài liệu này.</li>
          <li>Cung cấp thông tin giả mạo hoặc tài liệu lừa đảo.</li>
          <li>Có hành vi gây hại tới hệ thống hoặc người dùng khác.</li>
        </ul>
        Bạn có thể chấm dứt tài khoản bất kỳ lúc nào bằng cách gửi yêu cầu tới{' '}
        <a href="mailto:support@aminra.vn"
           className="inline-block py-1.5 -my-1.5 underline"
           style={{ color: '#0F5132' }}>
          support@aminra.vn
        </a>.
      </Section>

      <Section title="10. Luật áp dụng và giải quyết tranh chấp">
        Điều khoản này được điều chỉnh bởi pháp luật Việt Nam. Mọi tranh chấp ưu tiên giải
        quyết bằng thương lượng. Nếu không thành, các bên đồng ý đưa ra Toà án có thẩm quyền
        tại Việt Nam.
      </Section>

      <Section title="11. Thay đổi điều khoản">
        AMINRA có thể cập nhật điều khoản này. Phiên bản mới nhất luôn hiển thị tại đây với
        ngày &quot;Cập nhật lần cuối&quot;. Thay đổi đáng kể sẽ được thông báo qua email ít nhất 30
        ngày trước khi có hiệu lực. Tiếp tục sử dụng sau ngày hiệu lực = bạn đồng ý điều khoản
        mới.
      </Section>

      <Section title="12. Liên hệ">
        <p>Mọi thắc mắc về điều khoản dịch vụ:</p>
        <ul className="space-y-2">
          <li>
            Email:{" "}
            <a href="mailto:legal@aminra.vn"
               className="inline-block py-1.5 -my-1.5 underline"
               style={{ color: '#0F5132' }}>
              legal@aminra.vn
            </a>
          </li>
          <li>
            Hỗ trợ:{" "}
            <a href="mailto:support@aminra.vn"
               className="inline-block py-1.5 -my-1.5 underline"
               style={{ color: '#0F5132' }}>
              support@aminra.vn
            </a>
          </li>
        </ul>
      </Section>

      <footer className="mt-12 pt-6 border-t text-sm" style={{ borderColor: '#E2E8F0', color: '#94A3B8' }}>
        Xem thêm:{' '}
        <Link href="/privacy" className="inline-flex items-center min-h-[32px] underline" style={{ color: '#0F5132' }}>Chính sách bảo mật</Link>
      </footer>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-xl font-bold mb-3" style={{ color: '#0F5132' }}>{title}</h2>
      <div className="text-sm leading-relaxed" style={{ color: '#374151' }}>{children}</div>
    </section>
  );
}
