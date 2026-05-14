"use client";

/**
 * Phase 4b cutover (2026-05-14): Password reset owned by Keycloak.
 * The Keycloak email-link flow lands user on Keycloak's own reset page
 * (themed via `login-reset-password.ftl`), not this FE page.
 */

import { useEffect } from "react";
import { signinRedirect } from "@/lib/auth-oidc";

export default function ResetPasswordPage() {
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
          Đang chuyển hướng...
        </p>
        <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
          Khôi phục mật khẩu được xử lý bởi Keycloak qua email link.
        </p>
      </div>
    </div>
  );
}
