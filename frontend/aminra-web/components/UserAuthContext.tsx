"use client";

import {
  createContext,
  Fragment,
  useRef,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import {
  AUTH_SESSION_EVENT,
  clearApplicationCredentials,
  clearAuthDerivedState,
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

function readApplicationToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
}

function authorizationScope(user: UserProfile | null, token: string | null): string {
  if (!user) return "anonymous";
  const permissions = user.permissions;
  const roles = user.realm_roles ?? decodeJwtPayload(token || "")?.realm_access?.roles ?? [];
  return JSON.stringify([user.id, user.tenant_id, user.role, user.status, user.is_owner,
    [...roles].filter(role => ["business", "cb_admin", "auditor", "platform_admin"].includes(role)).sort(), user.is_owner ? [] : [
      !!permissions?.can_edit, !!permissions?.can_delete, !!permissions?.can_upload,
      !!permissions?.can_approve, !!permissions?.can_approve_documents,
    ]]);
}

export function UserAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const loginSequence = useRef(0);
  const activeSession = useRef<{ token: string | null; user: UserProfile | null }>({ token: null, user: null });
  const pendingRead = useRef<AbortController | null>(null);

  // Storage is a notification channel, never an authority for another account's profile.
  useEffect(() => {
    let mounted = true;
    let pageActive = true;
    const synchronize = async (force = false) => {
      if (!mounted || !pageActive) return;
      const storedToken = readApplicationToken();
      if (!storedToken) {
        if (activeSession.current.token) void clearAuthDerivedState();
        if (activeSession.current.token) loginSequence.current += 1;
        generation.current += 1; pendingRead.current?.abort();
        activeSession.current = { token: null, user: null };
        setToken(null); setUser(null); setLoading(false);
        return;
      }
      if (!force && storedToken === activeSession.current.token) return;
      const previous = activeSession.current.user;
      const claims = decodeJwtPayload(storedToken);
      const sameIdentity = !!previous && !!claims &&
        authorizationScope(previous, activeSession.current.token) === authorizationScope(previous, storedToken) &&
        JSON.stringify([...(decodeJwtPayload(activeSession.current.token || "")?.realm_access?.roles || [])].sort()) === JSON.stringify([...(claims.realm_access?.roles || [])].sort()) && (
        !!claims.sub && normalizeIdentity(claims.sub) === normalizeIdentity(previous.keycloak_sub || decodeJwtPayload(activeSession.current.token || "")?.sub)
      );
      if (storedToken !== activeSession.current.token) loginSequence.current += 1;
      if (!sameIdentity && activeSession.current.token) void clearAuthDerivedState();
      const current = ++generation.current;
      pendingRead.current?.abort();
      const controller = new AbortController(); pendingRead.current = controller;
      const deadline = window.setTimeout(() => controller.abort(), 5000);
      activeSession.current = { token: storedToken, user: sameIdentity ? previous : null };
      if (!sameIdentity) { setToken(null); setUser(null); setLoading(true); }
      try {
        const response = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${storedToken}` }, signal: controller.signal });
        if (!mounted || current !== generation.current || readApplicationToken() !== storedToken) return;
        if (!response.ok) throw new Error("Session rejected");
        const profile = (await response.json()) as UserProfile;
        if (!mounted || current !== generation.current || readApplicationToken() !== storedToken) return;
        assertKeycloakIdentityMatchesProfile(storedToken, profile);
        if (previous && authorizationScope(previous, storedToken) !== authorizationScope(profile, storedToken)) void clearAuthDerivedState();
        activeSession.current = { token: storedToken, user: profile };
        setToken(storedToken); setUser(profile);
        const storage = localStorage.getItem(TOKEN_KEY) === storedToken ? localStorage : sessionStorage;
        const serialized = JSON.stringify(profile);
        if (storage.getItem(PROFILE_KEY) !== serialized) storage.setItem(PROFILE_KEY, serialized);
      } catch {
        if (!mounted || current !== generation.current || readApplicationToken() !== storedToken) return;
        activeSession.current = { token: null, user: null };
        setToken(null); setUser(null); setLoading(false);
        await purgeAuthSessionState("auth_rejected");
      } finally {
        window.clearTimeout(deadline);
        if (mounted && current === generation.current) setLoading(false);
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === TOKEN_KEY || event.key === PROFILE_KEY || event.key === null) void synchronize(event.key === PROFILE_KEY);
    };
    const onSession = () => { void synchronize(); };
    // A navigation abort is not an authentication refusal. Invalidate work
    // before the browser cancels fetch/body reads in the departing document.
    const onPageHide = () => {
      pageActive = false;
      generation.current += 1; loginSequence.current += 1;
      pendingRead.current?.abort();
      activeSession.current = { token: null, user: null };
      setToken(null); setUser(null); setLoading(true);
    };
    const onPageShow = () => { pageActive = true; void synchronize(true); };
    const onFocus = () => { void synchronize(true); };
    const onVisibility = () => { if (document.visibilityState === "visible") void synchronize(true); };
    const interval = window.setInterval(() => {
      if (activeSession.current.token && document.visibilityState === "visible") void synchronize(true);
    }, 10000);
    window.addEventListener("storage", onStorage);
    window.addEventListener(AUTH_SESSION_EVENT, onSession);
    window.addEventListener("focus", onFocus);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    document.addEventListener("visibilitychange", onVisibility);
    void synchronize();
    return () => {
      mounted = false; generation.current += 1; pendingRead.current?.abort();
      // Effect replay must not mistake an aborted verification for a restored session.
      activeSession.current = { token: null, user: null };
      window.removeEventListener("storage", onStorage);
      window.removeEventListener(AUTH_SESSION_EVENT, onSession);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("pageshow", onPageShow);
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearInterval(interval);
    };
  }, []);

  const _saveSession = useCallback(
    (t: string, u: UserProfile, remember = true, preserveOidc = false) => {
      assertKeycloakIdentityMatchesProfile(t, u);
      generation.current += 1; pendingRead.current?.abort();
      activeSession.current = { token: t, user: u };
      void clearAuthDerivedState();
      if (!preserveOidc) {
        removeStoredAuthSessionKeys(localStorage);
        removeStoredAuthSessionKeys(sessionStorage);
      }
      setLoading(false);
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
      const attempt = ++loginSequence.current; generation.current += 1;
      const { access_token, user: u } = await apiLogin(
        email,
        password,
        "business",
      );
      if (attempt !== loginSequence.current) throw new Error("Yêu cầu đăng nhập đã được thay thế bởi một phiên mới.");
      if (u.role !== "business")
        throw new Error("Tài khoản không phải doanh nghiệp");
      _saveSession(access_token, u, remember);
    },
    [_saveSession],
  );

  const loginProvider = useCallback(
    async (email: string, password: string, remember = true) => {
      const attempt = ++loginSequence.current; generation.current += 1;
      const { access_token, user: u } = await apiLogin(
        email,
        password,
        "provider",
      );
      if (attempt !== loginSequence.current) throw new Error("Yêu cầu đăng nhập đã được thay thế bởi một phiên mới.");
      if (u.role !== "provider")
        throw new Error("Tài khoản không phải tổ chức");
      _saveSession(access_token, u, remember);
    },
    [_saveSession],
  );

  const loginViaKeycloak = useCallback(
    async (accessToken: string, expectedRole?: UserRole) => {
      const attempt = ++loginSequence.current; generation.current += 1;
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
      if (attempt !== loginSequence.current) throw new Error("Yêu cầu đăng nhập đã được thay thế bởi một phiên mới.");
      try {
        assertKeycloakIdentityMatchesProfile(accessToken, profile);
      } catch (error) {
        if (attempt === loginSequence.current) {
          generation.current += 1; pendingRead.current?.abort();
          activeSession.current = { token: null, user: null };
          setToken(null); setUser(null);
          await purgeAuthSessionState("callback_mismatch");
        }
        throw error;
      }
      if (expectedRole && profile.role !== expectedRole) {
        throw new Error(
          `Tài khoản không phù hợp (kỳ vọng ${expectedRole}, nhận được ${profile.role})`,
        );
      }
      _saveSession(accessToken, profile, true, true);
      return profile;
    },
    [_saveSession],
  );

  const refreshProfile = useCallback(async () => {
    if (!token || activeSession.current.token !== token) return;
    const current = ++generation.current;
    const res = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } });
    if (current !== generation.current || activeSession.current.token !== token || readApplicationToken() !== token) return;
    if (!res.ok) return;
    const profile = (await res.json()) as UserProfile;
    if (current !== generation.current || readApplicationToken() !== token) return;
    assertKeycloakIdentityMatchesProfile(token, profile);
    if (activeSession.current.user && authorizationScope(activeSession.current.user, token) !== authorizationScope(profile, token)) void clearAuthDerivedState();
    activeSession.current = { token, user: profile };
    setUser(profile);
    const storage = localStorage.getItem(TOKEN_KEY) === token ? localStorage : sessionStorage;
    storage.setItem(PROFILE_KEY, JSON.stringify(profile));
  }, [token]);

  const logout = useCallback(() => {
    const attempt = ++loginSequence.current;
    generation.current += 1; pendingRead.current?.abort();
    activeSession.current = { token: null, user: null };
    clearApplicationCredentials();
    setLoading(false);
    notifyAuthSessionChanged("logout");
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
        const oidcUser = isOidcEnabled()
          ? await getOidcUser().catch(() => null)
          : null;
        if (attempt !== loginSequence.current || readApplicationToken()) return;
        await purgeAuthSessionState("logout");
        if (attempt !== loginSequence.current || readApplicationToken()) return;
        if (oidcUser) {
          // Only browser-initiated SSO sessions need Keycloak end-session.
          // Normal business/provider logins use the AMINRA form plus a
          // server-side token exchange, so redirecting them to Keycloak on
          // logout would expose the identity-provider UI unnecessarily.
          await signoutRedirect(oidcUser);
        }
      } catch {
        if (attempt === loginSequence.current && !readApplicationToken()) await purgeAuthSessionState("logout");
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
      <Fragment key={authorizationScope(user, token)}>{children}</Fragment>
    </UserAuthContext.Provider>
  );
}

export function useUserAuth() {
  return useContext(UserAuthContext);
}
