import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ResetPasswordPage from "@/app/(auth)/reset-password/page";

const oidcMock = vi.hoisted(() => ({
  signinRedirect: vi.fn(),
}));

vi.mock("@/lib/auth-oidc", () => ({
  signinRedirect: oidcMock.signinRedirect,
}));

beforeEach(() => {
  oidcMock.signinRedirect.mockReset();
});

describe("ResetPasswordPage", () => {
  test("shows Keycloak-owned reset handoff copy", () => {
    render(<ResetPasswordPage />);

    expect(screen.getByText(/Đang chuyển hướng/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Khôi phục mật khẩu được xử lý bởi Keycloak/i),
    ).toBeInTheDocument();
  });

  test("redirects to Keycloak login/reset flow", async () => {
    render(<ResetPasswordPage />);

    await waitFor(() => {
      expect(oidcMock.signinRedirect).toHaveBeenCalledWith("/");
    });
  });
});
