import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const TRACE_ID = "73695b8a-3c10-570b-8bba-92c12da9b56e";

async function loadRoute() {
  vi.resetModules();
  return import("../app/api/[...path]/route");
}

function traceRequest(traceId = TRACE_ID) {
  return new NextRequest(`http://localhost:3100/api/api/supply-chain/batches/trace/${traceId}`);
}

function adminRequest() {
  return new NextRequest("http://localhost:3100/api/api/admin/users");
}

const traceParams = { params: Promise.resolve({ path: ["api", "supply-chain", "batches", "trace", TRACE_ID] }) };
const adminParams = { params: Promise.resolve({ path: ["api", "admin", "users"] }) };
const adminModuleParams = {
  params: Promise.resolve({
    path: ["auth", "admin", "tenants", "tenant-123", "modules", "workforce"],
  }),
};

describe("public trace Next proxy cache contract", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubEnv("BACKEND_URL", "http://backend.test");
    vi.stubEnv("PUBLIC_TRACE_PROXY_CACHE_TTL_MS", "5000");
    vi.stubEnv("PUBLIC_TRACE_PROXY_CACHE_MAX_ITEMS", "512");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ batch: { public_trace_id: TRACE_ID } }), {
          status: 200,
          headers: {
            "content-type": "application/json",
            "vary": "rsc, next-router-state-tree, next-router-prefetch, next-router-segment-prefetch",
          },
        }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("marks sealed public trace API responses as shared-edge cacheable without Next RSC vary fragmentation", async () => {
    const route = await loadRoute();

    const first = await route.GET(traceRequest(), traceParams);
    const second = await route.GET(traceRequest(), traceParams);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(first.headers.get("cache-control")).toBe("public, max-age=5, stale-while-revalidate=30");
    expect(first.headers.get("cdn-cache-control")).toBe("public, max-age=30, stale-while-revalidate=60");
    expect(first.headers.get("cloudflare-cdn-cache-control")).toBe("public, max-age=30, stale-while-revalidate=60");
    expect(first.headers.get("vary")).toBe("Accept-Encoding");
    expect(second.headers.get("x-aminra-proxy-cache")).toBe("hit");
  });

  it("does not apply public trace cache headers to non-trace admin/API paths", async () => {
    const route = await loadRoute();

    const response = await route.GET(adminRequest(), adminParams);

    expect(response.headers.get("cdn-cache-control")).toBeNull();
    expect(response.headers.get("cloudflare-cdn-cache-control")).toBeNull();
    expect(response.headers.get("x-aminra-proxy-cache")).toBeNull();
  });

  it("exports PATCH so admin module status updates are proxied instead of Next returning 405", async () => {
    const route = await loadRoute();
    const request = new NextRequest(
      "http://localhost:3100/api/auth/admin/tenants/tenant-123/modules/workforce",
      {
        method: "PATCH",
        headers: {
          authorization: "Bearer test-token",
          "content-type": "application/json",
        },
        body: JSON.stringify({ status: "disabled", config: {} }),
      },
    );

    const response = await route.PATCH(request, adminModuleParams);

    expect(response.status).toBe(200);
    expect(fetch).toHaveBeenCalledWith(
      "http://backend.test/auth/admin/tenants/tenant-123/modules/workforce",
      expect.objectContaining({ method: "PATCH" }),
    );
  });
});
