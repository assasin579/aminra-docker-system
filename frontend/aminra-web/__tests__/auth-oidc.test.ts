/**
 * Unit tests for lib/auth-oidc (ADR-005 Phase 2a).
 *
 * Mocks oidc-client-ts so the suite runs without a Keycloak server.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  mockSigninRedirect: vi.fn(),
  mockSigninRedirectCallback: vi.fn(),
  mockGetUser: vi.fn(),
  mockSignoutRedirect: vi.fn(),
  mockRemoveUser: vi.fn(),
}));

const {
  mockSigninRedirect,
  mockSigninRedirectCallback,
  mockGetUser,
  mockSignoutRedirect,
  mockRemoveUser,
} = hoisted;

vi.mock("oidc-client-ts", () => ({
  Log: {
    setLogger: vi.fn(),
    setLevel: vi.fn(),
    WARN: 1,
  },
  WebStorageStateStore: class {
    constructor(_: unknown) {}
  },
  UserManager: class {
    signinRedirect = hoisted.mockSigninRedirect;
    signinRedirectCallback = hoisted.mockSigninRedirectCallback;
    getUser = hoisted.mockGetUser;
    signoutRedirect = hoisted.mockSignoutRedirect;
    removeUser = hoisted.mockRemoveUser;
    constructor(_: unknown) {}
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(async () => {
  const mod = await import("@/lib/auth-oidc");
  mod._resetOidcManagerForTests();
});

describe("isOidcEnabled", () => {
  it("returns false when env flag missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "");
    const { isOidcEnabled } = await import("@/lib/auth-oidc");
    expect(isOidcEnabled()).toBe(false);
    vi.unstubAllEnvs();
  });

  it("returns true only for exact 'true' value", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const { isOidcEnabled } = await import("@/lib/auth-oidc");
    expect(isOidcEnabled()).toBe(true);
    vi.unstubAllEnvs();
  });

  it("returns false for non-true strings", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "TRUE");
    const { isOidcEnabled } = await import("@/lib/auth-oidc");
    expect(isOidcEnabled()).toBe(false);
    vi.unstubAllEnvs();
  });
});

describe("signinRedirect", () => {
  it("forwards returnTo into UserManager state", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const { signinRedirect } = await import("@/lib/auth-oidc");
    await signinRedirect("/dashboard/business");
    expect(mockSigninRedirect).toHaveBeenCalledWith({
      state: "/dashboard/business",
      extraQueryParams: { prompt: "login" },
    });
    vi.unstubAllEnvs();
  });

  it("defaults returnTo to '/' when omitted", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const { signinRedirect } = await import("@/lib/auth-oidc");
    await signinRedirect();
    expect(mockSigninRedirect).toHaveBeenCalledWith({
      state: "/",
      extraQueryParams: { prompt: "login" },
    });
    vi.unstubAllEnvs();
  });

  it("purges stale AMINRA and OIDC storage before starting a new SSO login", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    localStorage.setItem("aminra_user_token", "old-token");
    localStorage.setItem("aminra_user_profile", "old-profile");
    localStorage.setItem("aminra_admin_token", "old-admin");
    sessionStorage.setItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend", "old-oidc");
    sessionStorage.setItem("aminra_user_profile", "old-session-profile");

    const { signinRedirect } = await import("@/lib/auth-oidc");
    await signinRedirect("/admin");

    expect(localStorage.getItem("aminra_user_token")).toBeNull();
    expect(localStorage.getItem("aminra_user_profile")).toBeNull();
    expect(localStorage.getItem("aminra_admin_token")).toBeNull();
    expect(sessionStorage.getItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend")).toBeNull();
    expect(sessionStorage.getItem("aminra_user_profile")).toBeNull();
    expect(mockSigninRedirect).toHaveBeenCalledWith({
      state: "/admin",
      extraQueryParams: { prompt: "login" },
    });
    vi.unstubAllEnvs();
  });

  it("throws when feature flag is off", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "false");
    const { signinRedirect } = await import("@/lib/auth-oidc");
    await expect(signinRedirect("/x")).rejects.toThrow(/AUTH_KEYCLOAK_ENABLED=false/);
    vi.unstubAllEnvs();
  });
});

describe("handleSigninCallback", () => {
  it("returns user + parsed returnTo from state", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const fakeUser = {
      access_token: "kc-token",
      state: "/dashboard/business",
    };
    mockSigninRedirectCallback.mockResolvedValue(fakeUser);
    const { handleSigninCallback } = await import("@/lib/auth-oidc");
    const out = await handleSigninCallback();
    expect(out.user).toBe(fakeUser);
    expect(out.returnTo).toBe("/dashboard/business");
    vi.unstubAllEnvs();
  });

  it("falls back to '/' when state is not a string", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    mockSigninRedirectCallback.mockResolvedValue({
      access_token: "x",
      state: { obj: 1 },
    });
    const { handleSigninCallback } = await import("@/lib/auth-oidc");
    const out = await handleSigninCallback();
    expect(out.returnTo).toBe("/");
    vi.unstubAllEnvs();
  });
});

describe("getOidcUser", () => {
  it("returns null when flag off (no UserManager construction)", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "false");
    const { getOidcUser } = await import("@/lib/auth-oidc");
    expect(await getOidcUser()).toBeNull();
    expect(mockGetUser).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });

  it("delegates to UserManager when flag on", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    mockGetUser.mockResolvedValue({ access_token: "abc" });
    const { getOidcUser } = await import("@/lib/auth-oidc");
    const u = await getOidcUser();
    expect(u).toEqual({ access_token: "abc" });
    expect(mockGetUser).toHaveBeenCalledOnce();
    vi.unstubAllEnvs();
  });
});

describe("signoutRedirect", () => {
  it("falls back to direct end-session with a preserved id_token_hint when local OIDC state was purged first", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_URL", "https://auth.example.com");
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_REALM", "aminra");
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_CLIENT_ID", "aminra-frontend");
    mockSignoutRedirect.mockRejectedValue(new Error("end-session disabled"));
    const { signoutRedirect, _buildEndSessionUrlForTests } = await import("@/lib/auth-oidc");
    await signoutRedirect({ id_token: "id-token-before-purge" } as never);
    expect(mockSignoutRedirect).toHaveBeenCalledOnce();
    expect(mockRemoveUser).toHaveBeenCalledOnce();
    const endSessionUrl = _buildEndSessionUrlForTests("id-token-before-purge");
    expect(endSessionUrl).toContain(
      "https://auth.example.com/realms/aminra/protocol/openid-connect/logout",
    );
    expect(endSessionUrl).toContain("id_token_hint=id-token-before-purge");
    expect(endSessionUrl).toContain("client_id=aminra-frontend");
    vi.unstubAllEnvs();
  });

  it("is a no-op when flag off", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "false");
    const { signoutRedirect } = await import("@/lib/auth-oidc");
    await signoutRedirect();
    expect(mockSignoutRedirect).not.toHaveBeenCalled();
    expect(mockRemoveUser).not.toHaveBeenCalled();
    vi.unstubAllEnvs();
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// EXPANSION (Tier 3 batch 3) — env edge cases + manager singleton + flag transitions
// ═════════════════════════════════════════════════════════════════════════════


describe("getOidcManager singleton", () => {
  it("throws when called from server-side context", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const originalWindow = (globalThis as { window?: unknown }).window;
    Object.defineProperty(globalThis, "window", {
      value: undefined,
      configurable: true,
      writable: true,
    });
    const { getOidcManager } = await import("@/lib/auth-oidc");
    expect(() => getOidcManager()).toThrow(/browser context/);
    Object.defineProperty(globalThis, "window", {
      value: originalWindow,
      configurable: true,
      writable: true,
    });
    vi.unstubAllEnvs();
  });

  it("throws clear error when flag off", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "false");
    const { getOidcManager } = await import("@/lib/auth-oidc");
    expect(() => getOidcManager()).toThrow(/AUTH_KEYCLOAK_ENABLED=false/);
    vi.unstubAllEnvs();
  });

  it("reuses singleton across multiple invocations", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const { getOidcManager } = await import("@/lib/auth-oidc");
    const m1 = getOidcManager();
    const m2 = getOidcManager();
    const m3 = getOidcManager();
    expect(m1).toBe(m2);
    expect(m2).toBe(m3);
    vi.unstubAllEnvs();
  });

  it("_resetOidcManagerForTests releases singleton", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const { getOidcManager, _resetOidcManagerForTests } =
      await import("@/lib/auth-oidc");
    const m1 = getOidcManager();
    _resetOidcManagerForTests();
    const m2 = getOidcManager();
    expect(m1).not.toBe(m2);
    vi.unstubAllEnvs();
  });
});


describe("env var fallbacks", () => {
  it.each([
    ["http://keycloak:8080", "aminra", "aminra-frontend"],
    ["https://auth.aminra.vn", "aminra-prod", "aminra-frontend-prod"],
    ["http://localhost:8180", "test-realm", "test-client"],
  ])("respects custom env: %s / %s / %s",
    async (url, realm, clientId) => {
      vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
      vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_URL", url);
      vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_REALM", realm);
      vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_CLIENT_ID", clientId);
      const { getOidcManager } = await import("@/lib/auth-oidc");
      const mgr = getOidcManager();
      expect(mgr).toBeDefined();
      vi.unstubAllEnvs();
    });
});


describe("isOidcEnabled edge values", () => {
  it.each([
    ["true", true],
    ["false", false],
    ["", false],
    ["TRUE", false],
    ["1", false],
    ["yes", false],
    [" true ", false],
    ["true ", false],
  ])("isOidcEnabled('%s') returns %s",
    async (value, expected) => {
      vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", value);
      const { isOidcEnabled } = await import("@/lib/auth-oidc");
      expect(isOidcEnabled()).toBe(expected);
      vi.unstubAllEnvs();
    });
});


describe("signoutRedirect edge cases", () => {
  it("does not throw when removeUser also fails", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    mockSignoutRedirect.mockRejectedValue(new Error("rp-init failed"));
    mockRemoveUser.mockRejectedValue(new Error("storage failed"));
    const { signoutRedirect } = await import("@/lib/auth-oidc");
    await expect(signoutRedirect()).resolves.toBeUndefined();
    expect(mockRemoveUser).toHaveBeenCalledOnce();
    vi.unstubAllEnvs();
  });
});


describe("handleSigninCallback edge cases", () => {
  it("returns user object as-is from oidc-client-ts", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    const fakeUser = {
      access_token: "tok",
      id_token: "id-tok",
      refresh_token: "rt",
      expires_at: Math.floor(Date.now() / 1000) + 900,
      profile: { sub: "kc-1" },
      state: "/dashboard/business",
    };
    mockSigninRedirectCallback.mockResolvedValue(fakeUser);
    const { handleSigninCallback } = await import("@/lib/auth-oidc");
    const out = await handleSigninCallback();
    expect(out.user).toBe(fakeUser);
    vi.unstubAllEnvs();
  });

  it("propagates oidc-client-ts errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED", "true");
    mockSigninRedirectCallback.mockRejectedValue(
      new Error("PKCE verifier missing"),
    );
    const { handleSigninCallback } = await import("@/lib/auth-oidc");
    await expect(handleSigninCallback()).rejects.toThrow(/PKCE verifier missing/);
    vi.unstubAllEnvs();
  });
});
