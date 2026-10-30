"use client";

/**
 * Keycloak SSO button (ADR-005 Phase 2 canary).
 *
 * Renders an "OR — Đăng nhập với Keycloak SSO" affordance when the
 * NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED flag is on. Hidden entirely when
 * off — the legacy email/password form stays the only path. This is
 * intentional: solo-founder pilot can flip the flag per-environment
 * (dev → staging → prod) without code change.
 *
 * Used by business + provider login pages. Forgot/reset pages use
 * `KeycloakSsoNotice` instead since those flows are owned by Keycloak's
 * account console once SSO is enabled.
 */

import { useState } from "react";
import { isOidcEnabled, signinRedirect } from "@/lib/auth-oidc";

interface Props {
  /** Where to land after successful login. Forwarded as OIDC `state`. */
  returnTo: string;
  /** Subtitle text under the button (role-specific). */
  hint?: string;
  /** Defaults to "Đăng nhập với Keycloak SSO". */
  label?: string;
}

export function KeycloakSsoButton({
  returnTo,
  hint = "Bao gồm xác thực 2 yếu tố (TOTP) cho tài khoản cao cấp",
  label = "Đăng nhập với Keycloak SSO",
}: Props) {
  const [error, setError] = useState<string | null>(null);

  if (!isOidcEnabled()) return null;

  const handleClick = async () => {
    setError(null);
    try {
      await signinRedirect(returnTo);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Không thể chuyển sang Keycloak SSO",
      );
    }
  };

  return (
    <div className="mt-5">
      <div
        className="flex items-center gap-3 my-4 text-xs"
        style={{ color: "#94A3B8" }}
      >
        <div className="flex-1 h-px" style={{ background: "#E2E8F0" }} />
        <span>HOẶC</span>
        <div className="flex-1 h-px" style={{ background: "#E2E8F0" }} />
      </div>
      <button
        type="button"
        onClick={handleClick}
        className="btn-lift w-full py-3 rounded-xl font-semibold text-sm"
        style={{
          background: "#FFFFFF",
          color: "#0A1F44",
          border: "1px solid #0A1F44",
          cursor: "pointer",
        }}
        data-testid="keycloak-sso-button"
      >
        {label}
      </button>
      {hint && (
        <p
          className="text-[11px] mt-2 text-center"
          style={{ color: "#94A3B8" }}
        >
          {hint}
        </p>
      )}
      {error && (
        <p
          className="text-xs mt-3 px-3 py-2 rounded-lg"
          style={{
            background: "rgba(239,68,68,0.1)",
            color: "#ef4444",
            border: "1px solid rgba(239,68,68,0.2)",
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Notice shown on forgot/reset password pages when OIDC is enabled.
 * Keycloak owns the credential-reset flow; we direct users there.
 */
export function KeycloakSsoNotice({
  message = "Tài khoản đã được nâng cấp lên Keycloak SSO. Vui lòng dùng nút bên dưới để đặt lại mật khẩu.",
  ctaHref,
  ctaLabel = "Đặt lại mật khẩu trên Keycloak",
}: {
  message?: string;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  if (!isOidcEnabled()) return null;

  const accountUrl =
    ctaHref ??
    `${process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? ""}/realms/${
      process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aminra"
    }/account/#/security/signing-in`;

  return (
    <div
      className="mb-6 p-4 rounded-xl"
      style={{
        background: "rgba(10,31,68,0.04)",
        border: "1px solid #E2E8F0",
      }}
    >
      <p className="text-sm mb-3" style={{ color: "#0A1F44" }}>
        {message}
      </p>
      <a
        href={accountUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center text-sm font-medium underline"
        style={{ color: "#0A1F44" }}
        data-testid="keycloak-account-cta"
      >
        {ctaLabel} →
      </a>
    </div>
  );
}
