export type AuthPurgeReason =
  | "login_start"
  | "logout"
  | "callback_mismatch"
  | "self_reset"
  | "auth_rejected"
  | "storage_migration"
  | "unknown";

export const AUTH_SESSION_EVENT = "aminra:auth-session-changed";

const AUTH_KEYS = [
  "aminra_user_token",
  "aminra_user_profile",
  "aminra_admin_token",
];

const AUTH_TRANSACTION_KEYS = [
  "aminra_auth_login_started_at",
  "aminra_auth_expected_return_to",
  "aminra_auth_nonce",
];

function removeKeys(storage: Storage | undefined): void {
  if (!storage) return;
  for (const key of [...AUTH_KEYS, ...AUTH_TRANSACTION_KEYS]) storage.removeItem(key);

  const oidcKeys: string[] = [];
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i);
    if (key?.startsWith("oidc.")) oidcKeys.push(key);
  }
  for (const key of oidcKeys) storage.removeItem(key);
}

async function deleteAminraCaches(): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((key) => key.startsWith("aminra-")).map((key) => caches.delete(key)),
    );
  } catch {
    // Best-effort cache cleanup: auth state removal above is the critical path.
  }
}

export function notifyAuthSessionChanged(reason: AuthPurgeReason | "session_saved" = "unknown"): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(AUTH_SESSION_EVENT, {
      detail: { reason, at: Date.now() },
    }),
  );
}

export function removeStoredAuthSessionKeys(storage: Storage | undefined): void {
  removeKeys(storage);
}

export function removeLegacyAdminSessionKey(storage: Storage | undefined): void {
  storage?.removeItem("aminra_admin_token");
}

export async function purgeAuthSessionState(
  reason: AuthPurgeReason = "unknown",
): Promise<void> {
  if (typeof window !== "undefined") {
    removeKeys(window.localStorage);
    removeKeys(window.sessionStorage);
    try {
      document.cookie = "aminra_session=; path=/; max-age=0";
    } catch {}
    try {
      window.sessionStorage.setItem("aminra_auth_last_purge_reason", reason);
    } catch {}
  } else {
    removeKeys(globalThis.localStorage);
    removeKeys(globalThis.sessionStorage);
  }
  await deleteAminraCaches();
  notifyAuthSessionChanged(reason);
}
