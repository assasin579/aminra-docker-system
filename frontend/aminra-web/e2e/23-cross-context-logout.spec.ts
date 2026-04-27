/**
 * Cross-context logout discipline (static check).
 *
 * After UserAuthContext.logout() or AdminAuthContext.logout(), no token
 * from EITHER context should linger in localStorage. We verify this by
 * statically inspecting the source: each context's logout function must
 * remove the *other* context's primary token key.
 *
 * Why static instead of integration? The integration test would require
 * triggering the contexts' logout buttons via DOM, which adds flake; the
 * cleanup is a pure storage operation, so source-level enforcement is
 * cheaper and tighter.
 */
import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const ROOT = process.cwd();

test("UserAuthContext.logout removes aminra_admin_token", async () => {
  const src = await readFile(join(ROOT, "components/UserAuthContext.tsx"), "utf8");
  const logoutMatch = src.match(/const logout = useCallback\(\(\) => \{([\s\S]*?)\}, \[\]\);/);
  expect(logoutMatch, "UserAuthContext.logout function not found").not.toBeNull();
  const body = logoutMatch![1];
  expect(body, "UserAuthContext.logout must remove 'aminra_admin_token'").toMatch(
    /removeItem\(['"]aminra_admin_token['"]\)/,
  );
});

test("AdminAuthContext.logout removes aminra_user_token", async () => {
  const src = await readFile(join(ROOT, "components/AdminAuthContext.tsx"), "utf8");
  const logoutMatch = src.match(/const logout = useCallback\(\(\) => \{([\s\S]*?)\}, \[token\]\);/);
  expect(logoutMatch, "AdminAuthContext.logout function not found").not.toBeNull();
  const body = logoutMatch![1];
  expect(body, "AdminAuthContext.logout must remove 'aminra_user_token'").toMatch(
    /removeItem\(['"]aminra_user_token['"]\)/,
  );
});
