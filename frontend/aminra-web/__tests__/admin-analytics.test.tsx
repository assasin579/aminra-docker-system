import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import AdminAnalyticsPage from "@/app/admin/analytics/page";

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

const mockData = {
  cert_buckets: {
    healthy: 12,
    expiring_90d: 4,
    expiring_60d: 3,
    expiring_30d: 2,
    expired: 1,
    suspended: 0,
    revoked: 2,
    total: 24,
  },
  funnel: {
    pending: 0,
    assigned: 1,
    reviewing: 4,
    returned: 0,
    approved: 10,
    rejected: 2,
  },
  monthly_trend: [
    { month: "2026-03", issued: 3 },
    { month: "2026-04", issued: 5 },
  ],
  top_actions: [
    { action: "login.success", count: 42 },
    { action: "submission.submit", count: 12 },
  ],
  heatmap: [{ dow: 1, hour: 9, count: 15 }],
  generated_at: "2026-04-25T08:00:00Z",
};

describe("AdminAnalyticsPage", () => {
  test("shows login prompt when no token", async () => {
    render(<AdminAnalyticsPage />);
    expect(await screen.findByText(/Cần đăng nhập bằng tài khoản Admin/i)).toBeInTheDocument();
  });

  test("renders all sections from API response", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, mockData),
    );

    render(<AdminAnalyticsPage />);

    expect(await screen.findByText(/Tình trạng chứng chỉ/i)).toBeInTheDocument();
    expect(screen.getByText("Hồ sơ theo trạng thái")).toBeInTheDocument();
    expect(screen.getByText(/Hành động phổ biến/)).toBeInTheDocument();
    expect(screen.getByText(/Chứng chỉ được cấp theo tháng/)).toBeInTheDocument();
    expect(screen.getByText(/Nhịp hoạt động hệ thống/)).toBeInTheDocument();
  });

  test("displays cert bucket labels", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, mockData),
    );

    render(<AdminAnalyticsPage />);

    await screen.findByText(/Tình trạng chứng chỉ/i);
    expect(screen.getByText("Chứng chỉ được cấp theo tháng")).toBeInTheDocument();
    expect(screen.getByText("Hồ sơ theo trạng thái")).toBeInTheDocument();
    const certificateLegend = screen.getByRole("list", { name: "Tình trạng chứng chỉ legend" });
    expect(within(certificateLegend).getByText("Khỏe mạnh · ≥90 ngày")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Đã hết hạn")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Còn 0–30 ngày")).toBeInTheDocument();
  });

  test("top actions section lists action codes + counts", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, mockData),
    );

    render(<AdminAnalyticsPage />);
    const actionLegend = await screen.findByRole("list", { name: "Hành động phổ biến trong 7 ngày legend" });
    expect(within(actionLegend).getByText("Đăng nhập thành công")).toBeInTheDocument();
    expect(within(actionLegend).getByText("42")).toBeInTheDocument();
    expect(within(actionLegend).getByText("Gửi hồ sơ")).toBeInTheDocument();
  });

  test("shows backend error", async () => {
    localStorage.setItem("aminra_user_token", "jwt");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(403, { detail: "Admin access required" }),
    );

    render(<AdminAnalyticsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Admin access required",
    );
  });

  test("calls /api/auth/admin/analytics with bearer token", async () => {
    localStorage.setItem("aminra_user_token", "token-123");
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, mockData),
    );

    render(<AdminAnalyticsPage />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/admin/analytics",
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer token-123",
          }),
        }),
      );
    });
  });
});
