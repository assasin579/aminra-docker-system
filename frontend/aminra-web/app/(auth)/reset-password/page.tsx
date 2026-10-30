"use client";

import Link from "next/link";

export default function ResetPasswordPage() {
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
          Đặt lại mật khẩu
        </h1>
        <p className="mt-1 text-sm" style={{ color: "#6B7280" }}>
          Trang này được giữ trong ứng dụng AMINRA để người dùng không bị chuyển
          sang giao diện quản trị xác thực.
        </p>
      </div>

      <div
        className="rounded-2xl p-8 animate-section text-center"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
        }}
      >
        <p className="text-sm leading-relaxed" style={{ color: "#334155" }}>
          Nếu bạn cần đổi mật khẩu, hãy yêu cầu quản trị viên AMINRA hoặc quản
          trị viên tổ chức cấp mật khẩu mới. Sau đó đăng nhập lại ngay trên ứng
          dụng AMINRA.
        </p>
        <Link
          href="/business/login"
          className="btn-lift inline-flex mt-6 px-6 py-3 rounded-xl text-sm font-semibold text-white"
          style={{ background: "#0A1F44" }}
        >
          Về trang đăng nhập
        </Link>
      </div>
    </div>
  );
}
