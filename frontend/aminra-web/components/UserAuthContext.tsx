"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import {
  AUTH_SESSION_EVENT,
  notifyAuthSessionChanged,
  purgeAuthSessionState,
  removeLegacyAdminSessionKey,
  removeStoredAuthSessionKeys,
} from "@/lib/auth-session-cleanup";

export type UserRole = "business" | "provider";

export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  status: string;
  company_name: string;
  company_code: string | null;
  is_owner: boolean;
  tenant_id: string | null;
  member_count?: number | null;
  address?: string | null;
  phone?: string | null;
  representative_name?: string | null;
  permissions?: {
    can_edit: boolean;
    can_delete: boolean;
    can_approve: boolean;
    can_upload: boolean;
    /** Tier-1 #24 — Halal document approval permission. */
    can_approve_documents?: boolean;
  };
  /** IHC role (set on business members designated to Internal Halal Committee).
   *  Auto-grants can_approve_documents per JAKIM MS 1500 §5.4. */
  ihc_role?: string | null;
  /** TASK #19 — Industry schema assigned during onboarding. Null until
   *  business owner completes industry-select flow. Locked post-cert issued. */
  industry_schema_id?: string | null;
  industry_schema_code?: string | null;
  keycloak_sub?: string | null;
  realm_roles?: string[] | null;
}

interface UserAuthState {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  loginBusiness: (email: string, password: string, remember?: boolean) => Promise<void>;
  loginProvider: (email: string, password: string, remember?: boolean) => Promise<void>;
  /**
   * ADR-005 Phase 2: install a Keycloak-issued access token as the active
   * session. The token is verified and enriched by the BE dual-auth path
   * (`get_current_user` → keycloak_validator). Returns the resolved profile so
   * the callback can avoid redirecting a provider/admin into business-only pages.
   */
  loginViaKeycloak: (
    accessToken: string,
    expectedRole?: UserRole,
  ) => Promise<UserProfile>;
  /** Re-fetch /auth/me and update local user state. Used after server-side
   *  profile mutations (e.g. industry-schema assignment) so subsequent
   *  guard checks see the latest fields. */
  refreshProfile: () => Promise<void>;
  logout: () => void;
}

const UserAuthContext = createContext<UserAuthState>({
  user: null,
  token: null,
  isAuthenticated: false,
  loading: true,
  loginBusiness: async () => {},
  loginProvider: async () => {},
  loginViaKeycloak: async () => {
    throw new Error("UserAuthProvider not mounted");
  },
  refreshProfile: async () => {},
  logout: () => {},
});

const TOKEN_KEY = "aminra_user_token";
const PROFILE_KEY = "aminra_user_profile";

async function apiLogin(email: string, password: string, role?: string) {
  const { parseApiError } = await import("@/lib/apiError");
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, role }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      parseApiError(body, `Đăng nhập thất bại (HTTP ${res.status})`),
    );
  }
  return res.json() as Promise<{ access_token: string; user: UserProfile }>;
}

type KeycloakClaims = {
  sub?: string;
  email?: string;
  preferred_username?: string;
  realm_access?: { roles?: string[] };
};

function decodeJwtPayload(token: string): KeycloakClaims | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    return JSON.parse(atob(padded)) as KeycloakClaims;
  } catch {
    return null;
  }
}

function normalizeIdentity(value: string | null | undefined): string | null {
  return value?.trim().toLowerCase() || null;
}

function assertKeycloakIdentityMatchesProfile(
  accessToken: string,
  profile: UserProfile,
): void {
  const claims = decodeJwtPayload(accessToken);
  if (!claims) return;

  const claimSub = normalizeIdentity(claims.sub);
  const profileSub = normalizeIdentity(profile.keycloak_sub);
  if (claimSub && profileSub && claimSub !== profileSub) {
    throw new Error("Phiên đăng nhập không nhất quán. Vui lòng đăng nhập lại.");
  }

  const claimEmail = normalizeIdentity(claims.email);
  const claimUsername = normalizeIdentity(claims.preferred_username);
  const profileEmail = normalizeIdentity(profile.email);
  if (
    profileEmail &&
    (claimEmail || claimUsername) &&
    profileEmail !== claimEmail &&
    profileEmail !== claimUsername
  ) {
    throw new Error("Phiên đăng nhập không nhất quán. Vui lòng đăng nhập lại.");
  }
}

export function UserAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from localStorage OR sessionStorage and verify
  useEffect(() => {
    const storedToken =
      localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
    const storedProfile =
      localStorage.getItem(PROFILE_KEY) || sessionStorage.getItem(PROFILE_KEY);
    if (!storedToken || !storedProfile) {
      setLoading(false);
      return;
    }

    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then(async (res) => {
        if (res.ok) {
          const profile = (await res.json()) as UserProfile;
          assertKeycloakIdentityMatchesProfile(storedToken, profile);
          setToken(storedToken);
          setUser(profile);
          if (localStorage.getItem(TOKEN_KEY))
            localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
          else sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
        } else {
          await purgeAuthSessionState("auth_rejected");
          setToken(null);
          setUser(null);
        }
      })
      .catch(async () => {
        await purgeAuthSessionState("auth_rejected");
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const _saveSession = useCallback(
    (t: string, u: UserProfile, remember = true) => {
      setToken(t);
      setUser(u);
      const storage = remember ? localStorage : sessionStorage;
      storage.setItem(TOKEN_KEY, t);
      storage.setItem(PROFILE_KEY, JSON.stringify(u));
      // Clear the other storage
      const other = remember ? sessionStorage : localStorage;
      removeStoredAuthSessionKeys(other);
      removeLegacyAdminSessionKey(localStorage);
      // Notify same-tab consumers. Browser `storage` events only fire in other
      // tabs, so AdminAuthContext would otherwise keep a stale `isAdmin=false`
      // after the OIDC callback stores a fresh platform_admin token.
      notifyAuthSessionChanged();
      // Set cookie for middleware redirect check
      document.cookie =
        "aminra_session=1; path=/; max-age=31536000; SameSite=Lax";
    },
    [],
  );

  const loginBusiness = useCallback(
    async (email: string, password: string, remember = true) => {
      const { access_token, user: u } = await apiLogin(
        email,
        password,
        "business",
      );
      if (u.role !== "business")
        throw new Error("Tài khoản không phải doanh nghiệp");
      _saveSession(access_token, u, remember);
    },
    [_saveSession],
  );

  const loginProvider = useCallback(
    async (email: string, password: string, remember = true) => {
      const { access_token, user: u } = await apiLogin(
        email,
        password,
        "provider",
      );
      if (u.role !== "provider")
        throw new Error("Tài khoản không phải tổ chức");
      _saveSession(access_token, u, remember);
    },
    [_saveSession],
  );

  const loginViaKeycloak = useCallback(
    async (accessToken: string, expectedRole?: UserRole) => {
      // BE dual-auth path validates the Keycloak JWT and returns the
      // enriched profile. Use the same /api/auth/me endpoint as the
      // legacy refresh path — keeps server logic single-source.
      const res = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg =
          (body && (body.detail || body.message)) ||
          `Keycloak token rejected (HTTP ${res.status})`;
        throw new Error(msg);
      }
      const profile = (await res.json()) as UserProfile;
      try {
        assertKeycloakIdentityMatchesProfile(accessToken, profile);
      } catch (error) {
        await purgeAuthSessionState("callback_mismatch");
        setToken(null);
        setUser(null);
        throw error;
      }
      if (expectedRole && profile.role !== expectedRole) {
        throw new Error(
          `Tài khoản không phù hợp (kỳ vọng ${expectedRole}, nhận được ${profile.role})`,
        );
      }
      _saveSession(accessToken, profile, true);
      return profile;
    },
    [_saveSession],
  );

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const profile = (await res.json()) as UserProfile;
    setUser(profile);
    // Persist into whichever storage has the token
    if (localStorage.getItem(TOKEN_KEY))
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    else if (sessionStorage.getItem(TOKEN_KEY))
      sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  }, [token]);

  const logout = useCallback(() => {
    // Detect Keycloak session via stored OIDC user. If present, redirect
    // through Keycloak end-session endpoint so realm cookie is cleared —
    // otherwise next "Đăng nhập SSO" would auto-relogin same user.
    setToken(null);
    setUser(null);
    void (async () => {
      try {
        const { isOidcEnabled, getOidcUser, signoutRedirect } = await import(
          "@/lib/auth-oidc"
        );
        const shouldEndKeycloakSession = isOidcEnabled() && !!(await getOidcUser());
        await purgeAuthSessionState("logout");
        if (shouldEndKeycloakSession) {
          await signoutRedirect();
        }
      } catch {
        await purgeAuthSessionState("logout");
      }
    })();
  }, []);

  return (
    <UserAuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        loading,
        loginBusiness,
        loginProvider,
        loginViaKeycloak,
        refreshProfile,
        logout,
      }}
    >
      {children}
    </UserAuthContext.Provider>
  );
}

export function useUserAuth() {
  return useContext(UserAuthContext);
}
