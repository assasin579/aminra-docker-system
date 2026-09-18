import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("admin user delete is no longer app-owned", () => {
  const src = readFileSync(join(process.cwd(), "components/AdminUserManager.tsx"), "utf8");

  it("removes destructive delete UX from AMINRA Admin and points operators to Keycloak", () => {
    expect(src).toContain('data-identity-owner="keycloak"');
    expect(src).toContain("Open in Keycloak");
    expect(src).toContain("Tạo/xoá/vô hiệu hoá user");
    expect(src).toContain("delete-impact");
    expect(src).toContain("Đánh giá trước khi xóa");
    expect(src).toContain("deletion_warnings");
    expect(src).not.toContain("handleDelete");
    expect(src).not.toContain('method: "DELETE"');
    expect(src).not.toContain("Xác nhận xoá user");
    expect(src).not.toContain("Dữ liệu chưa bị xoá");
  });
});
