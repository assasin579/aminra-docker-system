import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResetPasswordPage from "@/app/(auth)/reset-password/page";

const pushMock = vi.fn();
const searchParamsMock = { get: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  useSearchParams: () => searchParamsMock,
}));

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  pushMock.mockReset();
  searchParamsMock.get.mockReset();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("ResetPasswordPage", () => {
  test("shows invalid state when no token in URL", async () => {
    searchParamsMock.get.mockReturnValue(null);
    render(<ResetPasswordPage />);
    expect(
      await screen.findByText(/không hợp lệ hoặc đã hết hạn/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Yêu cầu liên kết mới/i }),
    ).toBeInTheDocument();
  });

  test("shows invalid when verify-reset-token returns 400", async () => {
    searchParamsMock.get.mockReturnValue("bad-token");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(400, { detail: "Token không hợp lệ" }),
    );

    render(<ResetPasswordPage />);
    expect(
      await screen.findByText(/không hợp lệ hoặc đã hết hạn/i),
    ).toBeInTheDocument();
  });

  test("shows password form + email when token is valid", async () => {
    searchParamsMock.get.mockReturnValue("good-token");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { valid: true, email: "biz@example.vn" }),
    );

    render(<ResetPasswordPage />);
    expect(await screen.findByText("biz@example.vn")).toBeInTheDocument();
    // Two password inputs (new + confirm)
    expect(screen.getAllByPlaceholderText(/^•/)).toHaveLength(2);
  });

  test("rejects mismatched passwords client-side without calling reset API", async () => {
    searchParamsMock.get.mockReturnValue("good-token");
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      respond(200, { valid: true, email: "x@y.z" }),
    );

    render(<ResetPasswordPage />);
    await screen.findByText("x@y.z");

    const inputs = screen.getAllByPlaceholderText(/^•/);
    fireEvent.change(inputs[0], { target: { value: "Strong1Password" } });
    fireEvent.change(inputs[1], { target: { value: "DifferentPass1" } });

    const form = inputs[0].closest("form")!;
    fireEvent.submit(form);

    expect(
      await screen.findByText("Hai mật khẩu không khớp"),
    ).toBeInTheDocument();
    // Only the initial verify-token call happened
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("successful reset shows confirmation + calls reset endpoint", async () => {
    searchParamsMock.get.mockReturnValue("good-token");
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { valid: true, email: "x@y.z" }))
      .mockResolvedValueOnce(respond(200, { message: "OK" }));

    render(<ResetPasswordPage />);
    await screen.findByText("x@y.z");

    const inputs = screen.getAllByPlaceholderText(/^•/);
    fireEvent.change(inputs[0], { target: { value: "Strong1Password" } });
    fireEvent.change(inputs[1], { target: { value: "Strong1Password" } });
    fireEvent.submit(inputs[0].closest("form")!);

    expect(await screen.findByRole("status")).toHaveTextContent(/thành công/);

    const lastCall = fetchMock.mock.calls.at(-1)!;
    expect(lastCall[0]).toBe("/api/auth/reset-password");
    expect(JSON.parse(lastCall[1].body)).toEqual({
      token: "good-token",
      new_password: "Strong1Password",
    });
  });

  test("shows backend error message when reset returns 400", async () => {
    searchParamsMock.get.mockReturnValue("good-token");
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { valid: true, email: "x@y.z" }))
      .mockResolvedValueOnce(respond(400, { detail: "Token đã được sử dụng" }));

    render(<ResetPasswordPage />);
    await screen.findByText("x@y.z");

    const inputs = screen.getAllByPlaceholderText(/^•/);
    fireEvent.change(inputs[0], { target: { value: "Strong1Password" } });
    fireEvent.change(inputs[1], { target: { value: "Strong1Password" } });
    fireEvent.submit(inputs[0].closest("form")!);

    expect(
      await screen.findByText("Token đã được sử dụng"),
    ).toBeInTheDocument();
  });
});
