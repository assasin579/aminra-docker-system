import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { AdminAuthProvider, useAdminAuth } from "@/components/AdminAuthContext";

vi.mock("@/lib/auth-oidc", () => ({
  signinRedirect: vi.fn(),
  signoutRedirect: vi.fn(),
}));

function jwtWithRoles(roles: string[]): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ realm_access: { roles } }));
  return `${header}.${payload}.signature`;
}

function Probe() {
  const { isAdmin } = useAdminAuth();
  return <div data-testid="admin-state">{isAdmin ? "admin" : "not-admin"}</div>;
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

  it("removes admin access in the same tab after logout clears the token", async () => {
    localStorage.setItem(
      "aminra_user_token",
      jwtWithRoles(["platform_admin"]),
    );
    renderProbe();
    await waitFor(() => {
      expect(screen.getByTestId("admin-state")).toHaveTextContent("admin");
    });

    localStorage.removeItem("aminra_user_token");
    act(() => {
      window.dispatchEvent(new Event("aminra:auth-session-changed"));
    });

    await waitFor(() => {
      expect(screen.getByTestId("admin-state")).toHaveTextContent("not-admin");
    });
  });
});
