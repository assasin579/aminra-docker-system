// @vitest-environment node
import { afterEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/auth/login/route";

afterEach(() => vi.unstubAllGlobals());
function loginRequest() {
  return new NextRequest("http://localhost/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "synthetic@example.invalid", password: "synthetic-only", role: "business" }) });
}
for (const trace of ["a".repeat(32), "untrusted-identifier"]) {
  it(`preserves the authority failure status and only forwards a validated trace (${trace.length})`, async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ access_token: "synthetic-token" }))
      .mockResolvedValueOnce(Response.json({ detail: "Internal details must stay private" }, { status: 503, headers: { "X-Aminra-Auth-Trace": trace, "X-Aminra-Auth-Error": "authority_unavailable" } })));
    const response = await POST(loginRequest());
    expect(response.status).toBe(503);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("X-Aminra-Auth-Trace")).toBe(trace.length === 32 ? trace : null);
    expect(response.headers.get("X-Aminra-Auth-Error")).toBe("authority_unavailable");
    const body = await response.json();
    expect(JSON.stringify(body)).not.toContain("Internal details");
    expect(body.access_token).toBeUndefined();
  });
}
it("a successful token exchange cannot turn a rejected profile into an authenticated login", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ access_token: "synthetic-token" }))
    .mockResolvedValueOnce(Response.json({ detail: "Inactive" }, { status: 401 })));
  const response = await POST(loginRequest());
  expect(response.status).toBe(401);
  expect((await response.json()).access_token).toBeUndefined();
});
it("successful login responses containing credentials are explicitly non-cacheable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ access_token: "synthetic-token" }))
    .mockResolvedValueOnce(Response.json({ id: "synthetic-user", role: "business" })));
  const response = await POST(loginRequest());
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
});
