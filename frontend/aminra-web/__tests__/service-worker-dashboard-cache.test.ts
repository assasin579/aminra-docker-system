import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

type FetchEventStub = {
  request: Request;
  respondWith(response: Promise<Response>): void;
};

describe("service worker tenant-scoped dashboard caching", () => {
  it("never serves a stale cached dossier dashboard when network fetch fails", async () => {
    const source = readFileSync(resolve(process.cwd(), "public/sw.js"), "utf8");
    const handlers = new Map<string, (event: FetchEventStub) => void>();
    const cacheMatch = vi.fn(async () => new Response("tenant-a-stale", { status: 200 }));
    const cache = { addAll: vi.fn(async () => undefined), put: vi.fn(async () => undefined) };
    const cachesMock = {
      open: vi.fn(async () => cache),
      match: cacheMatch,
      keys: vi.fn(async () => ["aminra-v9"]),
      delete: vi.fn(async () => true),
    };
    const networkFetch = vi.fn(async (_request: Request) => {
      throw new TypeError("synthetic network offline");
    });
    const workerSelf = {
      location: { origin: "https://aminra.synthetic.invalid" },
      addEventListener: (name: string, handler: (...args: never[]) => void) => {
        handlers.set(name, handler as unknown as (event: FetchEventStub) => void);
      },
      skipWaiting: vi.fn(async () => undefined),
      clients: { claim: vi.fn(async () => undefined), matchAll: vi.fn(async () => []), openWindow: vi.fn() },
    };

    runInNewContext(source, {
      self: workerSelf,
      caches: cachesMock,
      fetch: networkFetch,
      URL,
      Request,
      Response,
      Promise,
      console,
    });

    const event: FetchEventStub & { response?: Promise<Response> } = {
      request: new Request("https://aminra.synthetic.invalid/api/dossiers/dashboard"),
      respondWith(response) { this.response = response; },
    };
    handlers.get("fetch")?.(event);
    expect(event.response).toBeDefined();
    await expect(event.response).rejects.toThrow("synthetic network offline");
    expect(cacheMatch).not.toHaveBeenCalled();
  });
});
