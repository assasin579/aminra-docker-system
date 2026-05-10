/**
 * Server-side Keycloak refresh-token grant (ADR-005 Phase 2d).
 *
 * Pilot-scope tradeoff: tokens still live in browser memory + (legacy
 * compat) localStorage. This Route Handler is the foundation for the
 * future httpOnly-cookie hardening — when we move refresh tokens off
 * the JS heap, this endpoint gains a `Set-Cookie` step + reads cookie
 * input instead of body. Keep the contract stable so the FE doesn't
 * need a flag-day flip.
 *
 * Phase 6 (post-pilot) hardening:
 *   1. Read refresh_token from `cookie('aminra_refresh')` instead of body
 *   2. Set new refresh_token via `cookies().set(...)` httpOnly+Secure+SameSite=Lax
 *   3. Return only access_token in JSON body
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const KEYCLOAK_URL = process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://keycloak:8080";
const KEYCLOAK_REALM = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aminra";
const KEYCLOAK_CLIENT_ID =
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "aminra-frontend";
const FLAG_ENABLED =
  process.env.NEXT_PUBLIC_AUTH_KEYCLOAK_ENABLED === "true";

export async function POST(req: NextRequest) {
  if (!FLAG_ENABLED) {
    return NextResponse.json(
      { detail: "Keycloak SSO not enabled in this environment" },
      { status: 404 },
    );
  }
  let body: { refresh_token?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { detail: "Invalid JSON body" },
      { status: 400 },
    );
  }
  const refreshToken = body.refresh_token;
  if (!refreshToken || typeof refreshToken !== "string") {
    return NextResponse.json(
      { detail: "refresh_token required" },
      { status: 400 },
    );
  }

  const tokenUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
  const params = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: KEYCLOAK_CLIENT_ID,
  });

  const upstream = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
    cache: "no-store",
  });

  if (!upstream.ok) {
    const text = await upstream.text();
    return NextResponse.json(
      { detail: "Refresh failed", upstream_status: upstream.status, upstream_body: text.slice(0, 200) },
      { status: 401 },
    );
  }

  const data = (await upstream.json()) as {
    access_token: string;
    refresh_token: string;
    expires_in: number;
    refresh_expires_in: number;
    token_type: string;
  };

  // Phase 6: split — return only access_token in body, set refresh_token in
  // httpOnly cookie. For now, return both so existing FE keeps working.
  return NextResponse.json({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_in: data.expires_in,
    refresh_expires_in: data.refresh_expires_in,
    token_type: data.token_type,
  });
}

export async function GET() {
  return NextResponse.json(
    { detail: "Method not allowed; use POST with refresh_token in body" },
    { status: 405 },
  );
}
