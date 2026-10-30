import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("admin password reset is no longer app-owned", () => {
  it("keeps account credential reset out of the AMINRA Admin UI", () => {
    const src = readFileSync(join(root, "components/AdminUserManager.tsx"), "utf8");

    expect(src).toContain('data-identity-owner="keycloak"');
    expect(src).toContain("Keycloak là nơi duy nhất quản lý user/account");
    expect(src).toContain("reset mật khẩu");
    expect(src).not.toContain("purgeAuthSessionState");
    expect(src).not.toContain("signoutRedirect");
    expect(src).not.toContain("self_reset");
    expect(src).not.toContain("sessions_revoked");
    expect(src).not.toContain("passwordChanged");
  });
});
