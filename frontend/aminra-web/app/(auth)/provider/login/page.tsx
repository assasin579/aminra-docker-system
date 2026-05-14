"use client";

/**
 * Phase 4b cutover (2026-05-14): Keycloak SSO is now the SOLE login path.
 */

import { useEffect } from "react";
import { signinRedirect } from "@/lib/auth-oidc";

export default function ProviderLoginPage() {
  useEffect(() => {
    void signinRedirect("/dashboard/provider");
  }, []);

  return (
    <div className="w-full max-w-md text-center" data-page>
      <div
        className="rounded-2xl p-8"
        style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}
      >
        <div
          className="inline-grid place-items-center w-12 h-12 rounded-full mb-4 mx-auto"
          style={{ background: "#F5F1E8" }}
          aria-hidden
        >
          <span className="text-2xl">⏳</span>
        </div>
        <p className="text-base font-semibold" style={{ color: "#1A1A1A" }}>
          Đang chuyển đến trang đăng nhập tổ chức...
        </p>
        <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
          Hệ thống xác thực AMINRA Keycloak. Nếu trang không tự chuyển,
          {" "}
          <button
            type="button"
            onClick={() => void signinRedirect("/dashboard/provider")}
            className="font-medium underline"
            style={{ color: "#0A1F44" }}
          >
            bấm vào đây
          </button>.
        </p>
      </div>
    </div>
  );
}
