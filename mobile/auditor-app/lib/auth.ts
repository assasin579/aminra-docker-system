/**
 * Auth — JWT login + secure storage.
 * Token lives in iOS Keychain / Android Keystore via expo-secure-store.
 * The same backend `/auth/login` endpoint as the web app.
 */
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';

const TOKEN_KEY   = 'aminra_auditor_token';
const PROFILE_KEY = 'aminra_auditor_profile';

export type UserProfile = {
  id:          string;
  email:       string;
  role:        'business' | 'provider';
  status:      string;
  company_name: string;
  is_owner:    boolean;
  tenant_id:   string | null;
};

export const API_BASE = (Constants.expoConfig?.extra?.apiBaseUrl as string)
  ?? 'https://dev-web.silvergem.org';

export async function login(email: string, password: string): Promise<{ token: string; user: UserProfile }> {
  // The auditor app accepts only provider-role accounts (auditor sub-role).
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, role: 'provider' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Đăng nhập thất bại');
  }
  const data = await res.json();
  if (data.user.role !== 'provider') {
    throw new Error('Tài khoản không phải tổ chức cấp chứng nhận');
  }
  await SecureStore.setItemAsync(TOKEN_KEY, data.access_token);
  await SecureStore.setItemAsync(PROFILE_KEY, JSON.stringify(data.user));
  return { token: data.access_token, user: data.user };
}

export async function loadSession(): Promise<{ token: string; user: UserProfile } | null> {
  const token = await SecureStore.getItemAsync(TOKEN_KEY);
  const profileJson = await SecureStore.getItemAsync(PROFILE_KEY);
  if (!token || !profileJson) return null;
  try {
    return { token, user: JSON.parse(profileJson) as UserProfile };
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(PROFILE_KEY);
}

export async function verifyToken(token: string): Promise<UserProfile | null> {
  try {
    const r = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return null;
    return (await r.json()) as UserProfile;
  } catch {
    return null;
  }
}
