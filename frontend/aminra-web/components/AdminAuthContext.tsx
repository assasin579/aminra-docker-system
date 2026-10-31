"use client";

/**
 * Phase 4c (2026-05-14): Admin auth via Keycloak realm role `platform_admin`.
 *
 * Token comes from the same Keycloak SSO session as regular users — there is
 * no separate admin login form. `isAdmin` derives from the JWT's
 * `realm_access.roles` claim. `login()` kicks off `signinRedirect` with a
 * return-to of `/admin`; `logout()` ends the Keycloak SSO session entirely.
 */

import { createContext, useCallback, useContext, type ReactNode } from "react";
import { signinRedirect } from "@/lib/auth-oidc";
import { useUserAuth } from "./UserAuthContext";

interface AdminAuthState {
  isAdmin: boolean;
  token: string | null;
  login: (returnTo?: string) => Promise<void>;
  logout: () => void;
}

const AdminAuthContext = createContext<AdminAuthState>({
  isAdmin: false,
  token: null,
  login: async () => {},
  logout: () => {},
});

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    // base64url → base64
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

function hasPlatformAdminRole(token: string | null): boolean {
  if (!token) return false;
  const claims = decodeJwtPayload(token);
  if (!claims) return false;
  const realm = claims["realm_access"] as { roles?: string[] } | undefined;
  return Array.isArray(realm?.roles) && realm!.roles!.includes("platform_admin");
}

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  // A storage token is only a candidate credential. Admin UI follows the same
  // verified principal and logout generation as every other application view.
  const { user, token, isAuthenticated, loading, logout } = useUserAuth();
  const login = useCallback(async (returnTo?: string) => {
    await signinRedirect(returnTo ?? "/admin");
  }, []);

  const isAdmin = !loading && isAuthenticated && (Array.isArray(user?.realm_roles)
    ? user.realm_roles.includes("platform_admin") : hasPlatformAdminRole(token));

  return (
    <AdminAuthContext.Provider value={{ isAdmin, token, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  return useContext(AdminAuthContext);
}
