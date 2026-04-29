"use client";

/**
 * Feature flag client — single fetch per session, hydrate `useFeature(name)`.
 *
 * Pairs with backend at GET /api/feature-flags/me which returns:
 *   { tenant_id: string, flags: { [name]: boolean } }
 *
 * Closed-default: unknown / not-yet-fetched flags resolve to false. Components
 * gating new features stay invisible until the user logs in AND the flags
 * fetch resolves AND the flag is on.
 *
 * Usage:
 *
 *   // 1. Wrap the app once (e.g. in app/layout.tsx after auth provider)
 *   <FeatureFlagProvider>{children}</FeatureFlagProvider>
 *
 *   // 2. Read inside components
 *   const ihcOn = useFeature("ihc_meetings_v1");
 *   if (!ihcOn) return null;
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// 60s TTL with stale-while-revalidate: serve stale on re-mount while a fresh
// fetch races in the background. Avoids a flag toggle being visible mid-session
// for too long when admin flips a tenant override.
const TTL_MS = 60_000;

type FlagsResponse = {
  tenant_id: string | null;
  flags: Record<string, boolean>;
};

type CacheEntry = { data: FlagsResponse; fetchedAt: number };

type ContextValue = {
  flags: Record<string, boolean>;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
};

const FeatureFlagContext = createContext<ContextValue>({
  flags: {},
  isLoading: false,
  error: null,
  refresh: async () => {},
});

let inflight: Promise<FlagsResponse> | null = null;
let cache: CacheEntry | null = null;

async function fetchFlags(token: string | null): Promise<FlagsResponse> {
  // De-dupe concurrent callers (Provider mount + first hook render race)
  if (inflight) return inflight;

  const headers: HeadersInit = { Accept: "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  inflight = fetch("/api/api/feature-flags/me", {
    headers,
    credentials: "same-origin",
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as FlagsResponse;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

interface ProviderProps {
  children: ReactNode;
  /** JWT for authenticated calls. If null, fetch is skipped (returns empty flags). */
  token?: string | null;
}

export function FeatureFlagProvider({ children, token = null }: ProviderProps) {
  const [data, setData] = useState<FlagsResponse | null>(() => {
    if (cache && Date.now() - cache.fetchedAt < TTL_MS) return cache.data;
    return null;
  });
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const fresh = await fetchFlags(token);
      cache = { data: fresh, fetchedAt: Date.now() };
      setData(fresh);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    // Only fetch when authenticated; logged-out users see closed-default flags.
    if (!token) return;
    if (cache && Date.now() - cache.fetchedAt < TTL_MS) return;
    void refresh();
  }, [token, refresh]);

  const value = useMemo<ContextValue>(
    () => ({
      flags: data?.flags ?? {},
      isLoading,
      error,
      refresh,
    }),
    [data, isLoading, error, refresh],
  );

  return (
    <FeatureFlagContext.Provider value={value}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

/**
 * Read a single feature flag. Returns false until flags are fetched.
 *
 *   const enabled = useFeature("ihc_meetings_v1");
 *   if (!enabled) return null;
 */
export function useFeature(name: string): boolean {
  const { flags } = useContext(FeatureFlagContext);
  return flags[name] === true;
}

/** Read all flags + loading/error state. Use sparingly (debug pages, admin). */
export function useFeatureFlags(): ContextValue {
  return useContext(FeatureFlagContext);
}

/** Manual cache invalidation — call after admin updates a flag in same session. */
export function invalidateFeatureFlagCache(): void {
  cache = null;
  inflight = null;
}
