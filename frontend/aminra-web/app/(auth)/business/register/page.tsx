"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import { parseApiError, validatePassword } from "@/lib/apiError";

export default function BusinessRegisterPage() {
  const router = useRouter();
  const { loginBusiness } = useUserAuth();

  const [form, setForm] = useState({
    email: "",
    password: "",
    confirm_password: "",
    company_name: "",
    company_code: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm_password) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }
    const pwErr = validatePassword(form.password);
    if (pwErr) {
      setError(pwErr);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/auth/business/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email.trim(),
          password: form.password,
          company_name: form.company_name.trim(),
          company_code: form.company_code.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(
          parseApiError(body, `Đăng ký thất bại (HTTP ${res.status})`),
        );
      }
      // Auto-login after register
      await loginBusiness(form.email.trim(), form.password);
      router.replace("/dashboard/business");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại");
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };
  const inputClass =
    "w-full px-4 py-3 rounded-xl text-sm outline-none transition-all";

  return (
    <div className="w-full max-w-lg" data-page>
      {/* Header */}
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
          Đăng ký doanh nghiệp
        </h1>
        <p className="mt-1 text-sm" style={{ color: "#6B7280" }}>
          Bắt đầu hành trình chứng nhận Halal cho doanh nghiệp của bạn
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
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Company info */}
          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Tên công ty *
            </label>
            <input
              required
              value={form.company_name}
              onChange={set("company_name")}
              placeholder="Công ty TNHH ABC"
              className={inputClass}
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
              onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
            />
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Mã số thuế / Mã đăng ký kinh doanh
            </label>
            <input
              value={form.company_code}
              onChange={set("company_code")}
              placeholder="0123456789 (tuỳ chọn)"
              className={inputClass}
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
              onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
            />
          </div>

          <div
            style={{
              borderTop: "1px solid #E2E8F0",
              paddingTop: "1rem",
              marginTop: "0.5rem",
            }}
          >
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Email đăng nhập *
            </label>
            <input
              type="email"
              required
              value={form.email}
              onChange={set("email")}
              placeholder="email@congtycua.com"
              className={inputClass}
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
              onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6B7280" }}
              >
                Mật khẩu *
              </label>
              <input
                type="password"
                required
                value={form.password}
                onChange={set("password")}
                placeholder="••••••••••"
                minLength={10}
                className={inputClass}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
                onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
              />
              <p className="text-xs mt-1.5" style={{ color: "#94A3B8" }}>
                Tối thiểu 10 ký tự, có chữ hoa, chữ thường và số.
              </p>
            </div>
            <div>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6B7280" }}
              >
                Xác nhận mật khẩu *
              </label>
              <input
                type="password"
                required
                value={form.confirm_password}
                onChange={set("confirm_password")}
                placeholder="Nhập lại mật khẩu"
                className={inputClass}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "#0A1F44")}
                onBlur={(e) => (e.target.style.borderColor = "#E2E8F0")}
              />
            </div>
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
            disabled={loading}
            className="btn-lift w-full py-3 rounded-xl font-semibold text-sm mt-2"
            style={{
              background: loading ? "#E2E8F0" : "#0A1F44",
              color: loading ? "#6B7280" : "white",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Đang đăng ký..." : "Đăng ký ngay"}
          </button>
        </form>

        <div
          className="mt-6 pt-5 text-center"
          style={{ borderTop: "1px solid #E2E8F0" }}
        >
          <p className="text-sm" style={{ color: "#6B7280" }}>
            Đã có tài khoản?{" "}
            <Link
              href="/business/login"
              className="inline-flex items-center min-h-[32px] font-medium transition-colors"
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