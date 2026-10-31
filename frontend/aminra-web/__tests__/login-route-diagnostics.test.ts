// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "../app/api/auth/login/route";

const secret = "NEVER_LOG_password_token_email@example.test";
const request = (body: unknown = { email: secret, password: secret, role: "business" }) =>
  new NextRequest("http://localhost/api/auth/login", { method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-ID": secret }, body: JSON.stringify(body) });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let fetchMock: ReturnType<typeof vi.fn>;
let logs: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
  logs = vi.spyOn(console, "info").mockImplementation(() => {});
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
type DiagnosticEvent = {
  stage: string; status: number | null; outcome: string; request_id: string; elapsed_ms: number;
};
function events(): DiagnosticEvent[] {
  return logs.mock.calls.map((args: unknown[]) => JSON.parse(String(args[0])) as DiagnosticEvent);
}
function assertDiagnostics(response: Response) {
  const id = response.headers.get("X-Request-ID");
  expect(id).toMatch(/^[a-f0-9-]{36}$/);
  expect(response.headers.get("Cache-Control")).toBe("no-store");
  expect(JSON.stringify(logs.mock.calls)).not.toContain(secret);
  for (const event of events()) {
    expect(Object.keys(event).sort()).toEqual(["elapsed_ms", "event", "outcome", "request_id", "stage", "status"]);
    expect(event.request_id).toBe(id);
    expect(event.elapsed_ms).toBeGreaterThanOrEqual(0);
  }
}
describe("login failure attribution without secrets", () => {
  it("correlates successful token/profile/completion and preserves no-store upstream fetches", async () => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(json({ role: "business", email: secret }));
    const response = await POST(request());
    expect(response.status).toBe(200);
    expect((await response.json()).access_token).toBe(secret);
    expect(events().map(e => [e.stage, e.status])).toEqual([["token", 200], ["profile", 200], ["complete", 200]]);
    expect(fetchMock.mock.calls.every(call => call[1].cache === "no-store")).toBe(true);
    assertDiagnostics(response);
  });
  it.each([401, 403, 503])("preserves profile refusal %s without returning a token", async status => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(json({ detail: secret }, status));
    const response = await POST(request());
    expect(response.status).toBe(status);
    expect(await response.text()).not.toContain(secret);
    expect(events().find(e => e.stage === "profile")?.status).toBe(status);
    assertDiagnostics(response);
  });
  it.each([401, 503])("attributes token upstream %s and preserves existing status mapping", async status => {
    fetchMock.mockResolvedValueOnce(json({ error: "invalid_grant", error_description: secret }, status));
    const response = await POST(request());
    expect(response.status).toBe(status === 401 ? 401 : 502);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(events()[0]).toMatchObject({ stage: "token", status });
    assertDiagnostics(response);
  });
  it.each(["token", "profile"])("redacts thrown transport errors at %s", async stage => {
    if (stage === "profile") fetchMock.mockResolvedValueOnce(json({ access_token: secret }));
    fetchMock.mockRejectedValueOnce(new Error(secret));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(events().find(e => e.outcome === "transport_error")).toMatchObject({ stage, status: null });
    assertDiagnostics(response);
  });
  it("records invalid token JSON without logging the body", async () => {
    fetchMock.mockResolvedValueOnce(new Response(secret, { status: 503 }));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(events()[0]).toMatchObject({ stage: "token", outcome: "invalid_response", status: 503 });
    assertDiagnostics(response);
  });
  it.each([null, [], "invalid", 42])("rejects invalid successful profile %j without returning a token", async profile => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(json(profile));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain(secret);
    expect(events()[1]).toMatchObject({ stage: "profile", status: 200, outcome: "invalid_response" });
    assertDiagnostics(response);
  });
  it("preserves upstream profile 503 with an unreadable response body", async () => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(new Response(secret, { status: 503 }));
    const response = await POST(request());
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain(secret);
    expect(events()[1]).toMatchObject({ stage: "profile", status: 503, outcome: "invalid_response" });
    assertDiagnostics(response);
  });
  it("rejects a non-string access token before profile access", async () => {
    fetchMock.mockResolvedValueOnce(json({ access_token: { secret } }));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    assertDiagnostics(response);
  });
  it("correlates malformed request JSON without upstream access", async () => {
    const response = await POST(new NextRequest("http://localhost/api/auth/login", {
      method: "POST", body: secret,
    }));
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
    assertDiagnostics(response);
  });
  it("returns 502 when a successful profile response is not JSON", async () => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(new Response(secret, { status: 200 }));
    const response = await POST(request());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain(secret);
    assertDiagnostics(response);
  });
  it("keeps concurrent login diagnostics bound to their own response ID", async () => {
    fetchMock.mockImplementation(async (url: string) =>
      url.endsWith("/token") ? json({ access_token: secret }) : json({ role: "business", email: secret }));
    const responses = await Promise.all([POST(request()), POST(request())]);
    const ids = responses.map(response => response.headers.get("X-Request-ID"));
    expect(new Set(ids).size).toBe(2);
    expect(JSON.stringify(logs.mock.calls)).not.toContain(secret);
    for (const response of responses) {
      expect(response.status).toBe(200);
      const ownEvents = events().filter(event => event.request_id === response.headers.get("X-Request-ID"));
      expect(ownEvents.map(event => event.stage)).toEqual(["token", "profile", "complete"]);
    }
  });
  it("retains role mismatch denial", async () => {
    fetchMock.mockResolvedValueOnce(json({ access_token: secret }))
      .mockResolvedValueOnce(json({ role: "provider", email: secret }));
    const response = await POST(request());
    expect(response.status).toBe(403);
    expect(await response.text()).not.toContain(secret);
    assertDiagnostics(response);
  });
  it.each([null, [], {}])("rejects invalid payload %j before upstream access", async body => {
    const response = await POST(request(body));
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
    assertDiagnostics(response);
  });
  it("generates distinct IDs across requests", async () => {
    const a = await POST(request(null));
    const b = await POST(request(null));
    expect(a.headers.get("X-Request-ID")).not.toBe(b.headers.get("X-Request-ID"));
  });
});
