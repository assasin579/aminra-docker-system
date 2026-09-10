/**
 * Static-analysis guard for token discipline.
 *
 * Catches regressions of two related bug families:
 *   A. Admin pages reading the wrong storage key (the 2026-04-25 bug)
 *   B. Non-admin pages bypassing useUserAuth() and inlining
 *      localStorage.getItem('aminra_user_token') reads — same anti-pattern,
 *      different blast radius (skips token freshness/verification logic)
 *
 * Rules enforced (per file under app/):
 *   1. NO file may read 'aminra_admin_token' directly except:
 *        - components/AdminAuthContext.tsx     (defines the key)
 *        - lib/adminAuth.ts                    (the shared helper)
 *        - lib/auth-session-cleanup.ts         (central purge-only helper)
 *        - components/UserAuthContext.tsx      (cross-context cleanup on login/logout)
 *        - app/account/confirm-deletion/page.tsx (clears all tokens on delete)
 *
 *   2. NO file under app/ may read 'aminra_user_token' directly except:
 *        - lib/adminAuth.ts                    (the shared helper)
 *        - app/account/confirm-deletion/page.tsx (clears all tokens on delete)
 *      Frontend pages must use useUserAuth() from components/UserAuthContext.
 */
import { test, expect } from "@playwright/test";
import { readFile, readdir, stat } from "node:fs/promises";
import { join, relative } from "node:path";

const ROOT = process.cwd();

const ADMIN_KEY_ALLOWED = new Set<string>([
  "components/AdminAuthContext.tsx",
  "components/UserAuthContext.tsx",
  "lib/adminAuth.ts",
  "lib/auth-session-cleanup.ts",
  "app/account/confirm-deletion/page.tsx",
]);

const USER_KEY_ALLOWED = new Set<string>([
  "components/UserAuthContext.tsx",
  "components/AdminAuthContext.tsx",
  "lib/adminAuth.ts",
  "lib/auth-session-cleanup.ts",
  "app/account/confirm-deletion/page.tsx",
]);

async function walk(dir: string, out: string[] = []): Promise<string[]> {
  for (const entry of await readdir(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    const s = await stat(full);
    if (s.isDirectory()) await walk(full, out);
    else if (/\.(tsx?|mts|cts)$/.test(full)) out.push(full);
  }
  return out;
}

test("no page reads aminra_admin_token outside the allowed central files", async () => {
  const offenders: string[] = [];
  for (const dir of ["app", "components", "lib"]) {
    const files = await walk(join(ROOT, dir));
    for (const file of files) {
      const rel = relative(ROOT, file);
      const src = await readFile(file, "utf8");
      if (!src.includes("aminra_admin_token")) continue;
      if (ADMIN_KEY_ALLOWED.has(rel)) continue;
      offenders.push(rel);
    }
  }
  expect(
    offenders,
    "Files reading 'aminra_admin_token' must be in the allowed list (lib/adminAuth.ts, AuthContexts, confirm-deletion).\n" +
      "If a new admin page legitimately needs the token, add an export to lib/adminAuth.ts and use it.\n" +
      "Offenders:\n" +
      offenders.map((f) => "  - " + f).join("\n"),
  ).toEqual([]);
});

test("no page reads aminra_user_token outside the allowed central files", async () => {
  const offenders: string[] = [];
  for (const dir of ["app", "components", "lib"]) {
    const files = await walk(join(ROOT, dir));
    for (const file of files) {
      const rel = relative(ROOT, file);
      const src = await readFile(file, "utf8");
      if (!src.includes("aminra_user_token")) continue;
      if (USER_KEY_ALLOWED.has(rel)) continue;
      offenders.push(rel);
    }
  }
  expect(
    offenders,
    "Files reading 'aminra_user_token' must use useUserAuth() from components/UserAuthContext or readAdminToken from @/lib/adminAuth.\n" +
      "Direct localStorage reads bypass token freshness checks and are how the 2026-04-25 admin auth bug shipped.\n" +
      "Offenders:\n" +
      offenders.map((f) => "  - " + f).join("\n"),
  ).toEqual([]);
});
