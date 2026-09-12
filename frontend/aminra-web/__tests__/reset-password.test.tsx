import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  test("keeps reset handoff inside AMINRA UI", () => {
    render(<ResetPasswordPage />);

    expect(screen.getByText(/Đặt lại mật khẩu/i)).toBeInTheDocument();
    expect(screen.getByText(/không bị chuyển/i)).toBeInTheDocument();
    expect(screen.getByText(/Về trang đăng nhập/i)).toHaveAttribute(
      "href",
      "/business/login",
    );
  });

  test("does not redirect to the identity provider", () => {
    render(<ResetPasswordPage />);

    expect(oidcMock.signinRedirect).not.toHaveBeenCalled();
  });
});
