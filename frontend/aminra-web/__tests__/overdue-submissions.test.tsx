import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import OverdueSubmissionsPage from "@/app/admin/overdue-submissions/page";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

describe("OverdueSubmissionsPage", () => {
  test("shows login prompt when no token", async () => {
    render(<OverdueSubmissionsPage />);
    expect(await screen.findByText(/Cần đăng nhập admin/i)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  test("shows empty state when no items", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { items: [], count: 0 }),
    );

    render(<OverdueSubmissionsPage />);
    // Empty-state confirmation text (separate from header subtitle)
    expect(await screen.findByText(/Tất cả tổ chức cấp/i)).toBeInTheDocument();
  });

  test("renders overdue items in table with provider info + days overdue", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        items: [
          {
            submission_id: "11111111-1111-1111-1111-111111111111",
            company_name: "Halal Foods Co",
            status: "reviewing",
            submitted_at: "2026-03-25T10:00:00Z",
            deadline: "2026-04-20T10:00:00Z",
            provider_email: "cb@halal.vn",
            provider_name: "Halal CB Vietnam",
            days_overdue: 5.3,
          },
          {
            submission_id: "22222222-2222-2222-2222-222222222222",
            company_name: "Other Co",
            status: "revision_required",
            submitted_at: "2026-03-01T00:00:00Z",
            deadline: "2026-03-15T00:00:00Z",
            provider_email: null,
            provider_name: null,
            days_overdue: 41.5,
          },
        ],
        count: 2,
      }),
    );

    render(<OverdueSubmissionsPage />);

    expect(await screen.findByText("Halal Foods Co")).toBeInTheDocument();
    expect(screen.getByText("Halal CB Vietnam")).toBeInTheDocument();
    expect(screen.getByText(/5\.3 ngày/)).toBeInTheDocument();
    expect(screen.getByText(/41\.5 ngày/)).toBeInTheDocument();
    // Provider email link
    expect(screen.getByRole("link", { name: "cb@halal.vn" })).toHaveAttribute(
      "href",
      "mailto:cb@halal.vn",
    );
    // Status label
    expect(screen.getByText("Đang đánh giá")).toBeInTheDocument();
    expect(screen.getByText("Cần sửa")).toBeInTheDocument();
  });

  test("shows backend error", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(403, { detail: "Admin access required" }),
    );

    render(<OverdueSubmissionsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Admin access required",
    );
  });

  test("calls correct admin endpoint with bearer token", async () => {
    localStorage.setItem("aminra_user_token", "token-456");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { items: [], count: 0 }),
    );

    render(<OverdueSubmissionsPage />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/admin/overdue-submissions",
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer token-456",
          }),
        }),
      );
    });
  });

  test("count summary text uses item count", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        items: [
          {
            submission_id: "x",
            company_name: "A",
            status: "reviewing",
            submitted_at: null,
            deadline: "2026-01-01T00:00:00Z",
            provider_email: null,
            provider_name: null,
            days_overdue: 1.0,
          },
        ],
        count: 1,
      }),
    );

    render(<OverdueSubmissionsPage />);
    expect(
      await screen.findByText(/1 hồ sơ đã quá deadline/i),
    ).toBeInTheDocument();
  });
});
