import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://aminra-backend:8000";

export async function GET(): Promise<NextResponse> {
  try {
    const upstream = await fetch(`${BACKEND.replace(/\/$/, "")}/health`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    const contentType = upstream.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await upstream.json().catch(() => ({ status: "error", detail: "Invalid backend health JSON" }))
      : { status: upstream.ok ? "ok" : "error", detail: await upstream.text().catch(() => "") };

    return NextResponse.json(body, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { status: "error", detail: "Backend health endpoint unreachable" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
