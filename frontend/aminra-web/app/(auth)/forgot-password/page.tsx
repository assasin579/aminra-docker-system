"use client";

import { useState } from "react";
import Link from "next/link";
import { KeycloakSsoNotice } from "@/components/KeycloakSsoButton";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/request-password-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), lang: "vi" }),
      });
      if (!res.ok) {
        throw new Error("Yêu cầu thất bại — vui lòng thử lại");
      }
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  };

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
          Quên mật khẩu?
        </h1>
        <p className="mt-1 text-sm" style={{ color: "#6B7280" }}>
          Nhập email tài khoản. Chúng tôi sẽ gửi liên kết đặt lại mật khẩu.
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
        <KeycloakSsoNotice
          message="Nếu tài khoản đã được nâng cấp lên Keycloak SSO, vui lòng đặt lại mật khẩu trên Keycloak account console. Form bên dưới chỉ áp dụng cho tài khoản chưa di trú."
        />
        {sent ? (
          <div role="status" className="text-center space-y-4">
            <div className="inline-grid place-items-center w-12 h-12 rounded-full bg-[#DCE3F0]">
              <span className="text-[#0A1F44] text-xl">✓</span>
            </div>
            <p className="text-sm" style={{ color: "#0A1F44" }}>
              Nếu email <strong>{email}</strong> tồn tại trong hệ thống, hướng
              dẫn đặt lại mật khẩu đã được gửi.
            </p>
            <p className="text-xs" style={{ color: "#6B7280" }}>
              Liên kết có hiệu lực trong 60 phút. Vui lòng kiểm tra cả thư mục
              Spam.
            </p>
            <Link
              href="/business/login"
              className="inline-block mt-4 text-sm font-medium"
              style={{ color: "#0A1F44" }}
            >
              ← Quay lại đăng nhập
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6B7280" }}
              >
                Email tài khoản
              </label>
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="cong-ty@example.com"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                  color: "#0A1F44",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
                onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
              />
            </div>

            {error && (
              <p
                className="text-xs px-3 py-2 rounded-lg"
                style={{
                  background: "rgba(239,68,68,0.1)",
                  color: "#ef4444",
                  border: "1px solid rgba(239,68,68,0.2)",
                }}
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3 rounded-xl font-semibold text-sm transition-all"
              style={{
                background: loading || !email ? "#E2E8F0" : "#0A1F44",
                color: loading || !email ? "#6B7280" : "white",
                cursor: loading || !email ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Đang gửi..." : "Gửi hướng dẫn đặt lại"}
            </button>
          </form>
        )}

        <div
          className="mt-6 pt-5 text-center"
          style={{ borderTop: "1px solid #E2E8F0" }}
        >
          <p className="text-sm" style={{ color: "#6B7280" }}>
            Nhớ mật khẩu rồi?{" "}
            <Link
              href="/business/login"
              className="inline-block font-medium py-2 -my-2 underline"
              style={{ color: "#0A1F44" }}
            >
              Đăng nhập
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
