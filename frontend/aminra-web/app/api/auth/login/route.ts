import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL || "http://aminra-backend:8000";
const KEYCLOAK_URL =
  process.env.KEYCLOAK_URL ||
  process.env.NEXT_PUBLIC_KEYCLOAK_URL ||
  "https://auth.silvergem.org";
const KEYCLOAK_REALM =
  process.env.KEYCLOAK_REALM ||
  process.env.NEXT_PUBLIC_KEYCLOAK_REALM ||
  "aminra";
const KEYCLOAK_CLIENT_ID =
  process.env.KEYCLOAK_CLIENT_ID ||
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ||
  "aminra-frontend";
const KEYCLOAK_CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET || "";

type LoginBody = {
  email?: unknown;
  password?: unknown;
  role?: unknown;
};

type TokenResponse = {
  access_token?: string;
  error?: string;
  error_description?: string;
};

function jsonError(message: string, status: number): NextResponse {
  return NextResponse.json({ detail: message }, { status });
}

function normalizeRole(role: unknown): "business" | "provider" | undefined {
  if (role === "business" || role === "provider") return role;
  return undefined;
}

function userMessageForKeycloakError(tokenBody: TokenResponse): string {
  const raw = `${tokenBody.error || ""} ${tokenBody.error_description || ""}`.toLowerCase();
  if (raw.includes("invalid_grant")) {
    return "Email hoặc mật khẩu không đúng.";
  }
  if (raw.includes("account is not fully set up") || raw.includes("required action")) {
    return "Tài khoản cần được admin AMINRA hoàn tất thiết lập trước khi đăng nhập.";
  }
  if (raw.includes("disabled")) {
    return "Tài khoản đang bị vô hiệu hóa. Vui lòng liên hệ AMINRA.";
  }
  return "Không thể xác thực tài khoản lúc này. Vui lòng thử lại sau.";
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: LoginBody;
  try {
    body = (await req.json()) as LoginBody;
  } catch {
    return jsonError("Payload đăng nhập không hợp lệ.", 400);
  }

  const email = typeof body.email === "string" ? body.email.trim() : "";
  const password = typeof body.password === "string" ? body.password : "";
  const expectedRole = normalizeRole(body.role);

  if (!email || !password) {
    return jsonError("Vui lòng nhập email và mật khẩu.", 400);
  }

  const tokenParams = new URLSearchParams({
    grant_type: "password",
    client_id: KEYCLOAK_CLIENT_ID,
    username: email,
    password,
  });
  if (KEYCLOAK_CLIENT_SECRET) {
    tokenParams.set("client_secret", KEYCLOAK_CLIENT_SECRET);
  }

  const tokenUrl = `${KEYCLOAK_URL.replace(/\/$/, "")}/realms/${encodeURIComponent(
    KEYCLOAK_REALM,
  )}/protocol/openid-connect/token`;

  let tokenRes: Response;
  try {
    tokenRes = await fetch(tokenUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: tokenParams,
      cache: "no-store",
    });
  } catch {
    return jsonError("Không kết nối được dịch vụ xác thực AMINRA.", 502);
  }

  const tokenBody = (await tokenRes.json().catch(() => ({}))) as TokenResponse;
  if (!tokenRes.ok || !tokenBody.access_token) {
    return jsonError(userMessageForKeycloakError(tokenBody), tokenRes.status === 401 ? 401 : 502);
  }

  let profileRes: Response;
  try {
    profileRes = await fetch(`${BACKEND.replace(/\/$/, "")}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenBody.access_token}` },
      cache: "no-store",
    });
  } catch {
    return jsonError("Không kết nối được backend AMINRA sau khi xác thực.", 502);
  }

  const profile = await profileRes.json().catch(() => null);
  if (!profileRes.ok || !profile) {
    return jsonError("Không tải được hồ sơ ứng dụng sau khi xác thực.", profileRes.status || 502);
  }

  if (expectedRole && profile.role !== expectedRole) {
    return jsonError(
      expectedRole === "business"
        ? "Tài khoản này không thuộc cổng doanh nghiệp."
        : "Tài khoản này không thuộc cổng tổ chức chứng nhận.",
      403,
    );
  }

  return NextResponse.json({ access_token: tokenBody.access_token, user: profile });
}
