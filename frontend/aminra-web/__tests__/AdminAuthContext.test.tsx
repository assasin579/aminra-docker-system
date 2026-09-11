import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { getOidcUser, signoutRedirect } from "@/lib/auth-oidc";
import { AdminAuthProvider, useAdminAuth } from "@/components/AdminAuthContext";

vi.mock("@/lib/auth-oidc", () => ({
  getOidcUser: vi.fn(),
  signinRedirect: vi.fn(),
  signoutRedirect: vi.fn(),
}));

function jwtWithRoles(roles: string[]): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ realm_access: { roles } }));
  return `${header}.${payload}.signature`;
}

function Probe() {
  const { isAdmin, logout } = useAdminAuth();
  return (
    <div>
      <div data-testid="admin-state">{isAdmin ? "admin" : "not-admin"}</div>
      <button type="button" onClick={logout}>logout</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <AdminAuthProvider>
      <Probe />
    </AdminAuthProvider>,
  );
}

describe("AdminAuthProvider token synchronization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("loads an existing platform_admin user token on mount", async () => {
    localStorage.setItem(
      "aminra_user_token",
      jwtWithRoles(["business", "platform_admin"]),
    );
    renderProbe();
    await expect(screen.findByTestId("admin-state")).resolves.toHaveTextContent(
      "admin",
    );
  });

  it("refreshes in the same tab after UserAuthContext saves a Keycloak token", async () => {
    renderProbe();
    expect(screen.getByTestId("admin-state")).toHaveTextContent("not-admin");

    localStorage.setItem(
      "aminra_user_token",
      jwtWithRoles(["platform_admin"]),
    );
    act(() => {
      window.dispatchEvent(new Event("aminra:auth-session-changed"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("admin-state")).toHaveTextContent("admin");
    });
  });

  it("preserves the OIDC id token through local purge so Keycloak admin session is ended", async () => {
    const oidcUser = { id_token: "admin-id-token" };
    vi.mocked(getOidcUser).mockResolvedValue(oidcUser as never);
    localStorage.setItem(
      "aminra_user_token",
      jwtWithRoles(["platform_admin"]),
    );
    renderProbe();

    screen.getByRole("button", { name: "logout" }).click();

    await waitFor(() => {
      expect(signoutRedirect).toHaveBeenCalledWith(oidcUser);
    });
    expect(localStorage.getItem("aminra_user_token")).toBeNull();
  });
});
