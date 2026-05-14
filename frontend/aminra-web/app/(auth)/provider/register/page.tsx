"use client";

/**
 * Phase 4b cutover (2026-05-14): Registration owned by Keycloak.
 */

import { useEffect } from "react";
import { signinRedirect } from "@/lib/auth-oidc";

export default function ProviderRegisterPage() {
  useEffect(() => {
    void signinRedirect("/dashboard/provider");
  }, []);

  return (
    <div className="w-full max-w-md text-center" data-page>
      <div
        className="rounded-2xl p-8"
        style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}
      >
        <p className="text-base font-semibold" style={{ color: "#1A1A1A" }}>
          Đang chuyển đến trang đăng ký tổ chức...
        </p>
        <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
          Tại trang đăng nhập Keycloak, bấm <b>"Đăng ký ngay"</b>. Tài khoản tổ chức sẽ chờ admin xét duyệt.
        </p>
      </div>
    </div>
  );
}
