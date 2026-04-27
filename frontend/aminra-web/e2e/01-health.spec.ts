import { test, expect } from "./fixtures";

test.describe("01. Infrastructure health", () => {
  test("Backend /health returns ok + db + qdrant", async ({ api }) => {
    const r = await api.get("/health");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.status).toBe("ok");
    expect(body.database).toBe("connected");
    expect(body.qdrant).toBe("connected");
  });

  test("Frontend landing renders with expected title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Aminra|Halal/i);
  });

  test("OpenAPI spec has ≥100 paths", async ({ api }) => {
    const r = await api.get("/openapi.json");
    expect(r.status()).toBe(200);
    const spec = await r.json();
    expect(Object.keys(spec.paths ?? {}).length).toBeGreaterThan(100);
  });
});
