import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (relativePath: string) => readFileSync(join(root, relativePath), "utf8");

describe("Admin user management is Keycloak-only", () => {
  it("renders AMINRA accounts as a read-only identity projection", () => {
    const src = read("components/AdminUserManager.tsx");

    expect(src).toContain('data-identity-owner="keycloak"');
    expect(src).toContain("Keycloak là nơi duy nhất quản lý user/account");
    expect(src).toContain("Open in Keycloak");
    expect(src).toContain("identity_source");
    expect(src).toContain("identity_status");
    expect(src).toContain("keycloak_deleted_at");
    expect(src).toContain("Keycloak missing");
  });

  it("does not expose admin-side create/edit/delete/reset account actions", () => {
    const src = read("components/AdminUserManager.tsx");

    expect(src).not.toContain("openCreate");
    expect(src).not.toContain("openEdit");
    expect(src).not.toContain("handleSave");
    expect(src).not.toContain("handleDelete");
    expect(src).not.toContain('method: "POST"');
    expect(src).not.toContain('method: "PUT"');
    expect(src).not.toContain('method: "DELETE"');
    expect(src).not.toContain("reset-password");
    expect(src).not.toContain("Xác nhận xoá user");
  });
});
