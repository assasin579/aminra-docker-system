import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MyModulesPanel from "@/components/MyModulesPanel";
import { apiJson } from "@/lib/apiClient";

const authState = vi.hoisted((): {
  isAuthenticated: boolean;
  token: string | null;
  user: {
    role: string;
    company_name: string;
    tenant_id: string;
  };
} => ({
  isAuthenticated: true,
  token: "business-token",
  user: {
    role: "business",
    company_name: "Demo Foods",
    tenant_id: "tenant-1",
  },
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => authState,
}));

vi.mock("@/lib/apiClient", () => ({
  apiJson: vi.fn(),
}));

const mockedApiJson = vi.mocked(apiJson);

const modulesPayload = {
  business_model: {
    code: "food_manufacturing",
    name_vi: "Sản xuất thực phẩm",
    name_en: "Food manufacturing",
  },
  modules: [
    {
      code: "supplier_management",
      name_vi: "Quản lý nhà cung cấp",
      category: "operations",
      status: "enabled",
      required: true,
      default_enabled: true,
      source: "business_model_default",
      access_state: "active",
      access_label_vi: "Đang hoạt động",
      route_path: "/supply-chain/materials",
    },
    {
      code: "public_trace",
      name_vi: "QR truy xuất công khai",
      category: "trust",
      status: "locked",
      required: false,
      default_enabled: false,
      source: "admin_override",
      access_state: "locked",
      access_label_vi: "Đang khóa",
      locked_reason: "Chưa nằm trong gói hiện tại",
      cta_label_vi: "Yêu cầu kích hoạt",
      route_path: "/trace",
    },
  ],
};

describe("MyModulesPanel customer experience", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.isAuthenticated = true;
    authState.token = "business-token";
    mockedApiJson.mockResolvedValue(modulesPayload);
  });

  it("loads the tenant module package and explains active vs locked modules to a business user", async () => {
    render(<MyModulesPanel />);

    expect(screen.getAllByText(/Đang tải gói module/i).length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(mockedApiJson).toHaveBeenCalledWith("/api/api/me/modules", {
        token: "business-token",
        fallbackError: "Không tải được gói module của doanh nghiệp.",
      });
    });

    expect(await screen.findByRole("heading", { name: /Gói module của tôi/i })).toBeInTheDocument();
    expect(screen.getByText("Sản xuất thực phẩm")).toBeInTheDocument();
    expect(screen.getByText("Quản lý nhà cung cấp")).toBeInTheDocument();
    expect(screen.getByText("Đang hoạt động")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mở Quản lý nhà cung cấp/i })).toHaveAttribute(
      "href",
      "/supply-chain/materials",
    );
    expect(screen.getByText("QR truy xuất công khai")).toBeInTheDocument();
    expect(screen.getByText("Chưa nằm trong gói hiện tại")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Yêu cầu kích hoạt QR truy xuất công khai/i })).toBeDisabled();
  });

  it("shows a fail-closed unauthenticated state instead of calling module APIs without a token", () => {
    authState.isAuthenticated = false;
    authState.token = null;

    render(<MyModulesPanel />);

    expect(screen.getByRole("alert")).toHaveTextContent("Vui lòng đăng nhập để xem gói module.");
    expect(mockedApiJson).not.toHaveBeenCalled();
  });
});
