import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Sidebar from "@/components/Sidebar";

const routeState = vi.hoisted(() => ({ pathname: "/admin" }));
const adminState = vi.hoisted(() => ({ isAdmin: true }));
const userState = vi.hoisted(() => ({
  isAuthenticated: true,
  token: "user-token",
  user: {
    role: "provider",
    is_owner: true,
    company_name: "AMINRA Platform",
    email: "admin@aminra.com",
    tenant_id: "platform-tenant",
  },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => routeState.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => (key === "navbar.home" ? "Chat với Aminra" : key),
    i18n: { language: "vi" },
  }),
}));

vi.mock("@/components/AdminAuthContext", () => ({
  useAdminAuth: () => ({
    isAdmin: adminState.isAdmin,
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({
    user: userState.user,
    isAuthenticated: userState.isAuthenticated,
    token: userState.token,
    logout: vi.fn(),
  }),
}));

vi.mock("@/components/NotificationBell", () => ({
  default: () => <div data-testid="notification-bell">notification bell</div>,
}));

describe("admin sidebar navigation contract", () => {
  beforeEach(() => {
    routeState.pathname = "/admin";
    adminState.isAdmin = true;
    userState.isAuthenticated = true;
    userState.token = "user-token";
    userState.user = {
      role: "provider",
      is_owner: true,
      company_name: "AMINRA Platform",
      email: "admin@aminra.com",
      tenant_id: "platform-tenant",
    };
  });

  it("renders admin-only navigation on /admin even when /auth/me projects the platform admin as provider", () => {
    render(<Sidebar />);

    expect(screen.getByText("AMINRA Platform Admin")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Admin Panel/i })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("link", { name: /Analytics/i })).toHaveAttribute("href", "/admin/analytics");
    expect(screen.getByRole("link", { name: /Audit logs/i })).toHaveAttribute("href", "/admin/audit-logs");
    expect(screen.getByRole("link", { name: /Overdue queue/i })).toHaveAttribute("href", "/admin/overdue-submissions");
    expect(screen.getByRole("link", { name: /^Standards$/i })).toHaveAttribute("href", "/admin/standards");
    expect(screen.getByRole("link", { name: /Industries ↔ Standards/i })).toHaveAttribute("href", "/admin/industries");

    expect(screen.queryByText("admin@aminra.com")).not.toBeInTheDocument();
    expect(screen.queryByTestId("notification-bell")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Dashboard/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Chat với Aminra/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Doanh nghiệp/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Chứng nhận/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Quản lý Auditor/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Hồ sơ nhận/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Kiểm định/i })).not.toBeInTheDocument();
  });

  it("keeps provider portal navigation outside /admin, with an explicit Admin Panel escape hatch", () => {
    routeState.pathname = "/portfolio";

    render(<Sidebar />);

    expect(screen.getByText("admin@aminra.com")).toBeInTheDocument();
    expect(screen.getByTestId("notification-bell")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Dashboard/i })).toHaveAttribute("href", "/dashboard/provider");
    expect(screen.getByRole("link", { name: /Chat với Aminra/i })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /Doanh nghiệp/i })).toHaveAttribute("href", "/portfolio");
    expect(screen.getByRole("link", { name: /Chứng nhận/i })).toHaveAttribute("href", "/certificates");
    expect(screen.getByRole("link", { name: /Quản lý Auditor/i })).toHaveAttribute("href", "/auditors");
    expect(screen.getByRole("link", { name: /Hồ sơ nhận/i })).toHaveAttribute("href", "/submissions");
    expect(screen.getByRole("link", { name: /Kiểm định/i })).toHaveAttribute("href", "/audits");
    expect(screen.getByRole("link", { name: /Admin Panel/i })).toHaveAttribute("href", "/admin");
  });

  it("does not show admin navigation on /admin unless Keycloak realm authority is present", () => {
    adminState.isAdmin = false;

    render(<Sidebar />);

    expect(screen.queryByText("AMINRA Platform Admin")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Analytics/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Audit logs/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Overdue queue/i })).not.toBeInTheDocument();
  });
});
