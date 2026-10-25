import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import BusinessDashboard from "@/app/dashboard/business/page";
import ProviderDashboard from "@/app/dashboard/provider/page";
import AdminAnalyticsPage from "@/app/admin/analytics/page";
import { AccessibleBarChart, completeMonthlySeries } from "@/components/dashboard/DashboardCharts";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.PropsWithChildren<{ href: string }>) => <a href={href} {...props}>{children}</a> }));
vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({ user: { role: "provider", is_owner: true, status: "active", company_name: "Certifier", email: "qa@example.invalid", member_count: 1 }, token: "test-token", isAuthenticated: true, loading: false, logout: vi.fn() }),
}));
vi.mock("@/lib/adminAuth", () => ({ readAdminToken: () => "admin-test-token" }));
vi.mock("@/components/CountUp", () => ({ default: ({ value, suffix = "" }: { value: number; suffix?: string }) => <>{value}{suffix}</> }));
vi.mock("@/components/SpotlightCard", () => ({ default: ({ children }: React.PropsWithChildren) => <div>{children}</div> }));

const analyticsFixture = {
  cert_buckets: { healthy: 12, expiring_90d: 4, expiring_60d: 3, expiring_30d: 2, expired: 1, suspended: 0, revoked: 2, total: 24 },
  funnel: { pending: 0, assigned: 1, reviewing: 4, returned: 0, approved: 10, rejected: 2 },
  monthly_trend: [{ month: "2026-03", issued: 3 }, { month: "2026-05", issued: 5 }],
  top_actions: [{ action: "login.success", count: 42 }], heatmap: [], generated_at: "2026-05-25T08:00:00Z",
};

describe("dashboard data visual contracts", () => {
  it("uses a real accessible graphic and text alternative for bar data", () => {
    render(<AccessibleBarChart title="Workload" data={[{ label: "Auditor A", value: 3 }]} />);
    expect(screen.getByRole("img", { name: "Workload" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("Auditor A");
    expect(screen.getByRole("table")).toHaveTextContent("3");
  });

  it("completes sparse monthly observations with explicit zero-valued months", () => {
    const result = completeMonthlySeries(analyticsFixture.monthly_trend, new Date("2026-06-15T12:00:00Z"), 4);
    expect(result).toEqual([
      { month: "2026-03", issued: 3 }, { month: "2026-04", issued: 0 },
      { month: "2026-05", issued: 5 }, { month: "2026-06", issued: 0 },
    ]);
  });

  it("renders admin status distribution as status, not a conversion funnel", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(analyticsFixture), { status: 200 })));
    render(<AdminAnalyticsPage />);
    expect(await screen.findByText("Phân bố trạng thái hồ sơ")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Phân bố trạng thái hồ sơ/ })).toBeInTheDocument();
    expect(screen.queryByText("Funnel hồ sơ")).not.toBeInTheDocument();
    expect(screen.getByText("Còn 30–60 ngày")).toBeInTheDocument();
    expect(screen.getByText("Còn 0–30 ngày")).toBeInTheDocument();
    expect(screen.getByText("Còn 60–90 ngày")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /12 tháng gần nhất/i })).toHaveTextContent("2026-04");
  });

  it("exposes business and provider-specific chart panels without pretending missing data is zero", async () => {
    const response = vi.fn().mockImplementation((url: string) => {
      if (url.includes("dashboard/stats")) return Promise.resolve(new Response(JSON.stringify({ readiness: 40, compliant_count: 2, total_types: 5, submitted_count: 3, total_documents: 3, avg_score: null, member_count: 1, doc_type_progress: [{ doc_type: "policy", label: "Policy", score: 80, status: "compliant", filename: "policy.pdf", uploaded_at: null }, { doc_type: "training", label: "Training", score: null, status: null, filename: null, uploaded_at: null }], recent_activity: [] }), { status: 200 }));
      if (url.includes("cb-stats")) return Promise.resolve(new Response(JSON.stringify({ portfolio_size: 2, certs: { total: 2, active: 1, expiring_soon: 1, inactive: 0 }, audits: { total: 1, completed: 1, avg_compliance: 75 }, submissions: { pending: 1, reviewing: 0, approved: 1, total: 2, avg_hours: null }, auditor_workload: [{ id: "a1", name: "Auditor A", active_visits: 2, active_submissions: 1 }], expiring_certs: [] }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ pending: 1, reviewing: 0, approved: 1, returned: 0, total: 2, overdue: 0, avg_response_hours: null, recent: [] }), { status: 200 }));
    });
    vi.stubGlobal("fetch", response);
    render(<BusinessDashboard />);
    expect(await screen.findByText("Trạng thái tài liệu")).toBeInTheDocument();
    expect(screen.getByText(/Điểm trung bình trên tài liệu đã chấm/)).toBeInTheDocument();
    render(<ProviderDashboard />);
    expect(await screen.findByText("Tải công việc Auditor")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tải công việc auditor/i })).toBeInTheDocument();
  });

  it("shows and retries API failure states instead of presenting silent empty dashboards", async () => {
    const failedFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Service unavailable" }), { status: 503 }));
    vi.stubGlobal("fetch", failedFetch);
    const business = render(<BusinessDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được số liệu hồ sơ (503)");
    fireEvent.click(screen.getByRole("button", { name: "Thử tải lại" }));
    await waitFor(() => expect(failedFetch).toHaveBeenCalledTimes(4));
    business.unmount();

    failedFetch.mockClear();
    render(<ProviderDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được số liệu CB (503)");
    fireEvent.click(screen.getByRole("button", { name: "Thử tải lại" }));
    await waitFor(() => expect(failedFetch.mock.calls.length).toBeGreaterThanOrEqual(4));
  });

  it("does not hide a failed certificate timeline behind successful business stats", async () => {
    const partialFetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("dashboard/stats")) return Promise.resolve(new Response(JSON.stringify({ readiness: 40, compliant_count: 2, total_types: 5, submitted_count: 3, total_documents: 3, avg_score: null, member_count: 1, doc_type_progress: [], recent_activity: [] }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({ detail: "Service unavailable" }), { status: 503 }));
    });
    vi.stubGlobal("fetch", partialFetch);
    render(<BusinessDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được dòng thời gian chứng chỉ (503)");
  });
});
