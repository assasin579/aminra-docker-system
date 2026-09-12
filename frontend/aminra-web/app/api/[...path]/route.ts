/**
 * Catch-all proxy — forwards all /api/* requests to the backend container.
 * Runs server-side so it can resolve the Docker-internal hostname.
 */
import { NextRequest, NextResponse } from "next/server";

// Allow large file uploads (50MB) and longer timeouts
export const maxDuration = 120;
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://aminra-backend:8000";
const PUBLIC_TRACE_PROXY_CACHE_TTL_MS = Number(process.env.PUBLIC_TRACE_PROXY_CACHE_TTL_MS || "5000");
const PUBLIC_TRACE_PROXY_CACHE_MAX_ITEMS = Number(process.env.PUBLIC_TRACE_PROXY_CACHE_MAX_ITEMS || "512");
const publicTraceProxyCache = new Map<string, { expiresAt: number; status: number; headers: [string, string][]; body: string }>();

function cacheablePublicTracePath(req: NextRequest, path: string[]): string | null {
  if (req.method !== "GET") return null;
  if (path.length === 5 && path[0] === "api" && path[1] === "supply-chain" && path[2] === "batches" && path[3] === "trace") {
    return `${path.join("/")}${req.nextUrl.search || ""}`;
  }
  return null;
}

function responseFromCached(entry: { expiresAt: number; status: number; headers: [string, string][]; body: string }): Response {
  const headers = new Headers(entry.headers);
  headers.set("x-aminra-proxy-cache", "hit");
  return new Response(entry.body, { status: entry.status, headers });
}

function rememberPublicTrace(cacheKey: string, upstream: Response, body: string): void {
  if (PUBLIC_TRACE_PROXY_CACHE_TTL_MS <= 0 || upstream.status !== 200) return;
  const now = Date.now();
  if (publicTraceProxyCache.size >= PUBLIC_TRACE_PROXY_CACHE_MAX_ITEMS) {
    for (const [key, value] of publicTraceProxyCache.entries()) {
      if (value.expiresAt <= now) publicTraceProxyCache.delete(key);
    }
    if (publicTraceProxyCache.size >= PUBLIC_TRACE_PROXY_CACHE_MAX_ITEMS) {
      const oldest = publicTraceProxyCache.keys().next().value;
      if (oldest) publicTraceProxyCache.delete(oldest);
    }
  }
  const headers = new Headers(upstream.headers);
  headers.set("cache-control", "public, max-age=5, stale-while-revalidate=30");
  headers.set("x-aminra-proxy-cache", "miss");
  publicTraceProxyCache.set(cacheKey, {
    expiresAt: now + PUBLIC_TRACE_PROXY_CACHE_TTL_MS,
    status: upstream.status,
    headers: Array.from(headers.entries()),
    body,
  });
}

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const qs = req.nextUrl.search || "";
  const backendUrl = `${BACKEND}/${path.join("/")}${qs}`;
  const publicTraceCacheKey = cacheablePublicTracePath(req, path);
  if (publicTraceCacheKey) {
    const cached = publicTraceProxyCache.get(publicTraceCacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return responseFromCached(cached);
    }
  }

  const contentType = req.headers.get("content-type") || "";
  const isMultipart = contentType.includes("multipart/form-data");
  let body: BodyInit | null = null;

  if (req.method !== "GET" && req.method !== "HEAD") {
    if (isMultipart) {
      // Pass raw body — don't parse & re-encode (avoids boundary mismatch)
      body = await req.arrayBuffer();
    } else {
      body = await req.text();
    }
  }

  const headers: HeadersInit = {};
  req.headers.forEach((v, k) => {
    if (!["host", "connection", "content-length"].includes(k.toLowerCase())) {
      headers[k] = v;
    }
  });

  const upstream = await fetch(backendUrl, {
    method: req.method,
    headers,
    body,
    // @ts-ignore — allow streaming duplex
    duplex: "half",
  });

  // Public trace is sealed/immutable; short proxy cache absorbs QR burst traffic
  // without affecting authenticated or mutable API paths.
  if (publicTraceCacheKey) {
    const bodyText = await upstream.text();
    rememberPublicTrace(publicTraceCacheKey, upstream, bodyText);
    const cached = publicTraceProxyCache.get(publicTraceCacheKey);
    if (cached) return responseFromCached(cached);
    return new Response(bodyText, { status: upstream.status, headers: upstream.headers });
  }

  // Stream the response back (handles SSE / chunked transfer too)
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}
