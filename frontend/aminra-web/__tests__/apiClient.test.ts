import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClientError, apiFetch, apiJson } from "@/lib/apiClient";

describe("apiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("attaches bearer token and serializes JSON body", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const body = await apiJson<{ ok: boolean }>("/api/api/supply-chain/processes", {
      method: "POST",
      token: "tok-123",
      json: { name: "Quy trình rang" },
    });

    expect(body).toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith(
      "/api/api/supply-chain/processes",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "Quy trình rang" }),
      }),
    );
    const init = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer tok-123");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("throws normalized FastAPI validation errors on non-2xx", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify({ detail: [{ loc: ["body", "name"], msg: "Field required" }] }),
        { status: 422, headers: { "content-type": "application/json" } },
      ),
    );

    await expect(
      apiFetch("/api/api/supply-chain/processes", {
        method: "POST",
        token: "tok-123",
        json: {},
        fallbackError: "Tạo quy trình thất bại",
      }),
    ).rejects.toMatchObject({
      name: "ApiClientError",
      status: 422,
      message: "name: Field required",
    });
  });

  it("turns network failures into user-facing ApiClientError", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(new TypeError("failed"));

    await expect(
      apiFetch("/api/api/supply-chain/processes", {
        method: "POST",
        token: "tok-123",
        json: { name: "X" },
        fallbackError: "Không thể tạo quy trình",
      }),
    ).rejects.toBeInstanceOf(ApiClientError);
  });
});
