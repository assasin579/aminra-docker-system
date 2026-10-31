import { afterEach, describe, expect, test, vi } from "vitest";
import { fetchBackendRead } from "@/lib/fetchBackendRead";

const reset = () => Object.assign(new TypeError("fetch failed"), { cause: { code: "UND_ERR_SOCKET" } });
afterEach(() => vi.unstubAllGlobals());

describe("upstream read transport recovery", () => {
  test.each(["GET", "HEAD"])("%s retries a closed socket once with the same authority", async method => {
    const response = new Response("authorized");
    const fetchMock = vi.fn().mockRejectedValueOnce(reset()).mockResolvedValueOnce(response);
    vi.stubGlobal("fetch", fetchMock);
    const options = { method, headers: { Authorization: "Bearer actor-a" } };
    expect(await fetchBackendRead("http://backend/history", options)).toBe(response);
    expect(fetchMock.mock.calls).toEqual([["http://backend/history", options], ["http://backend/history", options]]);
  });

  test.each(["POST", "PUT", "PATCH", "DELETE"])("%s is not automatically replayed", async method => {
    const fetchMock = vi.fn().mockRejectedValue(reset());
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchBackendRead("http://backend/command", { method, headers: { "Idempotency-Key": "client-receipt" } })).rejects.toThrow("fetch failed");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("a second reset propagates without an unbounded retry", async () => {
    const fetchMock = vi.fn().mockRejectedValue(reset());
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchBackendRead("http://backend/history", {})).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  test("an aborted read is not retried", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn().mockRejectedValue(reset());
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchBackendRead("http://backend/history", { signal: controller.signal })).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("unrelated errors propagate", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("invalid URL"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchBackendRead("invalid", {})).rejects.toThrow("invalid URL");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
