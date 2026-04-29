import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const mockFetch = (ok: boolean) => {
  (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
    new Response(JSON.stringify({ message: "ok" }), { status: ok ? 200 : 500 }),
  );
};

describe("ForgotPasswordPage", () => {
  test("renders email input + disabled submit button initially", () => {
    render(<ForgotPasswordPage />);
    expect(screen.getByPlaceholderText(/cong-ty/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Gửi hướng dẫn/i }),
    ).toBeDisabled();
  });

  test("submitting valid email POSTs to /api/auth/request-password-reset and shows confirmation", async () => {
    const user = userEvent.setup();
    mockFetch(true);

    render(<ForgotPasswordPage />);
    await user.type(screen.getByPlaceholderText(/cong-ty/i), "biz@example.vn");
    await user.click(screen.getByRole("button", { name: /Gửi hướng dẫn/i }));

    expect(fetch).toHaveBeenCalledWith(
      "/api/auth/request-password-reset",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "biz@example.vn", lang: "vi" }),
      }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "biz@example.vn",
    );
    expect(screen.getByText(/60 phút/)).toBeInTheDocument();
  });

  test("email is normalized lowercase + trimmed before send", async () => {
    const user = userEvent.setup();
    mockFetch(true);

    render(<ForgotPasswordPage />);
    await user.type(
      screen.getByPlaceholderText(/cong-ty/i),
      "  Biz@EXAMPLE.vn  ",
    );
    await user.click(screen.getByRole("button", { name: /Gửi hướng dẫn/i }));

    const sentBody = JSON.parse(
      (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
    );
    expect(sentBody.email).toBe("biz@example.vn");
  });

  test("shows error message when request fails", async () => {
    const user = userEvent.setup();
    mockFetch(false);

    render(<ForgotPasswordPage />);
    await user.type(screen.getByPlaceholderText(/cong-ty/i), "biz@example.vn");
    await user.click(screen.getByRole("button", { name: /Gửi hướng dẫn/i }));

    expect(await screen.findByText(/Yêu cầu thất bại/i)).toBeInTheDocument();
  });
});
