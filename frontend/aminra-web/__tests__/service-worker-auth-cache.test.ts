import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("service worker auth/admin cache recovery", () => {
  it("keeps auth and admin routes network-only and supports immediate activation", () => {
    const sw = readFileSync(join(root, "public/sw.js"), "utf8");

    expect(sw).toContain('CACHE_NAME = "aminra-v6"');
    expect(sw).toContain("/\\/auth(?:\\/|$)/");
    expect(sw).toContain("/\\/admin(?:\\/|$)/");
    expect(sw).toContain('type === "SKIP_WAITING"');
    expect(sw).toContain("event.respondWith(fetch(request))");
  });

  it("forces service worker update and evicts stale AMINRA caches on auth-critical routes", () => {
    const layout = readFileSync(join(root, "app/layout.tsx"), "utf8");

    expect(layout).toContain("updateViaCache: 'none'");
    expect(layout).toContain("registration.update()");
    expect(layout).toContain("registration.waiting.postMessage");
    expect(layout).toContain("key.startsWith('aminra-')");
    expect(layout).toContain("key !== 'aminra-v6'");
    expect(layout).toContain("window.location.pathname.startsWith('/auth/callback')");
  });
});
