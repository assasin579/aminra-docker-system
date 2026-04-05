'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

interface AdminAuthState {
  isAdmin: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AdminAuthContext = createContext<AdminAuthState>({
  isAdmin: false, token: null,
  login: async () => {}, logout: () => {},
});

const TOKEN_KEY = 'aminra_admin_token';
const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  // Restore token from localStorage and verify with backend
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) return;
    fetch(`${API}/admin/verify`, { headers: { Authorization: `Bearer ${stored}` } })
      .then(r => r.json())
      .then(d => { if (d.valid) setToken(stored); else localStorage.removeItem(TOKEN_KEY); })
      .catch(() => localStorage.removeItem(TOKEN_KEY));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API}/admin/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Đăng nhập thất bại');
    }
    const { token: t } = await res.json();
    setToken(t);
    localStorage.setItem(TOKEN_KEY, t);
  }, []);

  const logout = useCallback(() => {
    if (token) {
      fetch(`${API}/admin/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
    }
    setToken(null);
    localStorage.removeItem(TOKEN_KEY);
    try { sessionStorage.clear(); } catch {}
  }, [token]);

  return (
    <AdminAuthContext.Provider value={{ isAdmin: !!token, token, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  return useContext(AdminAuthContext);
}
