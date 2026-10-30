import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import ProviderDashboard from "@/app/dashboard/provider/page";

const initialUser = { id: "owner-a", tenant_id: "cb-a", role: "provider", is_owner: true, status: "active", company_name: "Certifier", email: "qa@example.invalid" };
const authState = vi.hoisted(() => ({ user: { id: "owner-a", tenant_id: "cb-a", role: "provider", is_owner: true, status: "active", company_name: "Certifier", email: "qa@example.invalid" } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.PropsWithChildren<{ href: string }>) => <a href={href} {...props}>{children}</a> }));
vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({ user: authState.user, token: "test-token", isAuthenticated: true, loading: false, logout: vi.fn() }),
}));
vi.mock("@/components/CountUp", () => ({ default: ({ value, suffix = "" }: { value: number; suffix?: string }) => <>{value}{suffix}</> }));
vi.mock("@/components/SpotlightCard", () => ({ default: ({ children }: React.PropsWithChildren) => <div>{children}</div> }));

const cbStats = {
  portfolio_size: 0,
  certs: { total: 0, active: 0, expiring_soon: 0, inactive: 0 },
  audits: { total: 0, completed: 0, avg_compliance: null },
  submissions: { pending: 0, reviewing: 0, approved: 0, total: 0, avg_hours: null },
  auditor_workload: [],
  expiring_certs: [],
};
const queueStats = { pending: 0, reviewing: 0, approved: 0, returned: 0, total: 0, overdue: 0, avg_response_hours: null, recent: [] };
const performance = {
  window_days: 90,
  attribution: "report_accepted_at",
  total: { completed: { current_90d: 3, previous_90d: 2 }, cycle_time_hours: { current_median: 12.5, current_p90: 24, previous_median: 18, previous_p90: 36 }, scheduled_to_acceptance_days: { current_median: 2, current_p90: 4, previous_median: 3, previous_p90: 6 } },
  auditors: [{ auditor_id: "auditor-1", name: "Auditor A", completed: { current_90d: 3, previous_90d: 2 }, cycle_time_hours: { current_median: 12.5, current_p90: 24, previous_median: 18, previous_p90: 36 }, scheduled_to_acceptance_days: { current_median: 2, current_p90: 4, previous_median: 3, previous_p90: 6 } }],
  limitations: [],
};

function responseFor(url: string) {
  if (url.includes("cb-performance")) return new Response(JSON.stringify(performance), { status: 200 });
  if (url.includes("cb-stats")) return new Response(JSON.stringify(cbStats), { status: 200 });
  return new Response(JSON.stringify(queueStats), { status: 200 });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function performanceFor(name: string) {
  return {
    ...performance,
    auditors: performance.auditors.map((auditor) => ({ ...auditor, name })),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  authState.user = { ...initialUser };
});

describe("CB owner 90-day auditor performance dashboard", () => {
  it("fetches and renders accepted-report metrics only for the CB owner", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve(responseFor(String(input))));
    vi.stubGlobal("fetch", fetchMock);

    render(<ProviderDashboard />);

    expect(await screen.findByText("Hiệu suất kiểm định viên — 90 ngày")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /Hiệu suất kiểm định viên/i })).toHaveTextContent("Auditor A");
    expect(screen.getByRole("table", { name: /Hiệu suất kiểm định viên/i })).toHaveTextContent("3");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("cb-performance"))).toBe(true);
  });

  it("does not request or render team performance for a non-owner auditor", async () => {
    authState.user.is_owner = false;
    const fetchMock = vi.fn((input: RequestInfo | URL) => Promise.resolve(responseFor(String(input))));
    vi.stubGlobal("fetch", fetchMock);

    render(<ProviderDashboard />);

    await screen.findByText("Hàng đợi được giao");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("cb-performance"))).toBe(false);
    expect(screen.queryByText("Hiệu suất kiểm định viên — 90 ngày")).not.toBeInTheDocument();
  });

  it("does not render or commit owner A's response after context changes to owner B", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const pending = [first, second];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("cb-performance")) return pending.shift()!.promise;
      return Promise.resolve(responseFor(url));
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<ProviderDashboard />);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("cb-performance"))).toHaveLength(1));

    authState.user = { ...initialUser, id: "owner-b", tenant_id: "cb-b", company_name: "Other CB" };
    view.rerender(<ProviderDashboard />);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("cb-performance"))).toHaveLength(2));

    expect(screen.queryByText("Auditor A")).not.toBeInTheDocument();
    second.resolve(new Response(JSON.stringify(performanceFor("Auditor B")), { status: 200 }));
    expect(await screen.findByText("Auditor B")).toBeInTheDocument();
    first.resolve(new Response(JSON.stringify(performanceFor("Stale Auditor A")), { status: 200 }));
    await waitFor(() => expect(screen.queryByText("Stale Auditor A")).not.toBeInTheDocument());
    expect(screen.getByText("Auditor B")).toBeInTheDocument();
  });

  it("does not resurrect owner A data when owner B fails and A succeeds late", async () => {
    const first = deferred<Response>();
    const second = deferred<Response>();
    const pending = [first, second];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("cb-performance")) return pending.shift()!.promise;
      return Promise.resolve(responseFor(url));
    });
    vi.stubGlobal("fetch", fetchMock);

    const view = render(<ProviderDashboard />);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("cb-performance"))).toHaveLength(1));
    authState.user = { ...initialUser, id: "owner-b", tenant_id: "cb-b", company_name: "Other CB" };
    view.rerender(<ProviderDashboard />);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("cb-performance"))).toHaveLength(2));

    second.resolve(new Response("{}", { status: 403 }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/403/));
    first.resolve(new Response(JSON.stringify(performanceFor("Stale Auditor A")), { status: 200 }));
    await waitFor(() => expect(screen.queryByText("Stale Auditor A")).not.toBeInTheDocument());
    expect(screen.queryByRole("table", { name: /Hiệu suất kiểm định viên/i })).not.toBeInTheDocument();
  });
});
