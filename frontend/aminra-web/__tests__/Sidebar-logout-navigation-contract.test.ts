import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const sidebarSource = fs.readFileSync(
  path.join(process.cwd(), "components", "Sidebar.tsx"),
  "utf8",
);

describe("Sidebar logout navigation contract", () => {
  it("does not race user/admin logout with local router navigation", () => {
    const userLogoutBranch = sidebarSource.match(/onClick=\{\(\) => \{[\s\S]*?logoutUser\(\);[\s\S]*?setAvatarOpen\(false\);[\s\S]*?onClose\?\.\(\);[\s\S]*?\}\}/)?.[0] ?? "";
    const adminLogoutBranch = sidebarSource.match(/onClick=\{\(\) => \{[\s\S]*?logoutAdmin\(\);[\s\S]*?onClose\?\.\(\);[\s\S]*?\}\}/)?.[0] ?? "";

    expect(userLogoutBranch).toContain("logoutUser();");
    expect(adminLogoutBranch).toContain("logoutAdmin();");
    expect(userLogoutBranch).not.toContain("router.push");
    expect(adminLogoutBranch).not.toContain("router.push");
  });
});
