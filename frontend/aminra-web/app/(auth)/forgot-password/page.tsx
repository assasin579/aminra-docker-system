"use client";

import Link from "next/link";

export default function ForgotPasswordPage() {
  return (
    <div className="w-full max-w-md" data-page>
      <div className="text-center mb-8 animate-section">
        <div
          className="inline-grid place-items-center w-16 h-16 rounded-2xl mb-4"
          style={{
            background: "#FFFFFF",
            border: "1px solid #E2E8F0",
            boxShadow: "0 8px 24px rgba(10,31,68,0.12)",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/aminra-mark.png"
            alt="AMINRA"
            className="w-11 h-11 object-contain"
          />
        </div>
        <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
          Khôi phục mật khẩu
        </h1>
        <p className="mt-1 text-sm" style={{ color: "#6B7280" }}>
          Vì lý do bảo mật, AMINRA xử lý yêu cầu đặt lại mật khẩu trong nội bộ
          ứng dụng — không chuyển người dùng sang trang quản trị xác thực.
        </p>
      </div>

      <div
        className="rounded-2xl p-8 animate-section"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        <div
          className="rounded-xl p-4 text-sm leading-relaxed"
          style={{
            background: "#F8FAFC",
            border: "1px solid #E2E8F0",
            color: "#334155",
          }}
        >
          <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
            Cần đặt lại mật khẩu?
          </p>
          <p>
            Vui lòng liên hệ quản trị viên AMINRA hoặc quản trị viên tổ chức để
            cấp mật khẩu mới. Sau khi nhận mật khẩu mới, quay lại trang đăng
            nhập của AMINRA để tiếp tục.
          </p>
        </div>

        <div
          className="mt-6 pt-5 text-center"
          style={{ borderTop: "1px solid #E2E8F0" }}
        >
          <Link
            href="/business/login"
            className="inline-flex items-center min-h-[32px] font-medium underline"
            style={{ color: "#0A1F44" }}
          >
            ← Quay lại đăng nhập doanh nghiệp
          </Link>
          <br />
          <Link
            href="/provider/login"
            className="inline-flex items-center min-h-[32px] text-sm mt-2 underline"
            style={{ color: "#64748B" }}
          >
            Đăng nhập tổ chức chứng nhận
          </Link>
        </div>
      </div>
    </div>
  );
}
