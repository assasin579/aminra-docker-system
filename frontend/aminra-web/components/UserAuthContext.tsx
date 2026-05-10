"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";

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
   * (`get_current_user` → keycloak_validator). Caller is responsible for
   * UI-level role gating (e.g. business login page rejecting non-business).
   */
  loginViaKeycloak: (accessToken: string, expectedRole?: UserRole) => Promise<void>;
  logout: () => void;
}

const UserAuthContext = createContext<UserAuthState>({
  user: null,
  token: null,
  isAuthenticated: false,
  loading: true,
  loginBusiness: async () => {},
  loginProvider: async () => {},
  loginViaKeycloak: async () => {},
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

    setToken(storedToken);
    setUser(JSON.parse(storedProfile));

    fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((profile) => {
        if (profile) {
          setUser(profile);
          // Update whichever storage has it
          if (localStorage.getItem(TOKEN_KEY))
            localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
          else sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
        } else {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(PROFILE_KEY);
          sessionStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(PROFILE_KEY);
          setToken(null);
          setUser(null);
        }
      })
      .catch(() => {})
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
      other.removeItem(TOKEN_KEY);
      other.removeItem(PROFILE_KEY);
      // Clear admin session — user and admin sessions must not coexist
      localStorage.removeItem("aminra_admin_token");
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
      if (expectedRole && profile.role !== expectedRole) {
        throw new Error(
          `Tài khoản không phù hợp (kỳ vọng ${expectedRole}, nhận được ${profile.role})`,
        );
      }
      _saveSession(accessToken, profile, true);
    },
    [_saveSession],
  );

  const logout = useCallback(() => {
    // Detect Keycloak session via stored OIDC user. If present, redirect
    // through Keycloak end-session endpoint so realm cookie is cleared —
    // otherwise next "Đăng nhập SSO" would auto-relogin same user.
    (async () => {
      try {
        const { isOidcEnabled, getOidcUser, signoutRedirect } = await import(
          "@/lib/auth-oidc"
        );
        if (isOidcEnabled()) {
          const oidcUser = await getOidcUser();
          if (oidcUser) {
            // Clear local first so the post-logout return lands on a clean state.
            setToken(null);
            setUser(null);
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(PROFILE_KEY);
            sessionStorage.removeItem(TOKEN_KEY);
            sessionStorage.removeItem(PROFILE_KEY);
            localStorage.removeItem("aminra_admin_token");
            document.cookie = "aminra_session=; path=/; max-age=0";
            await signoutRedirect();
            return;
          }
        }
      } catch {
        // Fall through to legacy local-only logout
      }
    })();
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(PROFILE_KEY);
    // Cross-context cleanup: never leave a stale admin token after user logout
    localStorage.removeItem("aminra_admin_token");
    document.cookie = "aminra_session=; path=/; max-age=0";
    try {
      sessionStorage.clear();
    } catch {}
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
