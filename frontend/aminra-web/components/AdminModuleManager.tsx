"use client";

import { useCallback, useMemo, useState } from "react";
import { apiJson } from "@/lib/apiClient";

type ModuleStatus = "enabled" | "trial" | "disabled" | "locked";

interface TenantModule {
  code: string;
  name_vi?: string | null;
  name_en?: string | null;
  category?: string | null;
  status: ModuleStatus;
  required?: boolean;
  default_enabled?: boolean;
  display_order?: number;
  config?: Record<string, unknown>;
  source?: string | null;
  access_label_vi?: string | null;
}

interface TenantModulesPayload {
  business_model?: {
    code?: string | null;
    name_vi?: string | null;
    name_en?: string | null;
  } | null;
  modules: TenantModule[];
}

interface ActivationRequest {
  id: string;
  tenant_id: string;
  module_code: string;
  module_name_vi?: string | null;
  status: "pending" | "approved" | "rejected" | "cancelled";
  requester_email?: string | null;
  route_path?: string | null;
  message?: string | null;
}

interface ActivationRequestsPayload {
  requests: ActivationRequest[];
}

const STATUSES: ModuleStatus[] = ["enabled", "trial", "disabled", "locked"];

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Thao tác module thất bại.";
}

function moduleLabel(module: TenantModule): string {
  return module.name_vi || module.name_en || module.code;
}

function configPreview(config?: Record<string, unknown>): string {
  if (!config || Object.keys(config).length === 0) return "{}";
  return JSON.stringify(config);
}

export default function AdminModuleManager({ token }: { token: string }) {
  const [tenantId, setTenantId] = useState("");
  const [payload, setPayload] = useState<TenantModulesPayload | null>(null);
  const [activationRequests, setActivationRequests] = useState<ActivationRequest[]>([]);
  const [draftStatuses, setDraftStatuses] = useState<Record<string, ModuleStatus>>({});
  const [loading, setLoading] = useState(false);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [savingCode, setSavingCode] = useState<string | null>(null);
  const [reviewingRequestId, setReviewingRequestId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const normalizedTenantId = tenantId.trim();

  const sortedModules = useMemo(() => {
    return [...(payload?.modules || [])].sort(
      (a, b) => (a.display_order || 0) - (b.display_order || 0) || a.code.localeCompare(b.code),
    );
  }, [payload]);

  const refreshModules = useCallback(async () => {
    const refreshed = await apiJson<TenantModulesPayload>(
      `/api/auth/admin/tenants/${encodeURIComponent(normalizedTenantId)}/modules`,
      {
        token,
        fallbackError: "Không tải được module của tenant.",
      },
    );
    setPayload(refreshed);
    setDraftStatuses(
      Object.fromEntries((refreshed.modules || []).map((item) => [item.code, item.status])),
    );
  }, [normalizedTenantId, token]);

  const loadModules = useCallback(async () => {
    if (!normalizedTenantId) {
      setError("Nhập tenant ID trước khi tải module.");
      return;
    }
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      await refreshModules();
    } catch (err) {
      setError(errorMessage(err));
      setPayload(null);
      setDraftStatuses({});
    } finally {
      setLoading(false);
    }
  }, [normalizedTenantId, refreshModules]);

  const loadActivationRequests = useCallback(async () => {
    if (!normalizedTenantId) {
      setError("Nhập tenant ID trước khi tải yêu cầu kích hoạt.");
      return;
    }
    setLoadingRequests(true);
    setError(null);
    try {
      const data = await apiJson<ActivationRequestsPayload>(
        `/api/auth/admin/module-activation-requests?tenant_id=${encodeURIComponent(normalizedTenantId)}&status=pending`,
        {
          token,
          fallbackError: "Không tải được yêu cầu kích hoạt.",
        },
      );
      setActivationRequests(data.requests || []);
    } catch (err) {
      setError(errorMessage(err));
      setActivationRequests([]);
    } finally {
      setLoadingRequests(false);
    }
  }, [normalizedTenantId, token]);

  const saveModule = useCallback(
    async (module: TenantModule) => {
      if (!normalizedTenantId) {
        setError("Nhập tenant ID trước khi lưu module.");
        return;
      }
      const nextStatus = draftStatuses[module.code] || module.status;
      setSavingCode(module.code);
      setError(null);
      setNotice(null);
      try {
        await apiJson(`/api/auth/admin/tenants/${encodeURIComponent(normalizedTenantId)}/modules/${module.code}`, {
          method: "PATCH",
          token,
          json: { status: nextStatus, config: module.config || {} },
          fallbackError: `Không cập nhật được module ${module.code}.`,
        });
        setNotice(`Đã cập nhật ${module.code} → ${nextStatus}`);
        await refreshModules();
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setSavingCode(null);
      }
    },
    [draftStatuses, normalizedTenantId, refreshModules, token],
  );

  const reviewRequest = useCallback(
    async (request: ActivationRequest, action: "approve" | "reject") => {
      setReviewingRequestId(request.id);
      setError(null);
      setNotice(null);
      try {
        await apiJson(`/api/auth/admin/module-activation-requests/${request.id}`, {
          method: "PATCH",
          token,
          json: {
            action,
            admin_note: action === "approve" ? "Approved from Tenant module console" : "Rejected from Tenant module console",
          },
          fallbackError: "Không xử lý được yêu cầu kích hoạt.",
        });
        setNotice(`${action === "approve" ? "Đã duyệt" : "Đã từ chối"} yêu cầu ${request.module_code}`);
        await loadActivationRequests();
        if (action === "approve") await refreshModules();
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setReviewingRequestId(null);
      }
    },
    [loadActivationRequests, refreshModules, token],
  );

  return (
    <section className="space-y-5" data-admin-module-console="true">
      <div>
        <h2 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
          Tenant module console
        </h2>
        <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
          Bật/tắt module theo tenant qua backend entitlement API. Backend vẫn enforce dependency blockers; UI không giả lập thành công.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(16rem,1fr)_auto_auto] items-end">
        <label className="grid gap-1 text-sm font-medium" style={{ color: "#334155" }}>
          Tenant ID
          <input
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
            placeholder="vd: tenant UUID"
            className="rounded-xl px-3 py-2 text-sm"
            style={{ border: "1px solid #CBD5E1", color: "#0A1F44" }}
          />
        </label>
        <button
          type="button"
          onClick={() => void loadModules()}
          disabled={loading}
          className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
          style={{ background: "#0A1F44", color: "white" }}
        >
          {loading ? "Đang tải..." : "Tải module"}
        </button>
        <button
          type="button"
          onClick={() => void loadActivationRequests()}
          disabled={loadingRequests}
          className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
          style={{ background: "#7C3AED", color: "white" }}
        >
          {loadingRequests ? "Đang tải..." : "Tải yêu cầu kích hoạt"}
        </button>
      </div>

      {error && (
        <div role="alert" className="rounded-xl p-3 text-sm" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="rounded-xl p-3 text-sm" style={{ background: "#ECFDF5", color: "#047857", border: "1px solid #A7F3D0" }}>
          {notice}
        </div>
      )}

      {activationRequests.length > 0 && (
        <section data-module-activation-requests="true" className="rounded-2xl p-4 space-y-3" style={{ background: "#FAF5FF", border: "1px solid #DDD6FE" }}>
          <h3 className="font-semibold" style={{ color: "#4C1D95" }}>Yêu cầu kích hoạt đang chờ</h3>
          {activationRequests.map((request) => (
            <div key={request.id} className="rounded-xl p-3 grid gap-3 md:grid-cols-[1fr_auto_auto] md:items-center" style={{ background: "white", border: "1px solid #E9D5FF" }}>
              <div className="text-sm" style={{ color: "#334155" }}>
                <strong>{request.module_name_vi || request.module_code}</strong> <code>{request.module_code}</code>
                <p>{request.message || "Không có ghi chú"}</p>
                <p className="text-xs" style={{ color: "#64748B" }}>Requester: {request.requester_email || "unknown"} · Route: {request.route_path || "n/a"}</p>
              </div>
              <button
                type="button"
                onClick={() => void reviewRequest(request, "approve")}
                disabled={reviewingRequestId === request.id}
                className="px-3 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
                style={{ background: "#0F766E", color: "white" }}
              >
                Duyệt {request.module_code}
              </button>
              <button
                type="button"
                onClick={() => void reviewRequest(request, "reject")}
                disabled={reviewingRequestId === request.id}
                className="px-3 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
                style={{ background: "#B91C1C", color: "white" }}
              >
                Từ chối {request.module_code}
              </button>
            </div>
          ))}
        </section>
      )}

      {payload?.business_model && (
        <div className="rounded-xl p-3 text-sm" style={{ background: "#F8FAFC", color: "#334155", border: "1px solid #E2E8F0" }}>
          Business model: <strong>{payload.business_model.name_vi || payload.business_model.name_en || payload.business_model.code}</strong>
        </div>
      )}

      {sortedModules.length > 0 && (
        <div className="grid gap-3">
          {sortedModules.map((module) => (
            <div
              key={module.code}
              className="rounded-2xl p-4 grid gap-4 md:grid-cols-[1fr_auto_auto] md:items-center"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold" style={{ color: "#0A1F44" }}>{moduleLabel(module)}</h3>
                  <code className="text-xs px-2 py-1 rounded-lg" style={{ background: "#F1F5F9", color: "#475569" }}>{module.code}</code>
                  {module.required && <span className="text-xs px-2 py-1 rounded-lg" style={{ background: "#FEF3C7", color: "#92400E" }}>required</span>}
                  {module.default_enabled && <span className="text-xs px-2 py-1 rounded-lg" style={{ background: "#E0F2FE", color: "#075985" }}>default</span>}
                </div>
                <p className="text-xs mt-2" style={{ color: "#64748B" }}>
                  Category: {module.category || "uncategorized"} · Source: {module.source || "unknown"} · Access: {module.access_label_vi || module.status} · Config: {configPreview(module.config)}
                </p>
              </div>

              <label className="grid gap-1 text-xs font-medium" style={{ color: "#475569" }}>
                Status
                <select
                  data-testid={`module-status-${module.code}`}
                  value={draftStatuses[module.code] || module.status}
                  onChange={(event) =>
                    setDraftStatuses((current) => ({
                      ...current,
                      [module.code]: event.target.value as ModuleStatus,
                    }))
                  }
                  className="rounded-xl px-3 py-2 text-sm"
                  style={{ border: "1px solid #CBD5E1", color: "#0A1F44" }}
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </label>

              <button
                type="button"
                onClick={() => void saveModule(module)}
                disabled={savingCode === module.code}
                className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-60"
                style={{ background: "#0F766E", color: "white" }}
              >
                {savingCode === module.code ? "Đang lưu..." : `Lưu ${module.code}`}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
