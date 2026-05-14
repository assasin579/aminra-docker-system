/**
 * Auth — Keycloak password grant + secure storage (Phase 4c-9).
 *
 * Token lives in iOS Keychain / Android Keystore via expo-secure-store.
 * Login goes directly to Keycloak via OAuth2 Resource Owner Password
 * Credentials grant (RFC 6749 §4.3) — acceptable for a first-party
 * native app. After grant, `/api/auth/me` resolves the AMINRA profile
 * and enforces the provider-role guard.
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

export const KEYCLOAK_URL = (Constants.expoConfig?.extra?.keycloakUrl as string)
  ?? 'https://auth.silvergem.org';
export const KEYCLOAK_REALM = (Constants.expoConfig?.extra?.keycloakRealm as string)
  ?? 'aminra';
export const KEYCLOAK_CLIENT_ID = (Constants.expoConfig?.extra?.keycloakClientId as string)
  ?? 'aminra-frontend';

export async function login(email: string, password: string): Promise<{ token: string; user: UserProfile }> {
  const tokenRes = await fetch(
    `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'password',
        client_id: KEYCLOAK_CLIENT_ID,
        username: email,
        password,
      }).toString(),
    },
  );
  if (!tokenRes.ok) {
    const err = await tokenRes.json().catch(() => ({}));
    // Keycloak returns `error_description` on grant failure; surface it to UX.
    throw new Error(err.error_description ?? err.error ?? 'Đăng nhập thất bại');
  }
  const { access_token } = await tokenRes.json() as { access_token: string };

  // Resolve the AMINRA profile (JIT-provisioned on first call). The
  // auditor app accepts only provider-role accounts.
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  if (!meRes.ok) {
    const err = await meRes.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Không xác thực được tài khoản');
  }
  const user = (await meRes.json()) as UserProfile;
  if (user.role !== 'provider') {
    throw new Error('Tài khoản không phải tổ chức cấp chứng nhận');
  }

  await SecureStore.setItemAsync(TOKEN_KEY, access_token);
  await SecureStore.setItemAsync(PROFILE_KEY, JSON.stringify(user));
  return { token: access_token, user };
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
