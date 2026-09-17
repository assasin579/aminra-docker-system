import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("admin user delete Keycloak sync contract", () => {
  const src = readFileSync(join(process.cwd(), "components/AdminUserManager.tsx"), "utf8");

  it("does not show false delete success when backend rejects Keycloak cleanup", () => {
    const deleteHandler = src.match(/const handleDelete = async \(id: string\) => \{[\s\S]*?^\s{2}\};/m)?.[0] ?? "";

    expect(deleteHandler).toContain("const res = await fetch");
    expect(deleteHandler).toContain("method: \"DELETE\"");
    expect(deleteHandler).toContain("if (!res.ok)");
    expect(deleteHandler).toContain("const err = await res.json().catch(() => ({}))");
    expect(deleteHandler).toContain("parseApiError(err");
    expect(deleteHandler).toContain("Dữ liệu chưa bị xoá");

    const errorBranch = deleteHandler.match(/if \(!res\.ok\) \{[\s\S]*?return;[\s\S]*?\}/)?.[0] ?? "";
    expect(errorBranch).toContain("return;");
  });
});
