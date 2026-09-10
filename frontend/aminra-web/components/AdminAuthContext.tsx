"use client";

/**
 * Phase 4c (2026-05-14): Admin auth via Keycloak realm role `platform_admin`.
 *
 * Token comes from the same Keycloak SSO session as regular users — there is
 * no separate admin login form. `isAdmin` derives from the JWT's
 * `realm_access.roles` claim. `login()` kicks off `signinRedirect` with a
 * return-to of `/admin`; `logout()` ends the Keycloak SSO session entirely.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { signinRedirect, signoutRedirect } from "@/lib/auth-oidc";
import { purgeAuthSessionState } from "@/lib/auth-session-cleanup";

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

const USER_TOKEN_KEY = "aminra_user_token";
const AUTH_SESSION_EVENT = "aminra:auth-session-changed";

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

function readUserToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem(USER_TOKEN_KEY) ||
    sessionStorage.getItem(USER_TOKEN_KEY) ||
    null
  );
}

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const refreshToken = () => setToken(readUserToken());
    refreshToken();
    const onStorage = (e: StorageEvent) => {
      if (e.key === USER_TOKEN_KEY || e.key === null) refreshToken();
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener(AUTH_SESSION_EVENT, refreshToken);
    window.addEventListener("focus", refreshToken);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(AUTH_SESSION_EVENT, refreshToken);
      window.removeEventListener("focus", refreshToken);
    };
  }, []);

  const login = useCallback(async (returnTo?: string) => {
    await signinRedirect(returnTo ?? "/admin");
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    void (async () => {
      await purgeAuthSessionState();
      await signoutRedirect();
    })();
  }, []);

  const isAdmin = hasPlatformAdminRole(token);

  return (
    <AdminAuthContext.Provider value={{ isAdmin, token, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  return useContext(AdminAuthContext);
}
