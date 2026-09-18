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

  it("lets admins clean uploaded files from the warning panel before Keycloak deletion", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.startsWith("/api/admin/users?")) {
        return Response.json({ users: [projectionUser], total: 1 });
      }
      if (url === "/api/admin/users/user-123/delete-impact") {
        return Response.json({
          user: projectionUser,
          impact: { documents_uploaded: 2, tenant_members: 0 },
          risk_level: "medium",
          hard_delete_safe: false,
          deletion_warnings: ["documents_uploaded: 2 reference(s) could be cascade-deleted by a hard DB delete; keep projection unless explicitly purging test data."],
          recommended_action: "delete_keycloak_identity_and_keep_projection",
        });
      }
      if (url === "/api/admin/users/user-123/related-files/cleanup" && init?.method === "POST") {
        return Response.json({
          user: projectionUser,
          cleanup: {
            scope: "documents.user_id physical files only; DB rows kept for audit",
            deleted_files: 2,
            cleared_document_rows: 2,
            missing_files: 0,
            skipped_files: 0,
          },
          safe_next_step: "Delete/disable the Keycloak account only after reviewing skipped_files and missing_files.",
        });
      }
      return Response.json({ detail: "unexpected request" }, { status: 500 });
    });

    render(<AdminUserManager token="admin-token" />);

    await userEvent.click(await screen.findByRole("button", { name: "Đánh giá trước khi xóa" }));
    await userEvent.click(await screen.findByRole("button", { name: "Tìm và xóa file liên quan" }));

    const statusPanel = await screen.findByRole("status");
    expect(statusPanel).toHaveTextContent("Đã xóa 2 file");
    expect(statusPanel).toHaveTextContent("DB rows kept for audit");

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/users/user-123/related-files/cleanup",
        expect.objectContaining({
          method: "POST",
          headers: { Authorization: "Bearer admin-token" },
        }),
      ),
    );
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
});
