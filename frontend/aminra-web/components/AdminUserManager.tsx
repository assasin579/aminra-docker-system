"use client";

import { useState, useEffect, useCallback } from "react";

const API = "/api";

interface User {
  id: string;
  email: string;
  keycloak_sub: string | null;
  identity_source?: "keycloak" | string;
  identity_status: "linked" | "missing_in_keycloak" | "disabled_in_keycloak" | "unknown";
  keycloak_deleted_at: string | null;
  role: "business" | "provider";
  company_name: string;
  company_code: string | null;
  status: "active" | "pending" | "suspended";
  is_owner: boolean;
  tenant_id: string | null;
  created_at: string;
}

const STATUS_CFG = {
  active: { label: "Hoạt động", bg: "rgba(10,31,68,0.1)", color: "#0A1F44" },
  pending: { label: "Chờ duyệt", bg: "rgba(245,158,11,0.1)", color: "#F59E0B" },
  suspended: { label: "Đình chỉ", bg: "rgba(239,68,68,0.1)", color: "#f87171" },
};
const ROLE_CFG = {
  business: { label: "Doanh nghiệp", color: "#0A1F44" },
  provider: { label: "Tổ chức", color: "#0EA5E9" },
};
const IDENTITY_STATUS_CFG = {
  linked: { label: "Keycloak linked", bg: "rgba(16,185,129,0.1)", color: "#047857" },
  missing_in_keycloak: { label: "Keycloak missing", bg: "rgba(239,68,68,0.1)", color: "#991B1B" },
  disabled_in_keycloak: { label: "Keycloak disabled", bg: "rgba(245,158,11,0.1)", color: "#B45309" },
  unknown: { label: "Keycloak unknown", bg: "rgba(100,116,139,0.1)", color: "#475569" },
};

type DeleteImpact = {
  user: User;
  impact: Record<string, number>;
  cleanup_options?: Array<{
    key: string;
    label: string;
    count: number;
    action: string;
    enabled: boolean;
    warning: string;
  }>;
  risk_level: "none" | "medium" | "high" | string;
  hard_delete_safe: boolean;
  deletion_warnings: string[];
  recommended_action: string;
};

type RelatedReferenceCleanup = {
  selected_references: string[];
  cleanup: Record<string, Record<string, unknown>>;
  users_projection_deleted: boolean;
  documents_db_rows_deleted: boolean;
  safe_next_step: string;
};

type AccountDeletionCaseItem = {
  reference_key: string;
  label: string;
  action: string;
  record_count: number;
  status: string;
  risk_level?: string;
  reason?: string;
};

type AccountDeletionCaseResponse = {
  case: {
    id: string;
    status: string;
    risk_level: string;
    confirmation_phrase: string;
  };
  items?: AccountDeletionCaseItem[];
  result?: {
    case_status: string;
    completed_items: number;
    skipped_items: number;
    blocked_items: number;
    failed_items?: number;
  };
};

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return "Hôm nay";
  if (d === 1) return "Hôm qua";
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
}

function keycloakUsersUrl() {
  const base = process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "https://auth.aminra.org";
  const realm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "aminra";
  return `${base.replace(/\/$/, "")}/admin/master/console/#/${encodeURIComponent(realm)}/users`;
}

export default function AdminUserManager({ token }: { token: string }) {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [impactLoadingId, setImpactLoadingId] = useState<string | null>(null);
  const [deleteImpact, setDeleteImpact] = useState<DeleteImpact | null>(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<RelatedReferenceCleanup | null>(null);
  const [selectedReferences, setSelectedReferences] = useState<string[]>([]);
  const [deletionCaseLoading, setDeletionCaseLoading] = useState(false);
  const [deletionCase, setDeletionCase] = useState<AccountDeletionCaseResponse | null>(null);
  const [deletionCaseMessage, setDeletionCaseMessage] = useState("");

  const [filterRole, setFilterRole] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [search, setSearch] = useState("");

  const authHdr = { Authorization: `Bearer ${token}` };
  const keycloakUrl = keycloakUsersUrl();

  const fetchUsers = useCallback(async () => {
    setFetching(true);
    setFetchError("");
    try {
      const params = new URLSearchParams();
      if (filterRole) params.set("role", filterRole);
      if (filterStatus) params.set("status", filterStatus);
      if (search) params.set("q", search);
      const res = await fetch(`${API}/admin/users?${params}`, {
        headers: authHdr,
      });
      if (!res.ok) {
        setFetchError(`Không tải được danh sách projection (HTTP ${res.status})`);
        return;
      }
      const d = await res.json();
      setUsers(d.users);
      setTotal(d.total);
    } finally {
      setFetching(false);
    }
  }, [filterRole, filterStatus, search, token]);

  const loadDeleteImpact = useCallback(async (user: User) => {
    setImpactLoadingId(user.id);
    setFetchError("");
    setDeleteImpact(null);
    setCleanupResult(null);
    setDeletionCase(null);
    setDeletionCaseMessage("");
    setSelectedReferences([]);
    try {
      const res = await fetch(`${API}/admin/users/${user.id}/delete-impact`, {
        headers: authHdr,
      });
      if (!res.ok) {
        let detail = "";
        try {
          const err = await res.json();
          detail = typeof err?.detail === "string" ? `: ${err.detail}` : "";
        } catch {
          detail = "";
        }
        setFetchError(`Không tải được cảnh báo xóa Keycloak (HTTP ${res.status})${detail}`);
        return;
      }
      setDeleteImpact(await res.json());
    } catch (error) {
      setFetchError(
        `Không tải được cảnh báo xóa Keycloak: ${error instanceof Error ? error.message : "lỗi mạng không xác định"}`,
      );
    } finally {
      setImpactLoadingId(null);
    }
  }, [token]);

  const cleanupSelectedReferences = useCallback(async () => {
    if (!deleteImpact || selectedReferences.length === 0) return;
    setCleanupLoading(true);
    setFetchError("");
    setCleanupResult(null);
    try {
      const res = await fetch(`${API}/admin/users/${deleteImpact.user.id}/related-references/cleanup`, {
        method: "POST",
        headers: { ...authHdr, "Content-Type": "application/json" },
        body: JSON.stringify({ selected_references: selectedReferences }),
      });
      if (!res.ok) {
        let detail = "";
        try {
          const err = await res.json();
          detail = typeof err?.detail === "string" ? `: ${err.detail}` : "";
        } catch {
          detail = "";
        }
        setFetchError(`Không xóa được reference đã chọn (HTTP ${res.status})${detail}`);
        return;
      }
      setCleanupResult(await res.json());
    } catch (error) {
      setFetchError(
        `Không xóa được reference đã chọn: ${error instanceof Error ? error.message : "lỗi mạng không xác định"}`,
      );
    } finally {
      setCleanupLoading(false);
    }
  }, [deleteImpact, selectedReferences, token]);

  const createDeletionCase = useCallback(async () => {
    if (!deleteImpact) return;
    setDeletionCaseLoading(true);
    setFetchError("");
    setDeletionCaseMessage("");
    try {
      const res = await fetch(`${API}/admin/users/${deleteImpact.user.id}/deletion-case`, {
        method: "POST",
        headers: { ...authHdr, "Content-Type": "application/json" },
      });
      if (!res.ok) {
        let detail = "";
        try {
          const err = await res.json();
          detail = typeof err?.detail === "string" ? `: ${err.detail}` : "";
        } catch {
          detail = "";
        }
        setFetchError(`Không tạo được hồ sơ cleanup an toàn (HTTP ${res.status})${detail}`);
        return;
      }
      setDeletionCase(await res.json());
    } catch (error) {
      setFetchError(
        `Không tạo được hồ sơ cleanup an toàn: ${error instanceof Error ? error.message : "lỗi mạng không xác định"}`,
      );
    } finally {
      setDeletionCaseLoading(false);
    }
  }, [deleteImpact, token]);

  const runDeletionCase = useCallback(async () => {
    if (!deletionCase) return;
    setDeletionCaseLoading(true);
    setFetchError("");
    setDeletionCaseMessage("");
    try {
      const res = await fetch(`${API}/admin/account-deletion-cases/${deletionCase.case.id}/run`, {
        method: "POST",
        headers: { ...authHdr, "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation_phrase: deletionCase.case.confirmation_phrase }),
      });
      if (!res.ok) {
        let detail = "";
        try {
          const err = await res.json();
          detail = typeof err?.detail === "string" ? `: ${err.detail}` : "";
        } catch {
          detail = "";
        }
        setFetchError(`Không chạy được hồ sơ cleanup an toàn (HTTP ${res.status})${detail}`);
        return;
      }
      const payload = await res.json();
      setDeletionCase((current) => ({
        ...payload,
        items: payload?.items ?? current?.items ?? [],
        result: payload?.result,
      }));
      const result = payload?.result;
      setDeletionCaseMessage(
        result
          ? `Cleanup an toàn đã chạy: status=${result.case_status}; completed=${result.completed_items}; skipped=${result.skipped_items}; blocked=${result.blocked_items}; failed=${result.failed_items ?? 0}`
          : `Cleanup an toàn đã chạy: status=${payload?.case?.status ?? "updated"}`,
      );
      await fetchUsers();
    } catch (error) {
      setFetchError(
        `Không chạy được hồ sơ cleanup an toàn: ${error instanceof Error ? error.message : "lỗi mạng không xác định"}`,
      );
    } finally {
      setDeletionCaseLoading(false);
    }
  }, [deletionCase, fetchUsers, token]);

  const toggleSelectedReference = useCallback((key: string) => {
    setSelectedReferences((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }, []);

  const cleanupOptions = deleteImpact?.cleanup_options ?? [];
  const selectableCleanupOptions = cleanupOptions.filter((option) => option.enabled);
  const lockedCleanupOptions = cleanupOptions.filter((option) => !option.enabled);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  return (
    <div data-identity-owner="keycloak">
      <div
        className="mb-5 rounded-2xl p-4"
        style={{
          background: "rgba(14,165,233,0.08)",
          border: "1px solid rgba(14,165,233,0.22)",
          color: "#0A1F44",
        }}
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <p className="text-sm font-semibold">
              Keycloak là nơi duy nhất quản lý user/account
            </p>
            <p className="mt-1 text-xs leading-relaxed" style={{ color: "#475569" }}>
              AMINRA Admin chỉ hiển thị projection đọc từ app DB để audit nghiệp vụ.
              Tạo/xoá/vô hiệu hoá user, reset mật khẩu, xác minh email, role và
              sửa identity phải thực hiện trong Keycloak Admin Console.
            </p>
          </div>
          <a
            href={keycloakUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-grid place-items-center rounded-xl px-4 py-2 text-sm font-semibold text-white"
            style={{ background: "#0A1F44" }}
          >
            Open in Keycloak
          </a>
        </div>
      </div>

      {/* Toolbar */}
      <div
        className="grid items-center mb-5 gap-3"
        style={{ gridTemplateColumns: "1fr auto" }}
      >
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(12rem, auto))",
          }}
        >
          <input
            type="text"
            placeholder="Tìm email, tên..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          />
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          >
            <option value="">Tất cả loại</option>
            <option value="business">Doanh nghiệp</option>
            <option value="provider">Tổ chức</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          >
            <option value="">Tất cả trạng thái projection</option>
            <option value="active">Hoạt động</option>
            <option value="pending">Chờ duyệt</option>
            <option value="suspended">Đình chỉ</option>
          </select>
        </div>
        <button
          onClick={fetchUsers}
          className="rounded-xl px-4 py-2 text-sm font-medium"
          style={{ background: "#F5F1E8", color: "#0A1F44", border: "1px solid #E2E8F0" }}
        >
          Làm mới
        </button>
      </div>

      {fetchError && (
        <div
          role="alert"
          className="mb-4 rounded-xl px-4 py-3 text-sm"
          style={{ background: "rgba(239,68,68,0.08)", color: "#991B1B" }}
        >
          {fetchError}
        </div>
      )}

      {deleteImpact && (
        <div
          role="status"
          aria-live="polite"
          className="mb-4 rounded-xl p-4 text-sm"
          style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)", color: "#0A1F44" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-semibold">Cảnh báo trước khi xóa Keycloak account</p>
              <p className="mt-1 text-xs font-medium" style={{ color: "#0A1F44" }}>
                {deleteImpact.user.email}
              </p>
              <p className="text-xs mt-1" style={{ color: "#6B7280" }}>
                Risk: {deleteImpact.risk_level} · hard_delete_safe={String(deleteImpact.hard_delete_safe)} · recommended_action={deleteImpact.recommended_action}
              </p>
            </div>
            <button
              onClick={() => setDeleteImpact(null)}
              className="rounded-lg px-3 py-1 text-xs font-semibold"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", color: "#0A1F44" }}
            >
              Đóng
            </button>
          </div>
          {deleteImpact.deletion_warnings.length > 0 ? (
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs" style={{ color: "#7C2D12" }}>
              {deleteImpact.deletion_warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-xs" style={{ color: "#047857" }}>
              Không tìm thấy dữ liệu nghiệp vụ liên quan; projection có thể được purge sau khi xóa Keycloak nếu admin xác nhận.
            </p>
          )}

          <div
            className="mt-4 rounded-xl p-3"
            style={{ background: "rgba(255,255,255,0.75)", border: "1px solid rgba(245,158,11,0.22)" }}
          >
            <p className="text-xs font-semibold" style={{ color: "#0A1F44" }}>
              Dọn reference liên quan tới account đã bị xóa khỏi Keycloak
            </p>
            <p className="mt-1 text-xs leading-relaxed" style={{ color: "#475569" }}>
              Không tự động xóa hàng loạt. Admin phải chọn từng checkbox; users projection và business/audit records mặc định được giữ lại.
            </p>
            {cleanupOptions.length > 0 ? (
              <div className="mt-3 space-y-3">
                {selectableCleanupOptions.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "#047857" }}>
                      Có thể chọn để cleanup nhanh
                    </p>
                    {selectableCleanupOptions.map((option) => (
                      <label
                        key={option.key}
                        className="flex items-start gap-2 rounded-lg p-2 text-xs"
                        style={{ background: "rgba(255,255,255,0.85)", color: "#0A1F44" }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedReferences.includes(option.key)}
                          disabled={cleanupLoading}
                          onChange={() => toggleSelectedReference(option.key)}
                        />
                        <span>
                          <span className="font-semibold">{option.label}</span> · {option.count} record(s) · {option.action}
                          <span className="block mt-0.5">{option.warning}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-lg px-3 py-2 text-xs" style={{ background: "rgba(14,165,233,0.08)", color: "#0A1F44", border: "1px solid rgba(14,165,233,0.18)" }}>
                    Không có reference nào đủ điều kiện cleanup nhanh cho projection này. Các dòng bên dưới là audit/business record hoặc chưa đạt điều kiện an toàn nên không có checkbox để xóa.
                  </p>
                )}

                {lockedCleanupOptions.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "#7C2D12" }}>
                      Giữ lại / cần quy trình riêng
                    </p>
                    {lockedCleanupOptions.map((option) => (
                      <div
                        key={option.key}
                        className="rounded-lg p-2 text-xs"
                        style={{ background: "rgba(148,163,184,0.08)", color: "#64748B", border: "1px solid rgba(148,163,184,0.18)" }}
                      >
                        <span className="font-semibold">{option.label}</span> · {option.count} record(s) · {option.action}
                        <span className="ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold" style={{ background: "rgba(124,45,18,0.10)", color: "#7C2D12" }}>
                          Không xóa nhanh
                        </span>
                        <span className="block mt-0.5">{option.warning}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-3 text-xs" style={{ color: "#047857" }}>
                Không có reference có thể cleanup bằng thao tác nhanh.
              </p>
            )}
            <button
              onClick={cleanupSelectedReferences}
              disabled={cleanupLoading || selectedReferences.length === 0}
              className="mt-3 rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={{ background: "#991B1B", color: "#FFFFFF", opacity: cleanupLoading || selectedReferences.length === 0 ? 0.55 : 1 }}
            >
              {cleanupLoading ? "Đang xóa reference đã chọn..." : "Xóa reference đã chọn"}
            </button>
          </div>

          {cleanupResult && (
            <div
              className="mt-3 rounded-xl px-3 py-2 text-xs"
              style={{ background: "rgba(16,185,129,0.10)", color: "#047857", border: "1px solid rgba(16,185,129,0.22)" }}
            >
              <p className="font-semibold">
                Đã dọn {cleanupResult.selected_references.length} nhóm reference · users_projection_deleted={String(cleanupResult.users_projection_deleted)} · documents_db_rows_deleted={String(cleanupResult.documents_db_rows_deleted)}
              </p>
              <p className="mt-1">Selected: {cleanupResult.selected_references.join(", ")}</p>
              <p className="mt-1">{cleanupResult.safe_next_step}</p>
            </div>
          )}

          {lockedCleanupOptions.length > 0 && (
            <div
              className="mt-4 rounded-xl p-3 text-xs"
              style={{ background: "rgba(14,165,233,0.08)", border: "1px solid rgba(14,165,233,0.22)", color: "#0A1F44" }}
            >
              <p className="font-semibold">Quy trình riêng cho reference quan trọng</p>
              <p className="mt-1 leading-relaxed" style={{ color: "#475569" }}>
                Tạo hồ sơ cleanup an toàn để hệ thống dry-run policy, giữ audit log append-only, detach reference nullable, và ghi evidence cho từng bước. Không xóa users projection hoặc document DB rows bằng luồng này.
              </p>
              <button
                onClick={createDeletionCase}
                disabled={deletionCaseLoading}
                className="mt-3 rounded-lg px-3 py-1.5 text-xs font-semibold"
                style={{ background: "#0A1F44", color: "#FFFFFF", opacity: deletionCaseLoading ? 0.65 : 1 }}
              >
                {deletionCaseLoading ? "Đang xử lý hồ sơ..." : "Tạo hồ sơ xử lý an toàn"}
              </button>

              {deletionCase && (
                <div
                  className="mt-3 rounded-lg p-3"
                  style={{ background: "rgba(255,255,255,0.82)", border: "1px solid rgba(14,165,233,0.18)" }}
                >
                  <p className="font-semibold">
                    Hồ sơ cleanup: {deletionCase.case.id} · status={deletionCase.case.status} · risk={deletionCase.case.risk_level}
                  </p>
                  <p className="mt-1 font-mono" style={{ color: "#7C2D12" }}>
                    {deletionCase.case.confirmation_phrase}
                  </p>
                  {deletionCase.items && deletionCase.items.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {deletionCase.items.map((item) => (
                        <li key={`${item.reference_key}-${item.action}`}>
                          <span className="font-semibold">{item.label}</span> · {item.record_count} record(s) · {item.action} · {item.status}
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    onClick={runDeletionCase}
                    disabled={deletionCaseLoading || deletionCase.case.status === "completed"}
                    className="mt-3 rounded-lg px-3 py-1.5 text-xs font-semibold"
                    style={{ background: "#047857", color: "#FFFFFF", opacity: deletionCaseLoading || deletionCase.case.status === "completed" ? 0.65 : 1 }}
                  >
                    {deletionCaseLoading ? "Đang chạy cleanup..." : "Chạy cleanup an toàn"}
                  </button>
                  {deletionCase.result && (
                    <p className="mt-2" style={{ color: "#047857" }}>
                      completed={deletionCase.result.completed_items} · skipped={deletionCase.result.skipped_items} · blocked={deletionCase.result.blocked_items} · failed={deletionCase.result.failed_items ?? 0}
                    </p>
                  )}
                  {deletionCaseMessage && <p className="mt-2 font-semibold" style={{ color: "#047857" }}>{deletionCaseMessage}</p>}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: "1px solid #E2E8F0", background: "#FFFFFF" }}
      >
        {fetching ? (
          <div className="divide-y" style={{ borderColor: "#E2E8F0" }}>
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="px-4 py-4 flex items-center gap-4">
                <div className="flex-1 space-y-2">
                  <div className="shimmer skeleton-text w-48" />
                  <div className="shimmer skeleton-text w-32" />
                </div>
                <div className="shimmer skeleton-text w-20" />
                <div className="shimmer skeleton-text w-16" />
              </div>
            ))}
          </div>
        ) : users.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <svg
              className="w-12 h-12 mx-auto mb-3"
              fill="none"
              stroke="#CBD5E1"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
            <p className="font-medium text-sm" style={{ color: "#0A1F44" }}>
              Không có projection nào
            </p>
            <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
              {filterRole || filterStatus || search
                ? "Thử bỏ bớt filter"
                : "User/account phải được tạo trong Keycloak trước"}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead style={{ background: "#F5F1E8" }}>
              <tr>
                {["Email / Tên", "Loại", "Trạng thái projection", "Keycloak", "Ngày tạo", "Preflight"].map(
                  (h) => (
                    <th
                      key={h}
                      className="text-left px-4 py-3 text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => {
                const st = STATUS_CFG[u.status] ?? STATUS_CFG.active;
                const rl = ROLE_CFG[u.role] ?? ROLE_CFG.business;
                const identity = IDENTITY_STATUS_CFG[u.identity_status] ?? IDENTITY_STATUS_CFG.unknown;
                return (
                  <tr
                    key={u.id}
                    style={{
                      background: i % 2 === 0 ? "#FFFFFF" : "#FFFFFF",
                      borderTop: "1px solid #E2E8F0",
                    }}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium" style={{ color: "#0A1F44" }}>
                        {u.email}
                      </p>
                      <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                        {u.company_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-medium" style={{ color: rl.color }}>
                        {rl.label}
                      </span>
                      {!u.is_owner && (
                        <span className="ml-1 text-xs" style={{ color: "#94A3B8" }}>
                          · thành viên
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium"
                        style={{ background: identity.bg, color: identity.color }}
                      >
                        {identity.label}
                      </span>
                      <p className="text-[11px] font-mono mt-1" style={{ color: "#94A3B8" }}>
                        {u.keycloak_sub ?? "projection-only"}
                      </p>
                      {u.keycloak_deleted_at && (
                        <p className="text-[11px] mt-0.5" style={{ color: "#991B1B" }}>
                          deleted {timeAgo(u.keycloak_deleted_at)}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: "#6B7280" }}>
                      {timeAgo(u.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => loadDeleteImpact(u)}
                        disabled={impactLoadingId === u.id}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold"
                        style={{ background: "#F5F1E8", color: "#0A1F44", border: "1px solid #E2E8F0" }}
                      >
                        {impactLoadingId === u.id ? "Đang kiểm tra..." : "Đánh giá trước khi xóa"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs mt-2" style={{ color: "#6B7280" }}>
        {total} projection · identity_source=keycloak
      </p>
    </div>
  );
}
