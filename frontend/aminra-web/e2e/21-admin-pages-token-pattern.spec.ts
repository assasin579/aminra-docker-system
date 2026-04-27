/**
 * Static-analysis guard for admin pages.
 *
 * Catches the regression we hit on 2026-04-25 where /admin/analytics,
 * /admin/audit-logs, /admin/overdue-submissions only read `aminra_user_token`
 * and broke for users logged in via the legacy /admin flow.
 *
 * Rules enforced:
 *  1. Any file under app/admin/ * /page.tsx that calls /api/auth/admin/*
 *     MUST import readAdminToken from '@/lib/adminAuth' and not inline a
 *     localStorage.getItem('aminra_user_token') for that purpose.
 *  2. The shared helper must exist at lib/adminAuth.ts.
 */
import { test, expect } from "@playwright/test";
import { readFile, readdir, stat } from "node:fs/promises";
import { join } from "node:path";

// Playwright runs from the frontend project root.
const ROOT = process.cwd();

async function walk(dir: string, out: string[] = []): Promise<string[]> {
  for (const entry of await readdir(dir)) {
    const full = join(dir, entry);
    const s = await stat(full);
    if (s.isDirectory()) await walk(full, out);
    else if (full.endsWith("page.tsx") || full.endsWith("page.ts")) out.push(full);
  }
  return out;
}

test("admin pages use shared readAdminToken helper", async () => {
  const helperPath = join(ROOT, "lib/adminAuth.ts");
  const helperSrc = await readFile(helperPath, "utf8").catch(() => null);
  expect(helperSrc, "lib/adminAuth.ts must exist").not.toBeNull();
  expect(helperSrc!).toContain("readAdminToken");
  expect(helperSrc!).toContain("aminra_admin_token");
  expect(helperSrc!).toContain("aminra_user_token");

  const adminPages = await walk(join(ROOT, "app/admin"));
  expect(adminPages.length).toBeGreaterThan(0);

  const offenders: { file: string; reason: string }[] = [];
  for (const file of adminPages) {
    const src = await readFile(file, "utf8");
    const callsAdminApi = /\/api\/auth\/admin\//.test(src);
    if (!callsAdminApi) continue;

    if (!src.includes("readAdminToken")) {
      offenders.push({
        file: file.replace(ROOT + "/", ""),
        reason: "calls /api/auth/admin/* but does not import readAdminToken from '@/lib/adminAuth'",
      });
      continue;
    }
    const inlinesUserTokenOnly =
      /localStorage\.getItem\(['"]aminra_user_token['"]\)/.test(src) &&
      !/from ['"]@\/lib\/adminAuth['"]/.test(src);
    if (inlinesUserTokenOnly) {
      offenders.push({
        file: file.replace(ROOT + "/", ""),
        reason: "inlines localStorage.getItem('aminra_user_token') without using readAdminToken helper",
      });
    }
  }

  expect(
    offenders,
    "Admin pages must use readAdminToken from @/lib/adminAuth — see lib/adminAuth.ts header for context.\n" +
      "Offenders:\n" +
      offenders.map(o => `  - ${o.file}: ${o.reason}`).join("\n"),
  ).toEqual([]);
});
