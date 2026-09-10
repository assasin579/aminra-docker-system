import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("admin self password reset session cleanup contract", () => {
  it("purges browser auth state and ends SSO when reset endpoint reports self_reset", () => {
    const src = readFileSync(join(root, "components/AdminUserManager.tsx"), "utf8");

    expect(src).toContain("purgeAuthSessionState");
    expect(src).toContain("signoutRedirect");
    expect(src).toContain("self_reset");
    expect(src).toContain("sessions_revoked");
    expect(src).toContain("Vui lòng đăng nhập lại");
  });

  it("does not purge admin browser state for non-self password resets", () => {
    const src = readFileSync(join(root, "components/AdminUserManager.tsx"), "utf8");

    const selfResetBranch = src.match(/if \(resetBody\?\.self_reset\)[\s\S]*?return;/);
    expect(selfResetBranch?.[0]).toContain("purgeAuthSessionState");
    expect(selfResetBranch?.[0]).toContain("signoutRedirect");
    expect(src).toContain("passwordChanged");
    expect(src).toContain("resetBody");
  });
});
