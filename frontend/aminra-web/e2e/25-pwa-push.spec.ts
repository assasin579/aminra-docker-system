/**
 * PWA + Web Push readiness checks.
 *
 * 1. Manifest + icons + service worker assets reachable
 * 2. SW source contains push event handler
 * 3. VAPID public key endpoint returns base64url-encoded key
 * 4. Subscribe endpoint requires auth
 * 5. Subscribe endpoint accepts a valid PushSubscription shape
 */
import { test, expect } from "@playwright/test";

test.describe("PWA + web push", () => {
  test.beforeEach(async ({}, testInfo) => {
    test.skip(
      !testInfo.project.name.startsWith("desktop"),
      "PWA endpoint checks only need desktop coverage",
    );
  });

  test("manifest, icons, sw.js all served", async ({ request }) => {
    const paths = ["/manifest.json", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/sw.js"];
    for (const p of paths) {
      const r = await request.get(p);
      expect.soft(r.status(), `${p} should be 200`).toBe(200);
    }

    const sw = await (await request.get("/sw.js")).text();
    expect(sw).toContain("addEventListener('push'");
    expect(sw).toContain("addEventListener('notificationclick'");
    expect(sw).toContain("showNotification");

    const manifest = await (await request.get("/manifest.json")).json();
    expect(manifest.name).toContain("AMINRA");
    expect(manifest.icons.length).toBeGreaterThanOrEqual(2);
    expect(manifest.theme_color).toBe("#087653");
  });

  test("VAPID public key endpoint returns key", async ({ request }) => {
    const r = await request.get("/api/api/notifications/push-public-key");
    expect(r.status()).toBe(200);
    const body = await r.json();
    expect(body.key).toBeTruthy();
    expect(body.key.length).toBeGreaterThan(80);
    expect(body.key).toMatch(/^[A-Za-z0-9_-]+$/);
  });

  test("subscribe endpoint requires auth", async ({ request }) => {
    const r = await request.post("/api/api/notifications/push-subscriptions", {
      data: { endpoint: "https://fcm.googleapis.com/fake/abc", p256dh: "x", auth: "y" },
    });
    expect(r.status()).toBe(401);
  });

  test("subscribe + unsubscribe with auth round-trips", async ({ request }) => {
    const login = await request.post("/api/auth/login", {
      data: { email: "biz-demo-1@demo.aminra.vn", password: "DemoP@ss2026", role: "business" },
    });
    if (!login.ok()) test.skip(true, "biz-demo-1 not seeded");
    const { access_token } = await login.json();

    const fakeEndpoint = `https://fcm.googleapis.com/fake/${Date.now()}`;
    const sub = await request.post("/api/api/notifications/push-subscriptions", {
      headers: { Authorization: `Bearer ${access_token}` },
      data: {
        endpoint: fakeEndpoint,
        p256dh: "BHsBSv3gCO0NYtpL2YxRu0YxWkHwNJDpCqu5O-_rSWbSVQ-fK5mKrEpINJgdLGXg2sLmvDLWvj37rl4kKL7Vr04",
        auth: "k8JV6sTyNRVm0XdTCJv0YQ",
        user_agent: "playwright-test",
      },
    });
    expect(sub.status()).toBe(200);

    const unsub = await request.delete(
      `/api/api/notifications/push-subscriptions?endpoint=${encodeURIComponent(fakeEndpoint)}`,
      { headers: { Authorization: `Bearer ${access_token}` } },
    );
    expect(unsub.status()).toBe(200);
  });
});
