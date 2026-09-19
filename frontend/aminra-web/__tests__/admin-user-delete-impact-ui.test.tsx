import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import AdminUserManager from "../components/AdminUserManager";

const projectionUser = {
  id: "user-123",
  email: "qa-admin-preflight@example.com",
  keycloak_sub: "kc-sub-123",
  identity_source: "keycloak",
  identity_status: "linked",
  keycloak_deleted_at: null,
  role: "business",
  company_name: "QA Business",
  company_code: "QA-BIZ",
  status: "active",
  is_owner: true,
  tenant_id: "user-123",
  created_at: new Date().toISOString(),
} as const;

describe("AdminUserManager delete-impact preflight UX", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a visible status panel above the table after clicking preflight", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?") || url === "/api/admin/users?") {
        return Response.json({ users: [projectionUser], total: 1 });
      }
      if (url === "/api/admin/users/user-123/delete-impact") {
        return Response.json({
          user: projectionUser,
          keycloak: {
            source_of_truth: "keycloak",
            keycloak_sub: projectionUser.keycloak_sub,
            identity_status: projectionUser.identity_status,
            keycloak_deleted_at: null,
          },
          impact: { documents: 0, tenant_members: 0 },
          risk_level: "none",
          hard_delete_safe: true,
          deletion_warnings: [],
          recommended_action: "delete_keycloak_identity_then_optionally_purge_zero-impact_projection",
        });
      }
      return Response.json({ detail: "unexpected request" }, { status: 500 });
    });

    render(<AdminUserManager token="admin-token" />);

    const preflightButton = await screen.findByRole("button", { name: "Đánh giá trước khi xóa" });
    await userEvent.click(preflightButton);

    const statusPanel = await screen.findByRole("status");
    expect(statusPanel).toHaveTextContent("Cảnh báo trước khi xóa Keycloak account");
    expect(statusPanel).toHaveTextContent("qa-admin-preflight@example.com");
    expect(statusPanel).toHaveTextContent("Risk: none");
    expect(statusPanel).toHaveTextContent("Không tìm thấy dữ liệu nghiệp vụ liên quan");

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/users/user-123/delete-impact",
        expect.objectContaining({ headers: { Authorization: "Bearer admin-token" } }),
      ),
    );
  });

  it("renders selectable cleanup references and deletes only checked references for a deleted Keycloak account", async () => {
    const deletedProjectionUser = {
      ...projectionUser,
      identity_status: "missing_in_keycloak",
      keycloak_deleted_at: new Date().toISOString(),
    } as const;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?")) {
        return Response.json({ users: [deletedProjectionUser], total: 1 });
      }
      if (url === "/api/admin/users/user-123/delete-impact") {
        return Response.json({
          user: deletedProjectionUser,
          impact: { documents_uploaded: 2, notifications: 3, push_subscriptions: 1, tenant_members: 0 },
          cleanup_options: [
            {
              key: "uploaded_document_files",
              label: "File vật lý đã upload",
              count: 2,
              action: "delete_physical_files_keep_document_rows",
              enabled: true,
              warning: "Giữ lại documents DB rows để audit.",
            },
            {
              key: "notifications",
              label: "Thông báo nội bộ",
              count: 3,
              action: "delete_rows",
              enabled: true,
              warning: "Xóa notification chỉ thuộc account đã mất Keycloak.",
            },
            {
              key: "documents_reviewed",
              label: "Lịch sử review tài liệu",
              count: 1,
              action: "keep_audit_record",
              enabled: false,
              warning: "Audit/business references không được xóa từ cleanup nhanh.",
            },
          ],
          risk_level: "medium",
          hard_delete_safe: false,
          deletion_warnings: ["documents_uploaded: 2 reference(s) could be cascade-deleted by a hard DB delete; keep projection unless explicitly purging test data."],
          recommended_action: "delete_keycloak_identity_and_keep_projection",
        });
      }
      if (url === "/api/admin/users/user-123/related-references/cleanup" && init?.method === "POST") {
        return Response.json({
          user: deletedProjectionUser,
          selected_references: ["uploaded_document_files", "notifications"],
          users_projection_deleted: false,
          documents_db_rows_deleted: false,
          cleanup: {
            uploaded_document_files: { deleted_files: 2, cleared_document_rows: 2, action: "delete_physical_files_keep_document_rows" },
            notifications: { action: "delete_rows" },
          },
          safe_next_step: "Review cleanup results. Keep users projection for audit unless a separate zero-impact purge is approved.",
        });
      }
      return Response.json({ detail: "unexpected request" }, { status: 500 });
    });

    render(<AdminUserManager token="admin-token" />);

    await userEvent.click(await screen.findByRole("button", { name: "Đánh giá trước khi xóa" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: /File vật lý đã upload/ }));
    await userEvent.click(await screen.findByRole("checkbox", { name: /Thông báo nội bộ/ }));
    expect(screen.queryByRole("checkbox", { name: /Lịch sử review tài liệu/ })).not.toBeInTheDocument();
    expect(screen.getByText("Giữ lại / cần quy trình riêng")).toBeInTheDocument();
    expect(screen.getByText("Không xóa nhanh")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Xóa reference đã chọn" }));

    const statusPanel = await screen.findByRole("status");
    expect(statusPanel).toHaveTextContent("Đã dọn 2 nhóm reference");
    expect(statusPanel).toHaveTextContent("users_projection_deleted=false");
    expect(statusPanel).toHaveTextContent("documents_db_rows_deleted=false");

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/users/user-123/related-references/cleanup",
        expect.objectContaining({
          method: "POST",
          headers: { Authorization: "Bearer admin-token", "Content-Type": "application/json" },
          body: JSON.stringify({ selected_references: ["uploaded_document_files", "notifications"] }),
        }),
      ),
    );
  });

  it("does not render fake checkboxes when all references are locked audit/business records", async () => {
    const deletedProjectionUser = {
      ...projectionUser,
      identity_status: "missing_in_keycloak",
      keycloak_deleted_at: new Date().toISOString(),
    } as const;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?")) {
        return Response.json({ users: [deletedProjectionUser], total: 1 });
      }
      if (url === "/api/admin/users/user-123/delete-impact") {
        return Response.json({
          user: deletedProjectionUser,
          impact: { audit_logs: 1, documents_reviewed: 1 },
          cleanup_options: [
            {
              key: "audit_logs",
              label: "Audit logs",
              count: 1,
              action: "keep_audit_record",
              enabled: false,
              warning: "Business/audit reference không được xóa từ cleanup nhanh; cần quy trình riêng nếu muốn purge.",
            },
            {
              key: "documents_reviewed",
              label: "Lịch sử review tài liệu",
              count: 1,
              action: "keep_audit_record",
              enabled: false,
              warning: "Business/audit reference không được xóa từ cleanup nhanh; cần quy trình riêng nếu muốn purge.",
            },
          ],
          risk_level: "high",
          hard_delete_safe: false,
          deletion_warnings: ["audit_logs: 1 reference(s) would lose actor linkage if DB row is hard-deleted."],
          recommended_action: "delete_keycloak_identity_and_keep_projection",
        });
      }
      return Response.json({ detail: "unexpected request" }, { status: 500 });
    });

    render(<AdminUserManager token="admin-token" />);

    await userEvent.click(await screen.findByRole("button", { name: "Đánh giá trước khi xóa" }));

    expect(await screen.findByText(/Không có reference nào đủ điều kiện cleanup nhanh/)).toBeInTheDocument();
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Xóa reference đã chọn" })).toBeDisabled();
    expect(screen.getAllByText("Không xóa nhanh")).toHaveLength(2);
  });

  it("surfaces backend detail when preflight fails instead of failing silently", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?")) {
        return Response.json({ users: [projectionUser], total: 1 });
      }
      return Response.json({ detail: "User projection not found" }, { status: 404 });
    });

    render(<AdminUserManager token="admin-token" />);

    await userEvent.click(await screen.findByRole("button", { name: "Đánh giá trước khi xóa" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Không tải được cảnh báo xóa Keycloak (HTTP 404): User projection not found",
    );
  });

  it("offers a governed deletion case workflow for locked audit/business references", async () => {
    const deletedProjectionUser = {
      ...projectionUser,
      identity_status: "missing_in_keycloak",
      keycloak_deleted_at: new Date().toISOString(),
    } as const;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?")) {
        return Response.json({ users: [deletedProjectionUser], total: 1 });
      }
      if (url === "/api/admin/users/user-123/delete-impact") {
        return Response.json({
          user: deletedProjectionUser,
          impact: { audit_logs: 1, documents_approved: 1, tenant_members: 0 },
          cleanup_options: [
            {
              key: "audit_logs",
              label: "Audit logs",
              count: 1,
              action: "keep_audit_record",
              enabled: false,
              warning: "Business/audit reference không được xóa từ cleanup nhanh; cần quy trình riêng nếu muốn purge.",
            },
          ],
          risk_level: "high",
          hard_delete_safe: false,
          deletion_warnings: ["audit_logs: 1 reference(s) would lose actor linkage if DB row is hard-deleted."],
          recommended_action: "delete_keycloak_identity_and_keep_projection",
        });
      }
      if (url === "/api/admin/users/user-123/deletion-case" && init?.method === "POST") {
        return Response.json({
          case: {
            id: "case-123",
            status: "assessment_ready",
            risk_level: "high",
            confirmation_phrase: "CONFIRM CLEANUP qa-admin-preflight@example.com",
          },
          items: [
            { reference_key: "audit_logs", label: "Audit logs", action: "retain_append_only_audit", record_count: 1, status: "skipped" },
            { reference_key: "documents_approved", label: "Tài liệu user đã approve", action: "detach_user_reference", record_count: 1, status: "pending" },
          ],
        });
      }
      if (url === "/api/admin/account-deletion-cases/case-123/run" && init?.method === "POST") {
        return Response.json({
          case: { id: "case-123", status: "completed", risk_level: "high" },
          result: { case_status: "completed", completed_items: 1, skipped_items: 1, blocked_items: 0 },
        });
      }
      return Response.json({ detail: "unexpected request" }, { status: 500 });
    });

    render(<AdminUserManager token="admin-token" />);

    await userEvent.click(await screen.findByRole("button", { name: "Đánh giá trước khi xóa" }));
    await userEvent.click(await screen.findByRole("button", { name: "Tạo hồ sơ xử lý an toàn" }));

    expect(await screen.findByText(/Hồ sơ cleanup: case-123/)).toBeInTheDocument();
    expect(screen.getByText(/retain_append_only_audit/)).toBeInTheDocument();
    expect(screen.getByText(/detach_user_reference/)).toBeInTheDocument();
    expect(screen.getByText(/CONFIRM CLEANUP qa-admin-preflight@example.com/)).toBeInTheDocument();

    await userEvent.click(await screen.findByRole("button", { name: "Chạy cleanup an toàn" }));
    expect(await screen.findByText(/Case completed/)).toBeInTheDocument();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/users/user-123/deletion-case",
        expect.objectContaining({ method: "POST" }),
      ),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/account-deletion-cases/case-123/run",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ confirmation_phrase: "CONFIRM CLEANUP qa-admin-preflight@example.com" }),
      }),
    );
  });
});
