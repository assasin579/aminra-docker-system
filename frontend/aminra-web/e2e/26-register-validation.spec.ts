/**
 * Regression for the 2026-04-26 register bug:
 *   1. FE password rule said "≥8 chars" but BE rule was "≥10 + uppercase + lowercase + digit"
 *      → user got 422 with arrayed `detail` showing as "[object Object]"
 *   2. FE error parsing didn't unwrap FastAPI's array-form 422 detail.
 *
 * The fix lives in `lib/apiError.ts::parseApiError()` + `validatePassword()`,
 * applied to both register pages and `UserAuthContext.apiLogin`.
 */
import { test, expect } from "@playwright/test";

test.describe("register validation", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "register validation only needs desktop coverage",
    );
  });

  test("BE 422 with arrayed detail returns parseable msg", async ({
    request,
  }) => {
    const r = await request.post("/api/auth/business/register", {
      data: {
        email: `x_${Date.now()}@e.com`,
        password: "short",
        company_name: "T",
      },
    });
    expect(r.status()).toBe(422);
    const body = await r.json();
    expect(Array.isArray(body.detail)).toBeTruthy();
    expect(body.detail[0].msg).toMatch(/at least 10 characters/);
  });

  test("static guard: register pages import shared apiError helpers", async () => {
    const { readFile } = await import("node:fs/promises");
    const { join } = await import("node:path");
    const ROOT = process.cwd();

    const helper = await readFile(join(ROOT, "lib/apiError.ts"), "utf8");
    expect(helper).toContain("parseApiError");
    expect(helper).toContain("validatePassword");
    expect(
      helper,
      "FE password rule must match BE: ≥10 chars + upper + lower + digit",
    ).toMatch(/length < 10/);
    expect(helper).toMatch(/A-Z/);
    expect(helper).toMatch(/a-z/);
    expect(helper).toMatch(/0-9/);

    for (const path of [
      "app/(auth)/business/register/page.tsx",
      "app/(auth)/provider/register/page.tsx",
      "components/UserAuthContext.tsx",
    ]) {
      const src = await readFile(join(ROOT, path), "utf8");
      expect(
        src,
        `${path} must use parseApiError instead of err.detail`,
      ).toContain("parseApiError");
    }
  });

  test("valid password completes register successfully", async ({
    request,
  }) => {
    const r = await request.post("/api/auth/business/register", {
      data: {
        email: `valid_${Date.now()}@e.com`,
        password: "StrongP@ss2026",
        company_name: "Valid Test Co",
      },
    });
    expect(r.status()).toBe(201);
    const body = await r.json();
    expect(body.access_token).toBeTruthy();
    expect(body.user.role).toBe("business");
  });
});
