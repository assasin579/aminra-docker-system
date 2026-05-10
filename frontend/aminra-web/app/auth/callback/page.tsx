"use client";

/**
 * Keycloak OIDC callback handler (ADR-005 Phase 2b canary).
 *
 * Keycloak redirects here after successful login with `?code=…&state=…`.
 * We exchange the code for tokens via oidc-client-ts, then install the
 * access_token into UserAuthContext so the rest of the app sees an
 * authenticated session.
 *
 * Error paths (user cancels, code expired, network) render an inline
 * message + a button back to the original login page. We don't auto-
 * retry to avoid login loops.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { handleSigninCallback, isOidcEnabled } from "@/lib/auth-oidc";
import { useUserAuth } from "@/components/UserAuthContext";

export default function OidcCallbackPage() {
  const router = useRouter();
  const { loginViaKeycloak } = useUserAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOidcEnabled()) {
      setError(
        "Keycloak SSO chưa được bật cho môi trường này. Vui lòng quay lại đăng nhập thường.",
      );
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { user, returnTo } = await handleSigninCallback();
        if (cancelled) return;
        await loginViaKeycloak(user.access_token);
        // Defensive: ensure returnTo is a relative path to prevent open-redirect
        const safeReturnTo =
          returnTo.startsWith("/") && !returnTo.startsWith("//")
            ? returnTo
            : "/dashboard/business";
        router.replace(safeReturnTo);
      } catch (e) {
        if (cancelled) return;
        setError(
          e instanceof Error
            ? e.message
            : "Lỗi khi xử lý phản hồi từ Keycloak",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loginViaKeycloak, router]);

  return (
    <div className="min-h-screen grid place-items-center px-6">
      <div className="w-full max-w-md text-center">
        {error ? (
          <>
            <h1
              className="text-lg font-semibold mb-3"
              style={{ color: "#0A1F44" }}
            >
              Đăng nhập SSO thất bại
            </h1>
            <p
              className="text-sm mb-6 px-4 py-3 rounded-lg"
              style={{
                background: "rgba(239,68,68,0.1)",
                color: "#ef4444",
                border: "1px solid rgba(239,68,68,0.2)",
              }}
            >
              {error}
            </p>
            <button
              type="button"
              onClick={() => router.replace("/business/login")}
              className="btn-lift py-3 px-6 rounded-xl font-semibold text-sm"
              style={{ background: "#0A1F44", color: "white" }}
            >
              Quay lại đăng nhập
            </button>
          </>
        ) : (
          <>
            <div
              className="inline-block w-10 h-10 rounded-full mb-4"
              style={{
                border: "3px solid #E2E8F0",
                borderTopColor: "#0A1F44",
                animation: "spin 0.8s linear infinite",
              }}
            />
            <p className="text-sm" style={{ color: "#6B7280" }}>
              Đang hoàn tất đăng nhập...
            </p>
          </>
        )}
      </div>
    </div>
  );
}
