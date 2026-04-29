"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { parseApiError } from "@/lib/apiError";

interface AdminAuthState {
  isAdmin: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AdminAuthContext = createContext<AdminAuthState>({
  isAdmin: false,
  token: null,
  login: async () => {},
  logout: () => {},
});

const TOKEN_KEY = "aminra_admin_token";
const API = "/api";

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  // Restore token from localStorage and verify with backend
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) return;
    fetch(`${API}/admin/verify`, {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.valid) setToken(stored);
        else localStorage.removeItem(TOKEN_KEY);
      })
      .catch(() => localStorage.removeItem(TOKEN_KEY));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API}/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseApiError(err, "Đăng nhập thất bại"));
    }
    const { token: t } = await res.json();
    setToken(t);
    localStorage.setItem(TOKEN_KEY, t);
    // Clear user session — admin and user sessions must not coexist
    localStorage.removeItem("aminra_user_token");
    localStorage.removeItem("aminra_user_profile");
    sessionStorage.removeItem("aminra_user_token");
    sessionStorage.removeItem("aminra_user_profile");
    document.cookie = "aminra_session=; path=/; max-age=0";
  }, []);

  const logout = useCallback(() => {
    if (token) {
      fetch(`${API}/admin/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    setToken(null);
    localStorage.removeItem(TOKEN_KEY);
    // Cross-context cleanup: never leave a stale user token after admin logout
    localStorage.removeItem("aminra_user_token");
    localStorage.removeItem("aminra_user_profile");
    document.cookie = "aminra_session=; path=/; max-age=0";
    try {
      sessionStorage.clear();
    } catch {}
  }, [token]);

  return (
    <AdminAuthContext.Provider
      value={{ isAdmin: !!token, token, login, logout }}
    >
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  return useContext(AdminAuthContext);
}
