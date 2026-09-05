import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";

const oidcMock = vi.hoisted(() => ({
  signinRedirect: vi.fn(),
}));

vi.mock("@/lib/auth-oidc", () => ({
  signinRedirect: oidcMock.signinRedirect,
}));

beforeEach(() => {
  oidcMock.signinRedirect.mockReset();
});

describe("ForgotPasswordPage", () => {
  test("shows Keycloak-owned password recovery handoff copy", () => {
    render(<ForgotPasswordPage />);

    expect(
      screen.getByText(/Đang chuyển đến trang khôi phục mật khẩu/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Quên mật khẩu/i)).toBeInTheDocument();
  });

  test("redirects to Keycloak login so user can use forgot-password link", async () => {
    render(<ForgotPasswordPage />);

    await waitFor(() => {
      expect(oidcMock.signinRedirect).toHaveBeenCalledWith("/");
    });
  });
});
