import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminModuleManager from "@/components/AdminModuleManager";
import { apiJson } from "@/lib/apiClient";

vi.mock("@/lib/apiClient", () => ({
  apiJson: vi.fn(),
}));

const modulesPayload = {
  business_model: { code: "cinnamon_export", name_vi: "Quế xuất khẩu", name_en: "Cinnamon Export" },
  modules: [
    {
      code: "supplier_management",
      name_vi: "Quản lý NCC",
      name_en: "Supplier Management",
      category: "supply_chain",
      status: "enabled",
      required: true,
      default_enabled: true,
      display_order: 10,
      config: {},
      source: "business_model_default",
      access_label_vi: "Đang hoạt động",
    },
    {
      code: "traceability",
      name_vi: "Truy xuất lô hàng",
      name_en: "Traceability",
      category: "supply_chain",
      status: "disabled",
      required: false,
      default_enabled: true,
      display_order: 20,
      config: { rollout_note: "pilot only" },
      source: "admin_override",
      access_label_vi: "Chưa kích hoạt",
    },
  ],
};

const activationRequestsPayload = {
  requests: [
    {
      id: "request-1",
      tenant_id: "tenant-123",
      module_code: "process_digitization",
      module_name_vi: "Số hóa quy trình",
      status: "pending",
      requester_email: "owner@example.com",
      route_path: "/supply-chain/process",
      message: "Cần bật để demo quy trình",
      priority: "normal",
      sla_due_at: "2026-09-20T00:00:00Z",
      sla_state: "overdue",
      hours_until_due: -30,
      notification_count: 1,
    },
  ],
};

describe("AdminModuleManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiJson).mockResolvedValue(modulesPayload);
  });

  it("loads tenant modules through the admin backend API and renders dependency-safe controls", async () => {
    render(<AdminModuleManager token="admin-token" />);

    await userEvent.type(screen.getByLabelText(/tenant id/i), "tenant-123");
    await userEvent.click(screen.getByRole("button", { name: /tải module/i }));

    await waitFor(() => {
      expect(apiJson).toHaveBeenCalledWith("/api/auth/admin/tenants/tenant-123/modules", {
        token: "admin-token",
        fallbackError: "Không tải được module của tenant.",
      });
    });

    expect(await screen.findByText("Quản lý NCC")).toBeInTheDocument();
    expect(screen.getByText("Truy xuất lô hàng")).toBeInTheDocument();
    expect(screen.getByText("Quế xuất khẩu")).toBeInTheDocument();
    expect(screen.getByText(/required/i)).toBeInTheDocument();
    expect(screen.getByText(/pilot only/i)).toBeInTheDocument();
    expect(screen.getByText(/admin_override/i)).toBeInTheDocument();
    expect(screen.getByText(/Chưa kích hoạt/i)).toBeInTheDocument();
    expect(screen.getByTestId("module-status-traceability")).toHaveValue("disabled");
  });

  it("updates one module with admin_override payload and surfaces success without silent reload assumptions", async () => {
    vi.mocked(apiJson)
      .mockResolvedValueOnce(modulesPayload)
      .mockResolvedValueOnce({ code: "traceability", status: "trial" })
      .mockResolvedValueOnce({ ...modulesPayload, modules: [{ ...modulesPayload.modules[1], status: "trial" }] });

    render(<AdminModuleManager token="admin-token" />);

    await userEvent.type(screen.getByLabelText(/tenant id/i), "tenant-123");
    await userEvent.click(screen.getByRole("button", { name: /tải module/i }));
    await screen.findByText("Truy xuất lô hàng");

    await userEvent.selectOptions(screen.getByTestId("module-status-traceability"), "trial");
    await userEvent.click(screen.getByRole("button", { name: /lưu traceability/i }));

    await waitFor(() => {
      expect(apiJson).toHaveBeenCalledWith(
        "/api/auth/admin/tenants/tenant-123/modules/traceability",
        {
          method: "PATCH",
          token: "admin-token",
          json: { status: "trial", config: { rollout_note: "pilot only" } },
          fallbackError: "Không cập nhật được module traceability.",
        },
      );
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Đã cập nhật traceability → trial");
  });

  it("renders dependency blocker errors and does not show a false success", async () => {
    vi.mocked(apiJson)
      .mockResolvedValueOnce(modulesPayload)
      .mockRejectedValueOnce(new Error("MODULE_DEPENDENCY_MISSING:supplier_management"));

    render(<AdminModuleManager token="admin-token" />);

    await userEvent.type(screen.getByLabelText(/tenant id/i), "tenant-123");
    await userEvent.click(screen.getByRole("button", { name: /tải module/i }));
    await screen.findByText("Truy xuất lô hàng");

    await userEvent.selectOptions(screen.getByTestId("module-status-traceability"), "enabled");
    await userEvent.click(screen.getByRole("button", { name: /lưu traceability/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("MODULE_DEPENDENCY_MISSING:supplier_management");
    expect(screen.queryByText(/Đã cập nhật traceability/i)).not.toBeInTheDocument();
  });

  it("loads pending activation requests and approves one through the admin review API", async () => {
    vi.mocked(apiJson)
      .mockResolvedValueOnce(modulesPayload)
      .mockResolvedValueOnce(activationRequestsPayload)
      .mockResolvedValueOnce({ ...activationRequestsPayload.requests[0], status: "approved" })
      .mockResolvedValueOnce({ requests: [] })
      .mockResolvedValueOnce({ ...modulesPayload, modules: [{ ...modulesPayload.modules[1], status: "trial" }] });

    render(<AdminModuleManager token="admin-token" />);

    await userEvent.type(screen.getByLabelText(/tenant id/i), "tenant-123");
    await userEvent.click(screen.getByRole("button", { name: /tải module/i }));
    await screen.findByText("Truy xuất lô hàng");

    await userEvent.click(screen.getByRole("button", { name: /tải yêu cầu kích hoạt/i }));
    expect(await screen.findByText("Cần bật để demo quy trình")).toBeInTheDocument();
    expect(screen.getByText(/Quá hạn SLA/i)).toBeInTheDocument();
    expect(screen.getByText(/Đã báo operator: 1 lần/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /duyệt process_digitization/i }));

    await waitFor(() => {
      expect(apiJson).toHaveBeenCalledWith("/api/auth/admin/module-activation-requests/request-1", {
        method: "PATCH",
        token: "admin-token",
        json: { action: "approve", admin_note: "Approved from Tenant module console" },
        fallbackError: "Không xử lý được yêu cầu kích hoạt.",
      });
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Đã duyệt yêu cầu process_digitization");
  });

  it("lets operators trigger SLA breach escalation for overdue activation requests", async () => {
    vi.mocked(apiJson)
      .mockResolvedValueOnce(modulesPayload)
      .mockResolvedValueOnce(activationRequestsPayload)
      .mockResolvedValueOnce({
        escalated_count: 1,
        requests: [
          {
            ...activationRequestsPayload.requests[0],
            priority: "urgent",
            escalation_count: 1,
            assigned_operator_id: "operator-1",
          },
        ],
      });

    render(<AdminModuleManager token="admin-token" />);

    await userEvent.type(screen.getByLabelText(/tenant id/i), "tenant-123");
    await userEvent.click(screen.getByRole("button", { name: /tải module/i }));
    await screen.findByText("Truy xuất lô hàng");
    await userEvent.click(screen.getByRole("button", { name: /tải yêu cầu kích hoạt/i }));
    expect(await screen.findByText(/Quá hạn SLA/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /escalate overdue/i }));

    await waitFor(() => {
      expect(apiJson).toHaveBeenCalledWith("/api/auth/admin/module-activation-requests/escalate-overdue", {
        method: "POST",
        token: "admin-token",
        json: { tenant_id: "tenant-123" },
        fallbackError: "Không escalation được yêu cầu quá hạn.",
      });
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Đã escalation 1 yêu cầu quá hạn");
    expect(screen.getByText(/Urgent escalation/i)).toBeInTheDocument();
  });
});
