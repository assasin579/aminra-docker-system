/**
 * Client-side API helpers for Tier-1 #24 Document Version Control.
 *
 * Pairs with backend endpoints in `auth/document_router.py` (commit 7e8ed6a).
 * All calls return parsed JSON or throw with the backend's detail message.
 *
 * Closed-default: when feature flag is OFF, backend returns 404 → callers
 * should handle gracefully (treat as "feature not available").
 */

export type ApprovalStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "obsolete";

export interface ApprovalBlock {
  approval_status: ApprovalStatus;
  version_number: number;
  version_parent_id: string | null;
  approver_id: string | null;
  approver_email?: string;
  approver_name?: string;
  approved_at: string | null;
  effective_date: string | null;
  next_review_date: string | null;
  retention_period_days: number;
  retention_expires_at: string | null;
  superseded_by_id: string | null;
  is_obsolete: boolean;
}

export interface VersionEntry {
  id: string;
  version_number: number;
  approval_status: ApprovalStatus;
  approved_at: string | null;
  effective_date: string | null;
}

export interface ApprovalRequest {
  effective_date?: string; // ISO date "YYYY-MM-DD"
  next_review_date?: string;
  retention_period_days?: number;
}

class DocVersioningError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function call<T>(
  method: string,
  path: string,
  token: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/api${path}`, {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = await res.json();
      detail = json?.detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new DocVersioningError(detail, res.status);
  }
  // Some endpoints return empty body; handle gracefully
  const text = await res.text();
  return (text ? JSON.parse(text) : {}) as T;
}

/** Submit a draft document for approval (state: draft → pending_approval). */
export async function submitForApproval(
  docId: string,
  token: string,
): Promise<{ message: string; approval_status: ApprovalStatus }> {
  return call("POST", `/documents/${docId}/submit-for-approval`, token);
}

/** Approve a pending document (state: pending_approval → approved). */
export async function approveDocument(
  docId: string,
  body: ApprovalRequest,
  token: string,
): Promise<{
  message: string;
  approval_status: ApprovalStatus;
  effective_date: string;
  next_review_date: string;
}> {
  return call("POST", `/documents/${docId}/approve`, token, body);
}

/** Reject a pending document with reason (state: pending_approval → draft). */
export async function rejectDocument(
  docId: string,
  reason: string,
  token: string,
): Promise<{ message: string; approval_status: ApprovalStatus }> {
  return call("POST", `/documents/${docId}/reject`, token, { reason });
}

/** Mark a doc obsolete + link new version (state: approved → obsolete). */
export async function supersedeDocument(
  oldDocId: string,
  newDocumentId: string,
  token: string,
): Promise<{
  message: string;
  old_document_id: string;
  new_document_id: string;
  new_version_number: number;
}> {
  return call("POST", `/documents/${oldDocId}/supersede`, token, {
    new_document_id: newDocumentId,
  });
}

/** Full version chain (parents + descendants), bounded by MAX_CHAIN_DEPTH. */
export async function getVersions(
  docId: string,
  token: string,
): Promise<{ doc_id: string; versions: VersionEntry[]; max_depth: number }> {
  return call("GET", `/documents/${docId}/versions`, token);
}

/** Read-only approval status snapshot. */
export async function getApprovalStatus(
  docId: string,
  token: string,
): Promise<ApprovalBlock> {
  return call("GET", `/documents/${docId}/approval-status`, token);
}

/** Localized status label for UI badges. */
export function approvalStatusLabel(status: ApprovalStatus): string {
  switch (status) {
    case "draft":
      return "Bản nháp";
    case "pending_approval":
      return "Chờ duyệt";
    case "approved":
      return "Đã phê duyệt";
    case "obsolete":
      return "Đã thay thế";
  }
}

/** Tailwind+navy palette colors per status. */
export function approvalStatusColors(status: ApprovalStatus): {
  bg: string;
  border: string;
  text: string;
} {
  switch (status) {
    case "draft":
      return {
        bg: "rgba(100,116,139,0.10)",
        border: "rgba(100,116,139,0.25)",
        text: "#475569",
      };
    case "pending_approval":
      return {
        bg: "rgba(245,158,11,0.12)",
        border: "rgba(245,158,11,0.3)",
        text: "#B45309",
      };
    case "approved":
      return {
        bg: "rgba(16,42,92,0.10)",
        border: "rgba(16,42,92,0.30)",
        text: "#102A5C",
      };
    case "obsolete":
      return {
        bg: "rgba(148,163,184,0.10)",
        border: "rgba(148,163,184,0.30)",
        text: "#64748B",
      };
  }
}
