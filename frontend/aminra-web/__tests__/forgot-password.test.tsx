import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  test("keeps password recovery handoff inside AMINRA UI", () => {
    render(<ForgotPasswordPage />);

    expect(screen.getByText(/Khôi phục mật khẩu/i)).toBeInTheDocument();
    expect(screen.getByText(/không chuyển người dùng/i)).toBeInTheDocument();
    expect(screen.getByText(/Quay lại đăng nhập doanh nghiệp/i)).toHaveAttribute(
      "href",
      "/business/login",
    );
  });

  test("does not redirect to the identity provider", () => {
    render(<ForgotPasswordPage />);

    expect(oidcMock.signinRedirect).not.toHaveBeenCalled();
  });
});
