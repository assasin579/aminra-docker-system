const AUTH_KEYS = [
  "aminra_user_token",
  "aminra_user_profile",
  "aminra_admin_token",
];

function removeKeys(storage: Storage | undefined): void {
  if (!storage) return;
  for (const key of AUTH_KEYS) storage.removeItem(key);

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

export async function purgeAuthSessionState(): Promise<void> {
  if (typeof window !== "undefined") {
    removeKeys(window.localStorage);
    removeKeys(window.sessionStorage);
    try {
      document.cookie = "aminra_session=; path=/; max-age=0";
    } catch {}
  } else {
    removeKeys(globalThis.localStorage);
    removeKeys(globalThis.sessionStorage);
  }
  await deleteAminraCaches();
}
