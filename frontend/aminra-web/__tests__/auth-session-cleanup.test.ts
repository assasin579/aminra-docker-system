import { beforeEach, describe, expect, it, vi } from "vitest";

const deletedCaches: string[] = [];

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  sessionStorage.clear();
  deletedCaches.length = 0;
  Object.defineProperty(globalThis, "caches", {
    configurable: true,
    value: {
      keys: vi.fn(async () => ["aminra-v5", "aminra-v6", "third-party-cache"]),
      delete: vi.fn(async (key: string) => {
        deletedCaches.push(key);
        return true;
      }),
    },
  });
});

describe("purgeAuthSessionState", () => {
  it("removes AMINRA and OIDC auth state while preserving non-auth preferences", async () => {
    localStorage.setItem("aminra_user_token", "jwt-local");
    localStorage.setItem("aminra_user_profile", "profile-local");
    localStorage.setItem("aminra_admin_token", "admin-local");
    localStorage.setItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend", "oidc-local");
    localStorage.setItem("oidc.signin:state", "signin-local");
    localStorage.setItem("aminra_lang", "vi");
    localStorage.setItem("aminra_file_versions_demo", "draft-data");
    sessionStorage.setItem("aminra_user_token", "jwt-session");
    sessionStorage.setItem("aminra_user_profile", "profile-session");
    sessionStorage.setItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend", "oidc-session");

    const { purgeAuthSessionState } = await import("@/lib/auth-session-cleanup");
    await purgeAuthSessionState();

    expect(localStorage.getItem("aminra_user_token")).toBeNull();
    expect(localStorage.getItem("aminra_user_profile")).toBeNull();
    expect(localStorage.getItem("aminra_admin_token")).toBeNull();
    expect(localStorage.getItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend")).toBeNull();
    expect(localStorage.getItem("oidc.signin:state")).toBeNull();
    expect(sessionStorage.getItem("aminra_user_token")).toBeNull();
    expect(sessionStorage.getItem("aminra_user_profile")).toBeNull();
    expect(sessionStorage.getItem("oidc.user:https://auth.silvergem.org/realms/aminra:aminra-frontend")).toBeNull();
    expect(localStorage.getItem("aminra_lang")).toBe("vi");
    // Filename-only history contains private analysis and must not survive account changes.
    expect(localStorage.getItem("aminra_file_versions_demo")).toBeNull();
    expect(deletedCaches).toEqual(["aminra-v5", "aminra-v6"]);
  });

  it("broadcasts the auth-session event and records the cleanup reason", async () => {
    const events: string[] = [];
    window.addEventListener("aminra:auth-session-changed", (event) => {
      events.push((event as CustomEvent).detail?.reason);
    });

    const { purgeAuthSessionState } = await import("@/lib/auth-session-cleanup");
    await purgeAuthSessionState("login_start");

    expect(events).toEqual(["login_start"]);
    expect(sessionStorage.getItem("aminra_auth_last_purge_reason")).toBe("login_start");
  });

  it("removes AMINRA auth transaction markers but preserves unrelated preferences", async () => {
    sessionStorage.setItem("aminra_auth_login_started_at", "123");
    sessionStorage.setItem("aminra_auth_expected_return_to", "/admin");
    sessionStorage.setItem("aminra_auth_nonce", "nonce");
    localStorage.setItem("aminra_lang", "vi");

    const { purgeAuthSessionState } = await import("@/lib/auth-session-cleanup");
    await purgeAuthSessionState("logout");

    expect(sessionStorage.getItem("aminra_auth_login_started_at")).toBeNull();
    expect(sessionStorage.getItem("aminra_auth_expected_return_to")).toBeNull();
    expect(sessionStorage.getItem("aminra_auth_nonce")).toBeNull();
    expect(localStorage.getItem("aminra_lang")).toBe("vi");
  });
});

it("requests legacy offline private database deletion and reports blocked deletion without hanging logout", async () => {
  const { clearPrivateOfflineState } = await import("@/lib/auth-session-cleanup");
  let request: { onsuccess?: () => void; onerror?: () => void; onblocked?: () => void } = {};
  const deleteDatabase = vi.fn(() => { request = {}; return request; });
  vi.stubGlobal("indexedDB", { deleteDatabase });
  const success = clearPrivateOfflineState(); request.onsuccess?.(); await expect(success).resolves.toBe(true);
  const blocked = clearPrivateOfflineState(); request.onblocked?.(); await expect(blocked).resolves.toBe(false);
  expect(deleteDatabase).toHaveBeenCalledWith("aminra-offline");
});
