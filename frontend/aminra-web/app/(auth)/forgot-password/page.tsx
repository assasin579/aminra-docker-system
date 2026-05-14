"use client";

/**
 * Phase 4b cutover (2026-05-14): Password reset owned by Keycloak.
 * Redirect to Keycloak SSO login where user clicks "Quên mật khẩu?"
 * to access reset flow (email link sent by Keycloak).
 */

import { useEffect } from "react";
import { signinRedirect } from "@/lib/auth-oidc";

export default function ForgotPasswordPage() {
  useEffect(() => {
    void signinRedirect("/");
  }, []);

  return (
    <div className="w-full max-w-md text-center" data-page>
      <div
        className="rounded-2xl p-8"
        style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}
      >
        <p className="text-base font-semibold" style={{ color: "#1A1A1A" }}>
          Đang chuyển đến trang khôi phục mật khẩu...
        </p>
        <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
          Tại trang đăng nhập Keycloak, bấm <b>"Quên mật khẩu?"</b> để nhận email khôi phục.
        </p>
      </div>
    </div>
  );
}
