import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import BusinessDashboard from "@/app/dashboard/business/page";
import ProviderDashboard from "@/app/dashboard/provider/page";
import AdminAnalyticsPage from "@/app/admin/analytics/page";
import { AccessibleBarChart, DonutChart, DashboardCard, MonthlyBarChart, completeMonthlySeries } from "@/components/dashboard/DashboardCharts";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.PropsWithChildren<{ href: string }>) => <a href={href} {...props}>{children}</a> }));
const providerAuthState = vi.hoisted(() => ({ user: { role: "provider", is_owner: true, status: "active", company_name: "Certifier", email: "qa@example.invalid", member_count: 1 } }));
vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({ user: providerAuthState.user, token: "test-token", isAuthenticated: true, loading: false, logout: vi.fn() }),
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
  it("uses motion hooks for every shared dashboard visual primitive", () => {
    const { container } = render(
      <main data-dashboard-motion-root="true">
        <DashboardCard title="Motion inventory">
          <DonutChart title="Status" data={[{ label: "Open", value: 3 }, { label: "Closed", value: 2 }]} />
          <AccessibleBarChart title="Workload" data={[{ label: "Auditor A", value: 3 }]} />
          <MonthlyBarChart title="Monthly trend" data={[{ month: "2026-04", issued: 0 }, { month: "2026-05", issued: 4 }]} />
        </DashboardCard>
      </main>,
    );
    for (const kind of ["card", "donut", "donut-segment", "legend-item", "bar-chart", "bar-fill", "monthly-chart", "monthly-bar"]) {
      expect(container.querySelector(`[data-dashboard-motion="${kind}"]`), `missing motion contract: ${kind}`).toBeInTheDocument();
    }
  });

  it("defines reduced-motion overrides and motion affordances for dashboard entry, cards, charts, and controls", () => {
    const motionCss = readFileSync(resolve(process.cwd(), "components/dashboard/DashboardMotion.module.css"), "utf8");
    expect(motionCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(motionCss).toContain("animation: none !important");
    expect(motionCss).toContain(":hover");
    expect(motionCss).toContain(":focus-visible");
    expect(motionCss).toContain("dashboardCard");
    expect(motionCss).toContain("donutSegment");
    expect(motionCss).toContain("monthlyBar");
    expect(motionCss).toContain("from { stroke-dasharray: 0 var(--circumference);");
    expect(motionCss).toContain(".row:hover");
  });

  it("wires the overdue queue to page, empty/error, card, and staggered-row motion", () => {
    const overdueSource = readFileSync(resolve(process.cwd(), "app/dashboard/provider/overdue/page.tsx"), "utf8");
    expect(overdueSource).toContain("${motion.page}");
    expect(overdueSource).toContain('data-dashboard-motion="alert"');
    expect(overdueSource).toContain('data-dashboard-motion="empty"');
    expect(overdueSource).toContain('data-dashboard-motion="card"');
    expect(overdueSource).toContain('data-dashboard-motion="row"');
    expect(overdueSource).toContain("Math.min(index, 12) * 35");
  });

  it("uses a real accessible graphic and text alternative for bar data", () => {
    render(<AccessibleBarChart title="Workload" data={[{ label: "Auditor A", value: 3 }]} />);
    expect(screen.getByRole("img", { name: "Workload" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("Auditor A");
    expect(screen.getByRole("table")).toHaveTextContent("3");
  });

  it("uses only the canonical AMINRA navy/gold/cream palette for dashboard surfaces and chart segments", () => {
    const { container } = render(<DashboardCard title="Brand palette"><DonutChart title="Brand mix" data={[{ label: "Primary", value: 6 }, { label: "Accent", value: 4 }]} /></DashboardCard>);
    const card = container.querySelector('[data-dashboard-card="true"]');
    expect(card?.className).toContain("from-cream-50");
    expect(card?.className).toContain("to-cream-100");
    expect(card?.className).toContain("border-cream-200");
    const segments = Array.from(container.querySelectorAll('[data-dashboard-color-segment="true"]'));
    expect(segments.map((segment) => segment.getAttribute("stroke"))).toEqual(["var(--navy-900)", "var(--navy-700)"]);
    expect(container.querySelector(".bg-gradient-to-b.from-gold-700")).toBeInTheDocument();
  });

  it("renders a visual donut card with an accessible total, legend, and table alternative", () => {
    const { container } = render(
      <DashboardCard title="Certificate status" description="Current distribution from API data.">
        <DonutChart title="Certificate status" data={[
          { label: "Valid", value: 5, color: "#1FA971" },
          { label: "Expiring", value: 3, color: "#E1AD32" },
          { label: "Expired", value: 2, color: "#CF5260" },
        ]} />
      </DashboardCard>,
    );

    expect(container.querySelector('[data-dashboard-card="true"]')).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Certificate status.*10/ })).toBeInTheDocument();
    expect(screen.getByTestId("donut-total")).toHaveTextContent("10");
    const legend = screen.getByRole("list", { name: "Certificate status legend" });
    expect(within(legend).getByText("Valid")).toBeInTheDocument();
    expect(within(legend).getByText("Expiring")).toBeInTheDocument();
    expect(within(legend).getByText("Expired")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /Certificate status.*table/i })).toHaveTextContent("10");
  });

  it("keeps empty and invalid donut values finite and explicit", () => {
    const { container } = render(
      <DonutChart title="Empty distribution" data={[
        { label: "Negative", value: -4 },
        { label: "Invalid", value: Number.NaN },
      ]} />,
    );

    expect(screen.getByTestId("donut-total")).toHaveTextContent("0");
    expect(screen.getByText("Chưa có dữ liệu để phân bố.")).toBeInTheDocument();
    expect(container.querySelector('[stroke-dasharray*="NaN"]')).not.toBeInTheDocument();
  });

  it("completes sparse monthly observations with explicit zero-valued months", () => {
    const result = completeMonthlySeries(analyticsFixture.monthly_trend, new Date("2026-06-15T12:00:00Z"), 4);
    expect(result).toEqual([
      { month: "2026-03", issued: 3 }, { month: "2026-04", issued: 0 },
      { month: "2026-05", issued: 5 }, { month: "2026-06", issued: 0 },
    ]);
  });

  it("uses only AMINRA navy/cream for activity heatmap intensity rather than unrelated teal", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ...analyticsFixture,
      heatmap: [{ dow: 1, hour: 9, count: 4 }],
    }), { status: 200 })));
    const { container } = render(<AdminAnalyticsPage />);
    const activeCell = await screen.findByLabelText("Thứ hai, 9:00 — 4 sự kiện");
    expect(activeCell).toHaveStyle({ backgroundColor: "color-mix(in srgb, var(--navy-700) 100%, var(--cream-50))" });
    expect(container.innerHTML).not.toContain("rgba(29,138,122");
  });

  it("renders admin status distribution as status, not a conversion funnel", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(analyticsFixture), { status: 200 })));
    render(<AdminAnalyticsPage />);
    expect(await screen.findByText("Hồ sơ theo trạng thái")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Hồ sơ theo trạng thái/ })).toBeInTheDocument();
    expect(screen.queryByText("Funnel hồ sơ")).not.toBeInTheDocument();
    const certificateLegend = screen.getByRole("list", { name: "Tình trạng chứng chỉ legend" });
    expect(within(certificateLegend).getByText("Còn 30–60 ngày")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Còn 0–30 ngày")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Còn 60–90 ngày")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /12 tháng gần nhất/i })).toHaveTextContent("2026-04");
  });

  it("exposes the business dashboard chart panels without fabricating missing data as zero", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("dashboard/stats")) return Promise.resolve(new Response(JSON.stringify({ total_documents: 3, avg_score: null, member_count: 1, doc_type_progress: [{ doc_type: "policy", label: "Policy", score: 80, status: "compliant", filename: "policy.pdf", uploaded_at: null }, { doc_type: "training", label: "Training", score: null, status: null, filename: null, uploaded_at: null }], recent_activity: [] }), { status: 200 }));
      if (url.includes("cert-timeline")) return Promise.resolve(new Response(JSON.stringify({ certificates: [] }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    }));
    const business = render(<BusinessDashboard />);
    expect(await screen.findByText("Trạng thái tài liệu")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Trạng thái tài liệu doanh nghiệp/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Phân bố điểm theo loại tài liệu/ })).toBeInTheDocument();
    expect(screen.getByText(/Điểm trung bình trên tài liệu đã chấm/)).toBeInTheDocument();
    business.unmount();
  });

  it("exposes provider-specific chart panels", async () => {
    providerAuthState.user.is_owner = true;
    try {
      vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
        const summary = {
          completed: { current_90d: 0, previous_90d: 0 },
          cycle_time_hours: { current_median: null, current_p90: null, previous_median: null, previous_p90: null },
          scheduled_to_acceptance_days: { current_median: null, current_p90: null, previous_median: null, previous_p90: null },
        };
        const data = url.includes("cb-performance")
          ? { window_days: 90, attribution: "report_accepted_at", total: summary, auditors: [], limitations: [] }
          : url.includes("cb-stats")
            ? { portfolio_size: 2, certs: { total: 2, active: 1, expiring_soon: 1, inactive: 0 }, audits: { total: 1, completed: 1, avg_compliance: 75 }, submissions: { pending: 1, reviewing: 0, approved: 1, total: 2, avg_hours: null }, auditor_workload: [{ id: "a1", name: "Auditor A", active_visits: 2, active_submissions: 1 }], expiring_certs: [] }
            : { pending: 1, reviewing: 0, approved: 1, returned: 0, total: 2, overdue: 0, avg_response_hours: null, recent: [] };
        return Promise.resolve(new Response(JSON.stringify(data), { status: 200 }));
      }));
      render(<ProviderDashboard />);
    expect(await screen.findByText("Tải công việc Auditor")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tải công việc auditor/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Chứng chỉ theo trạng thái/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Tiến độ kiểm định/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Hồ sơ Certification Body theo trạng thái/ })).toBeInTheDocument();
    } finally {
      providerAuthState.user.is_owner = true;
    }
  });

  it("shows the auditor queue as a visual donut and preserves unclassified counts", async () => {
    providerAuthState.user.is_owner = false;
    try {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
        pending: 2, reviewing: 1, approved: 3, returned: 1, total: 9,
        overdue: 1, avg_response_hours: 4.5, recent: [],
      }), { status: 200 })));
      render(<ProviderDashboard />);
      expect(await screen.findByRole("img", { name: /Hồ sơ auditor theo trạng thái.*9/ })).toBeInTheDocument();
      expect(screen.getByTestId("donut-total")).toHaveTextContent("9");
      expect(screen.getByRole("table", { name: /Hồ sơ auditor theo trạng thái.*table/i })).toHaveTextContent("Trạng thái khác");
      expect(screen.getByRole("table", { name: /Hồ sơ auditor theo trạng thái.*table/i })).toHaveTextContent("2");
    } finally {
      providerAuthState.user.is_owner = true;
    }
  });

  it("presents the business overview as a vibrant chart-first dashboard using real certificate data", async () => {
    const response = vi.fn().mockImplementation((url: string) => {
      if (url.includes("dashboard/stats")) return Promise.resolve(new Response(JSON.stringify({
        readiness: 40, compliant_count: 2, total_types: 5, submitted_count: 3,
        total_documents: 3, avg_score: 68, member_count: 4,
        doc_type_progress: [
          { doc_type: "policy", label: "Policy", score: 80, status: "compliant", filename: "policy.pdf", uploaded_at: null },
          { doc_type: "training", label: "Training", score: 56, status: "needs_review", filename: "training.pdf", uploaded_at: null },
          { doc_type: "trace", label: "Traceability", score: null, status: null, filename: "trace.pdf", uploaded_at: null },
          { doc_type: "supplier", label: "Supplier", score: null, status: null, filename: null, uploaded_at: null },
          { doc_type: "facility", label: "Facility", score: 68, status: "compliant", filename: "facility.pdf", uploaded_at: null },
        ], recent_activity: [],
      }), { status:  200 }));
      if (url.includes("cert-timeline")) return Promise.resolve(new Response(JSON.stringify({ certificates: [
        { cert_number: "CERT-001", provider_name: "CB One", status: "active", days_remaining: 120, expiry_date: "2027-01-01" },
        { cert_number: "CERT-002", provider_name: "CB Two", status: "active", days_remaining: 20, expiry_date: "2026-09-23" },
        { cert_number: "CERT-003", provider_name: "CB Three", status: "active", days_remaining: -2, expiry_date: "2026-07-02" },
        { cert_number: "CERT-004", provider_name: "CB Four", status: "suspended", days_remaining: 45, expiry_date: "2026-08-18" },
      ] }), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", response);
    const { container } = render(<BusinessDashboard />);
    expect(await screen.findByText("Phân bố chứng chỉ")).toBeInTheDocument();
    expect(container.querySelector('[data-dashboard-experience="business-v2"]')).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Profile readiness"]')).toBeInTheDocument();
    expect(container.querySelector('[data-dashboard-section="readiness-hero"]')).not.toBeInTheDocument();
    expect(container.querySelector('[data-dashboard-section="overview-charts"]')).toBeInTheDocument();
    const sectionOrder = Array.from(container.querySelectorAll("[data-dashboard-section]"), (section) => section.getAttribute("data-dashboard-section"));
    expect(sectionOrder.indexOf("overview-charts")).toBeLessThan(sectionOrder.indexOf("key-metrics"));
    expect(container.querySelectorAll('[data-dashboard-chart="donut"]')).toHaveLength(3);
    expect(screen.getByRole("img", { name: /Tình trạng chứng chỉ.*4/ })).toBeInTheDocument();
    const certificateLegend = screen.getByRole("list", { name: "Tình trạng chứng chỉ legend" });
    expect(within(certificateLegend).getByText("Còn hiệu lực · >60 ngày")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Sắp hết hạn · 0–60 ngày")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Quá ngày hết hạn")).toBeInTheDocument();
    expect(within(certificateLegend).getByText("Không hoạt động / khác")).toBeInTheDocument();
  });

  it("shows and retries API failure states instead of presenting silent empty dashboards", async () => {
    const failedFetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Service unavailable" }), { status: 503 }));
    vi.stubGlobal("fetch", failedFetch);
    const business = render(<BusinessDashboard />);
    expect(await screen.findByText("Không tải được số liệu hồ sơ (503).")).toBeInTheDocument();
    expect(screen.getByText("Could not load Profile readiness. Please try again.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thử tải lại" }));
    await waitFor(() => expect(failedFetch).toHaveBeenCalledTimes(5));
    business.unmount();

    failedFetch.mockClear();
    render(<ProviderDashboard />);
    expect(await screen.findByRole("alert")).toHaveTextContent("(503)");
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
    expect(await screen.findByText("Không tải được dòng thời gian chứng chỉ (503).")).toBeInTheDocument();
    expect(screen.getByText("Could not load Profile readiness. Please try again.")).toBeInTheDocument();
  });
});
