/** Private browser data belongs to both the application actor and current tenant. */
export function privateCacheKey(actorId: string | undefined, tenantId: string | null | undefined, kind: string, filename = ''): string | null {
  if (!actorId || !tenantId) return null;
  return ['aminra_private:v1', actorId, tenantId, kind, filename].map(encodeURIComponent).join(':');
}

/** Legacy filename-only caches cannot be attributed safely; discard them. */
export function clearPrivateClientData(storage: Storage): void {
  const keys: string[] = [];
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i);
    if (key && ['aminra_private', 'aminra_file_versions_', 'aminra_full_report_', 'aminra_eval_'].some(prefix => key.startsWith(prefix))) keys.push(key);
  }
  for (const key of keys) storage.removeItem(key);
}
