import { parseApiError } from "@/lib/apiError";

export class ApiClientError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.body = body;
  }
}

type ApiRequestOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  json?: unknown;
  body?: BodyInit | null;
  fallbackError?: string;
};

async function parseErrorBody(res: Response): Promise<unknown> {
  const clone = res.clone();
  const jsonBody = await clone.json().catch(() => undefined);
  if (jsonBody !== undefined) return jsonBody;

  const text = await res.text().catch(() => "");
  return text ? { detail: text } : {};
}

/**
 * Authenticated frontend-proxy API request.
 *
 * All non-GET write actions should go through this wrapper instead of raw fetch
 * so FastAPI error arrays/objects are normalized and non-2xx responses cannot
 * be mistaken for success.
 */
export async function apiFetch(path: string, options: ApiRequestOptions = {}): Promise<Response> {
  const { token, json, fallbackError, headers, ...init } = options;
  const mergedHeaders = new Headers(headers);
  if (token) mergedHeaders.set("Authorization", `Bearer ${token}`);
  if (json !== undefined && !mergedHeaders.has("Content-Type")) {
    mergedHeaders.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: mergedHeaders,
      body: json !== undefined ? JSON.stringify(json) : init.body,
    });
  } catch {
    throw new ApiClientError(
      fallbackError || "Không thể kết nối backend. Kiểm tra đăng nhập/mạng rồi thử lại.",
      0,
      null,
    );
  }

  if (!res.ok) {
    const body = await parseErrorBody(res);
    throw new ApiClientError(
      parseApiError(body, fallbackError || `API thất bại (HTTP ${res.status})`),
      res.status,
      body,
    );
  }

  return res;
}

export async function apiJson<T = unknown>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const res = await apiFetch(path, options);
  return res.json() as Promise<T>;
}
