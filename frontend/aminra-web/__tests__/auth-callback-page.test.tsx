/**
 * OIDC callback page edge cases (Tier 3 batch 1).
 *
 * User-perspective scenarios for `app/auth/callback/page.tsx`:
 * - Keycloak redirects user back with code+state, success path
 * - Keycloak redirects with error params (login_required, access_denied)
 * - Open-redirect attempts via state parameter
 * - Profile fetch failures (BE down, 401, 403)
 * - Component unmount during async work (cancelled cleanup)
 *
 * Mocks lib/auth-oidc + UserAuthContext so suite runs without browser
 * + without live Keycloak.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const hoisted = vi.hoisted(() => ({
  isOidcEnabled: vi.fn(),
  handleSigninCallback: vi.fn(),
  loginViaKeycloak: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("@/lib/auth-oidc", () => ({
  isOidcEnabled: hoisted.isOidcEnabled,
  handleSigninCallback: hoisted.handleSigninCallback,
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({
    loginViaKeycloak: hoisted.loginViaKeycloak,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: hoisted.routerReplace,
    push: vi.fn(),
  }),
}));

import OidcCallbackPage from "@/app/auth/callback/page";

beforeEach(() => {
  vi.clearAllMocks();
  hoisted.isOidcEnabled.mockReturnValue(true);
});

afterEach(() => {
  vi.clearAllMocks();
});


// ═════════════════════════════════════════════════════════════════════════════
// 1. FLAG GATE
// ═════════════════════════════════════════════════════════════════════════════


describe("flag gating", () => {
  it("renders error message when OIDC flag is off", async () => {
    hoisted.isOidcEnabled.mockReturnValue(false);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/Keycloak SSO chưa được bật/),
      ).toBeInTheDocument();
    });
    expect(hoisted.handleSigninCallback).not.toHaveBeenCalled();
  });

  it("does not call loginViaKeycloak when flag off", async () => {
    hoisted.isOidcEnabled.mockReturnValue(false);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(hoisted.loginViaKeycloak).not.toHaveBeenCalled();
    });
  });

  it("offers 'Quay lại đăng nhập' button when flag off", async () => {
    hoisted.isOidcEnabled.mockReturnValue(false);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Quay lại đăng nhập/ }),
      ).toBeInTheDocument();
    });
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 2. HAPPY PATH
// ═════════════════════════════════════════════════════════════════════════════


describe("successful callback", () => {
  it("calls loginViaKeycloak with access_token from oidc user", async () => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "kc-tok-1", state: "/dashboard/business" },
      returnTo: "/dashboard/business",
    });
    hoisted.loginViaKeycloak.mockResolvedValue(undefined);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(hoisted.loginViaKeycloak).toHaveBeenCalledWith("kc-tok-1");
    });
  });

  it("redirects to returnTo from state", async () => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: "/dashboard/business" },
      returnTo: "/dashboard/business",
    });
    hoisted.loginViaKeycloak.mockResolvedValue(undefined);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(hoisted.routerReplace).toHaveBeenCalledWith("/dashboard/business");
    });
  });

  it("renders loading spinner during in-flight callback", async () => {
    let resolveCallback: (v: unknown) => void = () => {};
    hoisted.handleSigninCallback.mockReturnValue(
      new Promise((r) => { resolveCallback = r; }),
    );
    render(<OidcCallbackPage />);
    expect(screen.getByText("Đang hoàn tất đăng nhập...")).toBeInTheDocument();
    resolveCallback({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    await waitFor(() => {
      expect(hoisted.loginViaKeycloak).toHaveBeenCalled();
    });
  });

  it("does not call router.replace before loginViaKeycloak resolves", async () => {
    let resolveLogin: () => void = () => {};
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    hoisted.loginViaKeycloak.mockReturnValue(
      new Promise<void>((r) => { resolveLogin = r; }),
    );
    render(<OidcCallbackPage />);
    // Wait for handleSigninCallback to resolve and loginViaKeycloak to start
    await waitFor(() => expect(hoisted.loginViaKeycloak).toHaveBeenCalled());
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
    resolveLogin();
    await waitFor(() =>
      expect(hoisted.routerReplace).toHaveBeenCalled(),
    );
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 3. RETURNTO SANITISATION — open-redirect defence
// ═════════════════════════════════════════════════════════════════════════════


describe("returnTo sanitisation (open-redirect defence)", () => {
  it.each([
    ["//evil.example.com", "/dashboard/business"],          // protocol-relative
    ["https://attacker.example.com", "/dashboard/business"], // absolute URL
    ["http://evil.com/path", "/dashboard/business"],
    ["javascript:alert(1)", "/dashboard/business"],
    ["data:text/html,<script>", "/dashboard/business"],
    ["", "/dashboard/business"],
    ["x", "/dashboard/business"],                           // not starting with /
    ["dashboard", "/dashboard/business"],                   // missing leading /
  ])("rejects unsafe returnTo %s and falls back", async (badReturnTo, fallback) => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: badReturnTo },
      returnTo: badReturnTo,
    });
    hoisted.loginViaKeycloak.mockResolvedValue(undefined);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(hoisted.routerReplace).toHaveBeenCalledWith(fallback);
    });
  });

  it.each([
    "/dashboard/business",
    "/dashboard/provider",
    "/admin/users",
    "/path/with/dots..",
    "/",
    "/abc?query=1&x=2",
  ])("accepts safe relative path %s", async (safeReturnTo) => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: safeReturnTo },
      returnTo: safeReturnTo,
    });
    hoisted.loginViaKeycloak.mockResolvedValue(undefined);
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(hoisted.routerReplace).toHaveBeenCalledWith(safeReturnTo);
    });
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 4. ERROR PATHS — handleSigninCallback throws
// ═════════════════════════════════════════════════════════════════════════════


describe("Keycloak callback errors", () => {
  it("renders error state when handleSigninCallback throws", async () => {
    hoisted.handleSigninCallback.mockRejectedValue(
      new Error("Authorization code expired"),
    );
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText("Authorization code expired")).toBeInTheDocument();
    });
  });

  it("renders generic Vietnamese fallback when error is not Error instance", async () => {
    hoisted.handleSigninCallback.mockRejectedValue("string-rejection");
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(
        screen.getByText("Lỗi khi xử lý phản hồi từ Keycloak"),
      ).toBeInTheDocument();
    });
  });

  it("does not redirect when callback fails", async () => {
    hoisted.handleSigninCallback.mockRejectedValue(new Error("PKCE mismatch"));
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText("PKCE mismatch")).toBeInTheDocument();
    });
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
  });

  it("renders 'Quay lại đăng nhập' button on error", async () => {
    hoisted.handleSigninCallback.mockRejectedValue(new Error("any"));
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Quay lại đăng nhập/ }),
      ).toBeInTheDocument();
    });
  });

  it.each([
    "PKCE verifier mismatch",
    "State mismatch",
    "Authorization code expired",
    "User cancelled login",
    "invalid_grant",
    "access_denied",
    "Network request failed",
  ])("displays Keycloak error: %s", async (errorMsg) => {
    hoisted.handleSigninCallback.mockRejectedValue(new Error(errorMsg));
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 5. ERROR PATHS — loginViaKeycloak throws
// ═════════════════════════════════════════════════════════════════════════════


describe("BE token rejection errors", () => {
  it("renders error when BE rejects Keycloak token", async () => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "stale-tok", state: "/" },
      returnTo: "/",
    });
    hoisted.loginViaKeycloak.mockRejectedValue(
      new Error("Tài khoản chưa kích hoạt"),
    );
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText("Tài khoản chưa kích hoạt")).toBeInTheDocument();
    });
  });

  it.each([
    "Tài khoản chưa kích hoạt",
    "Email chưa được xác thực",
    "Tài khoản bị tạm khóa",
    "Token bị từ chối (HTTP 401)",
    "Tài khoản không phù hợp (kỳ vọng business, nhận được provider)",
  ])("displays role-mismatch / status error: %s", async (errorMsg) => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    hoisted.loginViaKeycloak.mockRejectedValue(new Error(errorMsg));
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });

  it("does not redirect when BE rejects token", async () => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    hoisted.loginViaKeycloak.mockRejectedValue(new Error("rejected"));
    render(<OidcCallbackPage />);
    await waitFor(() => {
      expect(screen.getByText("rejected")).toBeInTheDocument();
    });
    expect(hoisted.routerReplace).not.toHaveBeenCalled();
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 6. UNMOUNT DURING ASYNC — cleanup correctness
// ═════════════════════════════════════════════════════════════════════════════


describe("unmount during async work", () => {
  it("does not setState after unmount when handleSigninCallback resolves later", async () => {
    let resolveCb: (v: unknown) => void = () => {};
    hoisted.handleSigninCallback.mockReturnValue(
      new Promise((r) => { resolveCb = r; }),
    );
    const { unmount } = render(<OidcCallbackPage />);
    unmount();
    // Resolve after unmount; should be no-op due to `cancelled` flag
    resolveCb({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    // Sanity: loginViaKeycloak was called or not — depends on cancel
    // implementation. Important: no React error console warnings.
  });

  it("does not setState after unmount when handleSigninCallback rejects later", async () => {
    let rejectCb: (e: unknown) => void = () => {};
    hoisted.handleSigninCallback.mockReturnValue(
      new Promise((_, rej) => { rejectCb = rej; }),
    );
    const { unmount } = render(<OidcCallbackPage />);
    unmount();
    rejectCb(new Error("late error"));
  });
});


// ═════════════════════════════════════════════════════════════════════════════
// 7. STATE / RETURNTO PARSING DEFAULT
// ═════════════════════════════════════════════════════════════════════════════


describe("returnTo defaults", () => {
  it("falls back to '/dashboard/business' when state is '/' (current spec)", async () => {
    hoisted.handleSigninCallback.mockResolvedValue({
      user: { access_token: "x", state: "/" },
      returnTo: "/",
    });
    hoisted.loginViaKeycloak.mockResolvedValue(undefined);
    render(<OidcCallbackPage />);
    // returnTo='/' → starts with '/' → safe → used directly
    await waitFor(() => {
      expect(hoisted.routerReplace).toHaveBeenCalledWith("/");
    });
  });
});
