import { beforeEach, describe, expect, it, vi } from "vitest";

const deletedCaches: string[] = [];

beforeEach(() => {
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
    expect(localStorage.getItem("aminra_file_versions_demo")).toBe("draft-data");
    expect(deletedCaches).toEqual(["aminra-v5", "aminra-v6"]);
  });
});
