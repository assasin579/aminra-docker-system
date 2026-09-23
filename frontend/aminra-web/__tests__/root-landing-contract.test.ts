import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, expect, test } from "vitest";

const ROOT = process.cwd();

async function readProjectFile(relativePath: string): Promise<string> {
  return readFile(join(ROOT, relativePath), "utf8");
}

describe("root landing route contract", () => {
  test("app root redirects on the server straight to /landing without auth-shell flash", async () => {
    const src = await readProjectFile("app/page.tsx");

    expect(src).toContain("redirect(\"/landing\")");
    expect(src).not.toContain("use client");
    expect(src).not.toContain("useUserAuth");
    expect(src).not.toContain("useRouter");
    expect(src).not.toMatch(/router\.replace\(["']\/(chat|landing)["']\)/);
    expect(src).not.toMatch(/return\s+null/);
  });

  test("public home/back/auth fallback links bypass the legacy root auth shell", async () => {
    const publicFiles = [
      "components/Navbar.tsx",
      "app/privacy/page.tsx",
      "app/terms/page.tsx",
      "app/account/confirm-deletion/page.tsx",
      "app/submissions/page.tsx",
      "lib/auth-oidc.ts",
    ];

    const offenders: string[] = [];
    for (const relativePath of publicFiles) {
      const src = await readProjectFile(relativePath);
      if (/href=[{]?['"]\/['"]/.test(src)) offenders.push(`${relativePath}: href to /`);
      if (/router\.(push|replace)\(['"]\/['"]\)/.test(src)) {
        offenders.push(`${relativePath}: router navigation to /`);
      }
      if (/returnTo\s*\?\?\s*['"]\/['"]/.test(src)) {
        offenders.push(`${relativePath}: OIDC returnTo defaults to /`);
      }
      if (/post_logout_redirect_uri:\s*`\$\{origin\}\/`/.test(src)) {
        offenders.push(`${relativePath}: OIDC post-logout defaults to /`);
      }
      if (/\?\s*`\$\{window\.location\.origin\}\/`/.test(src)) {
        offenders.push(`${relativePath}: OIDC end-session defaults to /`);
      }
    }

    expect(offenders).toEqual([]);
  });
});
