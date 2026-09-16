import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Sidebar from "@/components/Sidebar";
import { apiJson } from "@/lib/apiClient";

const routeState = vi.hoisted(() => ({ pathname: "/dashboard/business" }));
const userState = vi.hoisted(() => ({
  isAuthenticated: true,
  token: "business-token",
  user: {
    role: "business",
    is_owner: true,
    company_name: "Demo Business",
    email: "biz@example.com",
    tenant_id: "tenant-1",
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
    isAdmin: false,
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

vi.mock("@/lib/apiClient", () => ({
  apiJson: vi.fn(),
}));

const mockedApiJson = vi.mocked(apiJson);

describe("business sidebar module navigation", () => {
  beforeEach(() => {
    routeState.pathname = "/dashboard/business";
    userState.isAuthenticated = true;
    userState.token = "business-token";
    userState.user = {
      role: "business",
      is_owner: true,
      company_name: "Demo Business",
      email: "biz@example.com",
      tenant_id: "tenant-1",
    };
    mockedApiJson.mockReset();
  });

  it("hides traceability/process links when those modules are disabled for the tenant", async () => {
    mockedApiJson.mockResolvedValue({
      modules: [
        { code: "supplier_management", status: "enabled" },
        { code: "process_digitization", status: "disabled" },
        { code: "traceability", status: "disabled" },
      ],
    });

    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Nguyên vật liệu/i })).toHaveAttribute(
        "href",
        "/supply-chain/materials",
      );
      expect(screen.queryByRole("link", { name: /Quy trình/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: /Lô hàng/i })).not.toBeInTheDocument();
    });

    expect(mockedApiJson).toHaveBeenCalledWith("/api/api/me/modules", {
      token: "business-token",
      fallbackError: "Không tải được cấu hình module.",
    });
  });

  it("shows supply-chain links when their modules are enabled", async () => {
    mockedApiJson.mockResolvedValue({
      modules: [
        { code: "supplier_management", status: "enabled" },
        { code: "process_digitization", status: "enabled" },
        { code: "traceability", status: "trial" },
      ],
    });

    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Nguyên vật liệu/i })).toHaveAttribute(
        "href",
        "/supply-chain/materials",
      );
      expect(screen.getByRole("link", { name: /Quy trình/i })).toHaveAttribute(
        "href",
        "/supply-chain/process",
      );
      expect(screen.getByRole("link", { name: /Lô hàng/i })).toHaveAttribute(
        "href",
        "/supply-chain/batches",
      );
    });
  });

  it("fails open to preserve current demo navigation when module API is unavailable", async () => {
    mockedApiJson.mockRejectedValue(new Error("network"));

    render(<Sidebar />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /Nguyên vật liệu/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Quy trình/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Lô hàng/i })).toBeInTheDocument();
    });
  });
});
