import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const allowedDirectCleanupFiles = new Set([
  "lib/auth-session-cleanup.ts",
  "__tests__/auth-session-cleanup.test.ts",
  "__tests__/auth-token-cleanup-guardrails.test.ts",
]);

function walk(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];
  for (const entry of entries) {
    if (["node_modules", ".next", "coverage", "__tests__", "e2e"].includes(entry)) continue;
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) files.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(entry)) files.push(full);
  }
  return files;
}

describe("auth token cleanup guardrails", () => {
  it("centralizes direct AMINRA/OIDC token removal in auth-session-cleanup", () => {
    const offenders: string[] = [];
    const directCleanupPattern = /(localStorage|sessionStorage)\.removeItem\((?:["']aminra_(?:user_token|user_profile|admin_token)["']|[^)]*oidc\.)/;
    for (const full of walk(root)) {
      const file = relative(root, full);
      if (allowedDirectCleanupFiles.has(file)) continue;
      const src = readFileSync(full, "utf8");
      if (directCleanupPattern.test(src)) offenders.push(file);
    }
    expect(offenders).toEqual([]);
  });
});
