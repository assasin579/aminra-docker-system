/**
 * Authenticated fetch wrapper for AMINRA backend.
 * On 401, fires `onUnauthorized` so the auth context can sign-out + redirect.
 */
import { API_BASE } from './auth';

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function authedFetch(path: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...((init.headers as Record<string, string>) ?? {}),
  };
  if (init.body && typeof init.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) onUnauthorized();
  return res;
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  const r = await authedFetch(path, token);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new ApiError(r.status, body.detail ?? `HTTP ${r.status}`);
  }
  return (await r.json()) as T;
}

export async function apiPost<T>(path: string, token: string, body: unknown): Promise<T> {
  const r = await authedFetch(path, token, { method: 'POST', body: JSON.stringify(body) });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new ApiError(r.status, j.detail ?? `HTTP ${r.status}`);
  }
  return (await r.json()) as T;
}

export async function apiPut<T>(path: string, token: string, body: unknown): Promise<T> {
  const r = await authedFetch(path, token, { method: 'PUT', body: JSON.stringify(body) });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new ApiError(r.status, j.detail ?? `HTTP ${r.status}`);
  }
  return (await r.json()) as T;
}

// ── Domain endpoints ────────────────────────────────────────────────────────

export type AuditVisit = {
  id: string;
  business_tenant: string;
  business_name?: string | null;
  provider_id: string;
  auditor_id: string | null;
  visit_type: string;
  status: 'scheduled' | 'in_progress' | 'completed' | 'report_submitted';
  scheduled_date: string;
  location?: string | null;
  notes?: string | null;
  compliance_score?: number | null;
};

export type ChecklistItem = {
  id: string;
  visit_id: string;
  category: string;
  criteria: string;
  severity: 'minor' | 'major' | 'critical';
  status: 'pending' | 'pass' | 'fail' | 'na';
  notes?: string | null;
};

export const Visits = {
  list: (token: string) => apiGet<{ visits: AuditVisit[] }>(`/api/audits/`, token),
  get:  (token: string, id: string) => apiGet<AuditVisit>(`/api/audits/visits/${id}`, token),
  updateStatus: (token: string, id: string, status: AuditVisit['status']) =>
    apiPost(`/api/audits/visits/${id}/status`, token, { status }),
  listItems: (token: string, id: string) =>
    apiGet<{ items: ChecklistItem[] }>(`/api/audits/visits/${id}/items`, token),
  updateItem: (token: string, vid: string, itemId: string, patch: Partial<ChecklistItem>) =>
    apiPut(`/api/audits/visits/${vid}/items/${itemId}`, token, patch),
};

// Multipart photo / signature upload helper.
// `localUri` is e.g. file:///.../IMG_1234.jpg from expo-image-manipulator/camera.
async function uploadFile(path: string, token: string, localUri: string, fieldName = 'file'): Promise<{ ok: true } | { ok: false; status: number; detail: string }> {
  const form = new FormData();
  // RN FormData accepts {uri, name, type} objects
  form.append(fieldName, {
    uri:  localUri,
    name: localUri.split('/').pop() ?? 'photo.jpg',
    type: 'image/jpeg',
  } as unknown as Blob);
  const r = await fetch(`${API_BASE}${path}`, {
    method:  'POST',
    headers: { Authorization: `Bearer ${token}` },
    body:    form as unknown as BodyInit,
  });
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    return { ok: false, status: r.status, detail: j.detail ?? `HTTP ${r.status}` };
  }
  return { ok: true };
}

export const Photos = {
  uploadForItem: (token: string, vid: string, itemId: string, uri: string) =>
    uploadFile(`/api/audits/${vid}/items/${itemId}/photo`, token, uri),
};

export const Signatures = {
  uploadAuditor: (token: string, vid: string, uri: string) =>
    uploadFile(`/api/audits/${vid}/signature?type=auditor`, token, uri),
  uploadBusiness: (token: string, vid: string, uri: string) =>
    uploadFile(`/api/audits/${vid}/signature?type=business`, token, uri),
};
