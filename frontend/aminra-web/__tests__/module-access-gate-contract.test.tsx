import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ModuleAccessGate from "@/components/ModuleAccessGate";
import { apiJson } from "@/lib/apiClient";

const authState = vi.hoisted((): {
  isAuthenticated: boolean;
  token: string | null;
} => ({
  isAuthenticated: true,
  token: "business-token",
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => authState,
}));

vi.mock("@/lib/apiClient", () => ({
  apiJson: vi.fn(),
}));

const mockedApiJson = vi.mocked(apiJson);

const tenantModulesPayload = {
  business_model: {
    code: "restaurant_hotel",
    name_vi: "Nhà hàng / khách sạn",
  },
  modules: [
    {
      code: "supplier_management",
      name_vi: "Quản lý nhà cung cấp",
      status: "enabled",
      access_state: "active",
      access_label_vi: "Đang hoạt động",
      route_path: "/supply-chain/materials",
    },
    {
      code: "process_digitization",
      name_vi: "Số hóa quy trình",
      status: "disabled",
      access_state: "disabled",
      access_label_vi: "Chưa kích hoạt",
      locked_reason: "Module này chưa nằm trong gói hiện tại.",
      cta_label_vi: "Yêu cầu kích hoạt",
      route_path: "/supply-chain/process",
    },
  ],
};

describe("ModuleAccessGate direct-route locked UX", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.isAuthenticated = true;
    authState.token = "business-token";
    mockedApiJson.mockResolvedValue(tenantModulesPayload);
  });

  it("renders children only when the tenant module is active", async () => {
    render(
      <ModuleAccessGate moduleCode="supplier_management" routePath="/supply-chain/materials">
        <div>Supplier workspace</div>
      </ModuleAccessGate>,
    );

    expect(screen.getByText(/Đang kiểm tra quyền truy cập module/i)).toBeInTheDocument();
    expect(await screen.findByText("Supplier workspace")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Module chưa kích hoạt/i })).not.toBeInTheDocument();
    expect(mockedApiJson).toHaveBeenCalledWith("/api/api/me/modules", {
      token: "business-token",
      fallbackError: "Không kiểm tra được quyền truy cập module.",
    });
  });

  it("renders a locked-state screen for direct URL access to a disabled module", async () => {
    render(
      <ModuleAccessGate moduleCode="process_digitization" routePath="/supply-chain/process">
        <div>Process workspace must stay hidden</div>
      </ModuleAccessGate>,
    );

    expect(await screen.findByRole("heading", { name: /Module chưa kích hoạt/i })).toBeInTheDocument();
    expect(screen.getByText("Số hóa quy trình")).toBeInTheDocument();
    expect(screen.getByText("Module này chưa nằm trong gói hiện tại.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Xem gói module của tôi/i })).toHaveAttribute("href", "/modules");
    expect(screen.getByRole("button", { name: /Yêu cầu kích hoạt Số hóa quy trình/i })).toBeDisabled();
    expect(screen.queryByText("Process workspace must stay hidden")).not.toBeInTheDocument();
  });

  it("fails closed when module metadata cannot be loaded", async () => {
    mockedApiJson.mockRejectedValue(new Error("backend unavailable"));

    render(
      <ModuleAccessGate moduleCode="process_digitization" routePath="/supply-chain/process">
        <div>Process workspace must stay hidden</div>
      </ModuleAccessGate>,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("backend unavailable");
    });
    expect(screen.queryByText("Process workspace must stay hidden")).not.toBeInTheDocument();
  });
});
