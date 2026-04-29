/**
 * Catch-all proxy — forwards all /api/* requests to the backend container.
 * Runs server-side so it can resolve the Docker-internal hostname.
 */
import { NextRequest, NextResponse } from "next/server";

// Allow large file uploads (50MB) and longer timeouts
export const maxDuration = 120;
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://aminra-backend:8000";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const qs = req.nextUrl.search || "";
  const backendUrl = `${BACKEND}/${path.join("/")}${qs}`;

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
