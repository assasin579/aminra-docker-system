import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { router } from 'expo-router';
import { loadSession, login as apiLogin, logout as apiLogout, UserProfile, verifyToken } from './auth';
import { setUnauthorizedHandler } from './api';

interface AuthCtx {
  token: string | null;
  user:  UserProfile | null;
  loading: boolean;
  signIn:  (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({
  token: null, user: null, loading: true,
  signIn: async () => {}, signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user,  setUser]  = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(async () => {
    await apiLogout();
    setToken(null);
    setUser(null);
    router.replace('/(auth)/login');
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => { signOut(); });
  }, [signOut]);

  useEffect(() => {
    (async () => {
      const session = await loadSession();
      if (!session) { setLoading(false); return; }

      const fresh = await verifyToken(session.token);
      if (fresh) {
        setToken(session.token);
        setUser(fresh);
      } else {
        await apiLogout();
      }
      setLoading(false);
    })();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const { token: t, user: u } = await apiLogin(email, password);
    setToken(t);
    setUser(u);
  }, []);

  return (
    <Ctx.Provider value={{ token, user, loading, signIn, signOut }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
