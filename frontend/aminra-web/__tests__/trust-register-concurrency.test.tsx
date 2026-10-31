import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useTrustRegister } from "@/components/trust/TrustRegister";

afterEach(() => vi.unstubAllGlobals());

it("serializes rapid submissions before React renders the disabled form", async () => {
  let complete: (response: Response) => void = () => {};
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") return new Promise<Response>(resolve => { complete = resolve; });
    return Response.json({ cases: [] });
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useTrustRegister<{ id: string }>("/cases", "cases", "synthetic-token"));
  await waitFor(() => expect(result.current.loading).toBe(false));
  let first!: ReturnType<typeof result.current.mutate>;
  let second!: ReturnType<typeof result.current.mutate>;
  act(() => {
    first = result.current.mutate("/cases", { title: "Repeated click" });
    second = result.current.mutate("/cases", { title: "Repeated click" });
  });
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  expect(result.current.pending).toBe(true);
  await act(async () => {
    complete(Response.json({ id: "saved-once" }));
    await Promise.all([first, second]);
  });
  expect(result.current.pending).toBe(false);
  expect(result.current.notice).toBe("Saved saved-once.");
});

it("a delayed session reload cannot overwrite the result of a completed write", async () => {
  let staleRead: (response: Response) => void = () => {};
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    const auth = new Headers(init?.headers).get("Authorization");
    if (init?.method === "POST") return Response.json({ id: "new-record" });
    if (auth === "Bearer refreshed-token" && !init?.method) {
      // The first read after token refresh is delayed; the write's refresh completes first.
      return new Promise<Response>(resolve => { staleRead = resolve; });
    }
    return Response.json({ cases: [] });
  }));
  const { result, rerender } = renderHook(({ token }) => useTrustRegister<{ id: string }>("/cases", "cases", token), { initialProps: { token: "old-token" } });
  await waitFor(() => expect(result.current.loading).toBe(false));
  rerender({ token: "refreshed-token" });
  const fetchMock = vi.mocked(fetch);
  // The mutation's own fresh read must return the persisted row rather than the delayed snapshot.
  fetchMock.mockImplementationOnce(async () => Response.json({ id: "new-record" }));
  fetchMock.mockImplementationOnce(async () => Response.json({ cases: [{ id: "new-record" }] }));
  await act(async () => { await result.current.mutate("/cases", { title: "New" }); });
  await act(async () => { staleRead(Response.json({ cases: [] })); });
  expect(result.current.rows).toEqual([{ id: "new-record" }]);
});

it("a token-refresh read started during a pending write cannot replace its saved result", async () => {
  let finishWrite: (response: Response) => void = () => {};
  let staleRead: (response: Response) => void = () => {};
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") return new Promise<Response>(resolve => { finishWrite = resolve; });
    if (new Headers(init?.headers).get("Authorization") === "Bearer refreshed-token") {
      return new Promise<Response>(resolve => { staleRead = resolve; });
    }
    return Response.json({ cases: [{ id: "new-record" }] });
  });
  vi.stubGlobal("fetch", fetchMock);
  const { result, rerender } = renderHook(({ token }) => useTrustRegister<{ id: string }>("/cases", "cases", token), { initialProps: { token: "old-token" } });
  await waitFor(() => expect(result.current.loading).toBe(false));
  let write!: ReturnType<typeof result.current.mutate>;
  act(() => { write = result.current.mutate("/cases", { title: "New" }); });
  rerender({ token: "refreshed-token" });
  await act(async () => { finishWrite(Response.json({ id: "new-record" })); await write; });
  await act(async () => { staleRead(Response.json({ cases: [] })); });
  expect(result.current.rows).toEqual([{ id: "new-record" }]);
});


it("an unconfirmed successful write blocks duplicate submission without inventing a saved receipt", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
    Response.json(init?.method === "POST" ? {} : { cases: [] }));
  vi.stubGlobal("fetch", fetchMock);
  const { result } = renderHook(() => useTrustRegister<{ id: string }>("/cases", "cases", "synthetic-token"));
  await waitFor(() => expect(result.current.loading).toBe(false));
  await act(async () => { await result.current.mutate("/cases", { title: "Uncertain receipt" }); });
  expect(result.current.uncertain).toBe(true);
  expect(result.current.notice).toBe("");
  expect(result.current.rows).toEqual([]);
  expect(result.current.error).toContain("did not confirm a saved record");
  await act(async () => { await result.current.mutate("/cases", { title: "Uncertain receipt" }); });
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
