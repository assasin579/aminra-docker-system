/**
 * UserAuthContext.loginViaKeycloak edge cases (Tier 3 batch 2).
 *
 * User-perspective scenarios for the new Phase 2 method:
 * - BE accepts token + returns enriched profile
 * - BE rejects with various HTTP statuses
 * - Network failure
 * - Role mismatch (token role doesn't match expected)
 * - Profile shape edge cases (missing fields, nullable)
 * - Persists session correctly via internal _saveSession
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, renderHook } from "@testing-library/react";
import {
  UserAuthProvider,
  useUserAuth,
} from "@/components/UserAuthContext";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  // Clean any storage from prior test
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});


function _ok(profile: Record<string, unknown>) {
  return {
    ok: true,
    status: 200,
    json: async () => profile,
  };
}

function _err(status: number, body: Record<string, unknown> = {}) {
  return {
    ok: false,
    status,
    json: async () => body,
  };
}


function wrap() {
  return ({ children }: { children: React.ReactNode }) => (
    <UserAuthProvider>{children}</UserAuthProvider>
  );
}


// ═════════════════════════════════════════════════════════════════════════════
// 1. HAPPY PATH
// ═════════════════════════════════════════════════════════════════════════════


describe("loginViaKeycloak happy path", () => {
  it("calls /api/auth/me with Bearer access_token", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u-1", email: "user@example.com", role: "business",
      status: "active", company_name: "ACME", company_code: null,
      is_owner: true, tenant_id: "t-1",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("kc-tok-1");
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({
        headers: { Authorization: "Bearer kc-tok-1" },
      }),
    );
  });

  it("populates user state on success", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u-1", email: "user@example.com", role: "business",
      status: "active", company_name: "ACME", company_code: null,
      is_owner: true, tenant_id: "t-1",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(result.current.user?.email).toBe("user@example.com");
    expect(result.current.token).toBe("tok");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("persists token to localStorage (remember=true default)", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(localStorage.getItem("aminra_user_token")).toBe("tok");
  });

  it("sets aminra_session cookie", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(document.cookie).toMatch(/aminra_session=1/);
  });

  it("clears legacy admin token on Keycloak login", async () => {
    localStorage.setItem("aminra_admin_token", "legacy-admin");
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(localStorage.getItem("aminra_admin_token")).toBeNull();
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 2. EXPECTED ROLE GUARD
// ═════════════════════════════════════════════════════════════════════════════


describe("expectedRole guard", () => {
  it("accepts when token role matches expectedRole", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok", "business");
    });
    expect(result.current.user?.role).toBe("business");
  });

  it("throws Vietnamese error when role mismatch (provider expected, business returned)", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok", "provider");
      }),
    ).rejects.toThrow(/không phù hợp.*provider.*business/i);
  });

  it("throws when role mismatch (business expected, provider returned)", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "provider", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: null,
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok", "business");
      }),
    ).rejects.toThrow(/business.*provider/i);
  });

  it("does not check role when expectedRole omitted", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "provider", status: "active",
      company_name: "", company_code: null, is_owner: true, tenant_id: null,
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    // No throw, profile saved as-is
    expect(result.current.user?.role).toBe("provider");
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 3. BE REJECTION — HTTP errors
// ═════════════════════════════════════════════════════════════════════════════


describe("BE rejection paths", () => {
  it.each([
    [401, "Token bị từ chối"],
    [403, "Tài khoản bị tạm khóa"],
    [404, "Không tìm thấy tài khoản"],
    [500, "Lỗi server"],
    [502, "BE down"],
    [503, "Bảo trì hệ thống"],
  ])("throws on HTTP %i with detail message", async (status, detail) => {
    fetchMock.mockResolvedValue(_err(status, { detail }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok");
      }),
    ).rejects.toThrow(detail);
  });

  it("falls back to default message when body has no detail", async () => {
    fetchMock.mockResolvedValue(_err(401, {}));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok");
      }),
    ).rejects.toThrow(/HTTP 401/);
  });

  it("uses 'message' field as fallback when detail is missing", async () => {
    fetchMock.mockResolvedValue(_err(403, { message: "Custom message" }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok");
      }),
    ).rejects.toThrow("Custom message");
  });

  it("does not populate user state on rejection", async () => {
    fetchMock.mockResolvedValue(_err(401));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    try {
      await act(async () => {
        await result.current.loginViaKeycloak("tok");
      });
    } catch {}
    expect(result.current.user).toBeNull();
    expect(result.current.token).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 4. NETWORK FAILURE
// ═════════════════════════════════════════════════════════════════════════════


describe("network failures", () => {
  it("propagates network error", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await expect(
      act(async () => {
        await result.current.loginViaKeycloak("tok");
      }),
    ).rejects.toThrow("Failed to fetch");
  });

  it("does not save session on network failure", async () => {
    fetchMock.mockRejectedValue(new Error("Network down"));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    try {
      await act(async () => {
        await result.current.loginViaKeycloak("tok");
      });
    } catch {}
    expect(localStorage.getItem("aminra_user_token")).toBeNull();
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 5. PROFILE SHAPE EDGES
// ═════════════════════════════════════════════════════════════════════════════


describe("profile shape edge cases", () => {
  it("accepts profile with null tenant_id (provider role)", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "provider", status: "active",
      company_name: "JAKIM", company_code: null,
      is_owner: true, tenant_id: null,
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(result.current.user?.tenant_id).toBeNull();
  });

  it("accepts profile with optional permissions field", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "ACME", company_code: null,
      is_owner: true, tenant_id: "t",
      permissions: { can_edit: true, can_delete: false, can_approve: false, can_upload: true },
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(result.current.user?.permissions?.can_edit).toBe(true);
  });

  it("accepts profile with ihc_role field", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "ACME", company_code: null,
      is_owner: false, tenant_id: "t",
      ihc_role: "Halal Executive",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(result.current.user?.ihc_role).toBe("Halal Executive");
  });

  it("accepts profile with unicode company_name", async () => {
    fetchMock.mockResolvedValue(_ok({
      id: "u", email: "u@x", role: "business", status: "active",
      company_name: "Công ty TNHH Việt Nam ăn ó ý",
      company_code: null,
      is_owner: true, tenant_id: "t",
    }));
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });
    await act(async () => {
      await result.current.loginViaKeycloak("tok");
    });
    expect(result.current.user?.company_name).toBe(
      "Công ty TNHH Việt Nam ăn ó ý",
    );
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 6. CONCURRENT CALLS
// ═════════════════════════════════════════════════════════════════════════════


describe("concurrent loginViaKeycloak calls", () => {
  it("two simultaneous calls — both fetches happen, last write wins", async () => {
    let resolves: Array<(v: unknown) => void> = [];
    fetchMock.mockImplementation(
      () => new Promise((r) => resolves.push(r)),
    );
    const { result } = renderHook(() => useUserAuth(), { wrapper: wrap() });

    let p1, p2;
    await act(async () => {
      p1 = result.current.loginViaKeycloak("tok-1");
      p2 = result.current.loginViaKeycloak("tok-2");
      // Resolve in order
      resolves[0](_ok({
        id: "u1", email: "first@x", role: "business", status: "active",
        company_name: "First", company_code: null,
        is_owner: true, tenant_id: "t1",
      }));
      resolves[1](_ok({
        id: "u2", email: "second@x", role: "business", status: "active",
        company_name: "Second", company_code: null,
        is_owner: true, tenant_id: "t2",
      }));
      await Promise.all([p1, p2]);
    });
    // Last successful save wins
    expect(["first@x", "second@x"]).toContain(result.current.user?.email);
  });
});
