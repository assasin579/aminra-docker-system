'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

export type UserRole = 'business' | 'provider';

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
}

interface UserAuthState {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  loginBusiness: (email: string, password: string) => Promise<void>;
  loginProvider: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const UserAuthContext = createContext<UserAuthState>({
  user: null, token: null, isAuthenticated: false, loading: true,
  loginBusiness: async () => {}, loginProvider: async () => {}, logout: () => {},
});

const TOKEN_KEY   = 'aminra_user_token';
const PROFILE_KEY = 'aminra_user_profile';

async function apiLogin(email: string, password: string) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Đăng nhập thất bại');
  }
  return res.json() as Promise<{ access_token: string; user: UserProfile }>;
}

export function UserAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken]   = useState<string | null>(null);
  const [user, setUser]     = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from localStorage and verify
  useEffect(() => {
    const storedToken   = localStorage.getItem(TOKEN_KEY);
    const storedProfile = localStorage.getItem(PROFILE_KEY);
    if (!storedToken || !storedProfile) { setLoading(false); return; }

    // Optimistic restore
    setToken(storedToken);
    setUser(JSON.parse(storedProfile));

    // Verify token is still valid
    fetch('/api/auth/me', { headers: { Authorization: `Bearer ${storedToken}` } })
      .then(r => r.ok ? r.json() : null)
      .then(profile => {
        if (profile) {
          setUser(profile);
          localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
        } else {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(PROFILE_KEY);
          setToken(null);
          setUser(null);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const _saveSession = useCallback((t: string, u: UserProfile) => {
    setToken(t);
    setUser(u);
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(PROFILE_KEY, JSON.stringify(u));
  }, []);

  const loginBusiness = useCallback(async (email: string, password: string) => {
    const { access_token, user: u } = await apiLogin(email, password);
    if (u.role !== 'business') throw new Error('Tài khoản không phải doanh nghiệp');
    _saveSession(access_token, u);
  }, [_saveSession]);

  const loginProvider = useCallback(async (email: string, password: string) => {
    const { access_token, user: u } = await apiLogin(email, password);
    if (u.role !== 'provider') throw new Error('Tài khoản không phải tổ chức');
    _saveSession(access_token, u);
  }, [_saveSession]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(PROFILE_KEY);
    // Clear all session-scoped data (evaluation results, etc.)
    try { sessionStorage.clear(); } catch {}
  }, []);

  return (
    <UserAuthContext.Provider value={{
      user, token, isAuthenticated: !!token && !!user, loading,
      loginBusiness, loginProvider, logout,
    }}>
      {children}
    </UserAuthContext.Provider>
  );
}

export function useUserAuth() {
  return useContext(UserAuthContext);
}
