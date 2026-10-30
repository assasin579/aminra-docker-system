"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiJson } from "@/lib/apiClient";
import { useUserAuth } from "./UserAuthContext";

type ModuleStatus = "enabled" | "trial" | "disabled" | "locked";

type TenantModule = {
  code: string;
  name_vi?: string | null;
  name_en?: string | null;
  category?: string | null;
  status: ModuleStatus;
  required?: boolean;
  default_enabled?: boolean;
  source?: string | null;
  access_state?: "active" | "trial" | "locked" | "disabled" | string;
  access_label_vi?: string | null;
  locked_reason?: string | null;
  cta_label_vi?: string | null;
  route_path?: string | null;
};

type TenantModulesPayload = {
  business_model?: {
    code?: string | null;
    name_vi?: string | null;
    name_en?: string | null;
  } | null;
  modules: TenantModule[];
};

const STATUS_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  active: { bg: "#ECFDF5", color: "#047857", border: "#A7F3D0" },
  trial: { bg: "#EFF6FF", color: "#1D4ED8", border: "#BFDBFE" },
  locked: { bg: "#FEF2F2", color: "#B91C1C", border: "#FECACA" },
  disabled: { bg: "#F8FAFC", color: "#475569", border: "#CBD5E1" },
};

function moduleLabel(module: TenantModule): string {
  return module.name_vi || module.name_en || module.code;
}

function businessModelLabel(payload: TenantModulesPayload | null): string {
  const model = payload?.business_model;
  return model?.name_vi || model?.name_en || model?.code || "Chưa xác định";
}

function normalizeAccessState(module: TenantModule): string {
  if (module.access_state) return module.access_state;
  if (module.status === "enabled") return "active";
  if (module.status === "trial") return "trial";
  return module.status;
}

function fallbackAccessLabel(module: TenantModule): string {
  if (module.access_label_vi) return module.access_label_vi;
  const state = normalizeAccessState(module);
  if (state === "active") return "Đang hoạt động";
  if (state === "trial") return "Đang dùng thử";
  if (state === "locked") return "Đang khóa";
  return "Chưa kích hoạt";
}

function sourceLabel(source?: string | null): string {
  if (source === "admin_override") return "Admin override";
  if (source === "business_model_default") return "Theo gói ngành";
  return source || "Nguồn chưa rõ";
}

export default function MyModulesPanel() {
  const { token, isAuthenticated, user } = useUserAuth();
  const [payload, setPayload] = useState<TenantModulesPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      setPayload(null);
      setError("Vui lòng đăng nhập để xem gói module.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    apiJson<TenantModulesPayload>("/api/api/me/modules", {
      token,
      fallbackError: "Không tải được gói module của doanh nghiệp.",
    })
      .then((data) => {
        if (!cancelled) setPayload(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Không tải được gói module của doanh nghiệp.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, token]);

  const modules = useMemo(() => payload?.modules || [], [payload]);
  const activeCount = modules.filter((module) => ["enabled", "trial"].includes(module.status)).length;

  if (error) {
    return (
      <section className="rounded-2xl p-6" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}>
        <div role="alert" className="rounded-xl p-4 text-sm" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
          {error}
        </div>
      </section>
    );
  }

  return (
    <section data-my-modules-panel="true" className="space-y-6">
      <div className="rounded-3xl p-6" style={{ background: "linear-gradient(135deg, #0A1F44 0%, #0F766E 100%)", color: "white" }}>
        <p className="text-sm uppercase tracking-[0.2em] opacity-80">AMINRA modules</p>
        <h1 className="text-3xl font-bold mt-2">Gói module của tôi</h1>
        <p className="mt-2 opacity-90">
          {user?.company_name || "Doanh nghiệp"} · Business model: <strong>{businessModelLabel(payload)}</strong>
        </p>
        <p className="mt-4 text-sm opacity-90">
          {loading ? "Đang tải gói module..." : `${activeCount}/${modules.length} module đang hoạt động hoặc dùng thử.`}
        </p>
      </div>

      {loading && <p className="text-sm" style={{ color: "#64748B" }}>Đang tải gói module...</p>}

      {!loading && modules.length === 0 && (
        <div className="rounded-2xl p-6" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", color: "#475569" }}>
          Chưa có module nào được provision cho tenant này. Vui lòng liên hệ AMINRA operator.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {modules.map((module) => {
          const state = normalizeAccessState(module);
          const style = STATUS_STYLE[state] || STATUS_STYLE.disabled;
          const label = moduleLabel(module);
          const active = ["enabled", "trial"].includes(module.status);
          return (
            <article key={module.code} className="rounded-2xl p-5 space-y-4" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-bold text-lg" style={{ color: "#0A1F44" }}>{label}</h2>
                <span className="text-xs px-2 py-1 rounded-full" style={{ background: style.bg, color: style.color, border: `1px solid ${style.border}` }}>
                  {fallbackAccessLabel(module)}
                </span>
                {module.required && <span className="text-xs px-2 py-1 rounded-full" style={{ background: "#FEF3C7", color: "#92400E" }}>Bắt buộc</span>}
                {module.default_enabled && <span className="text-xs px-2 py-1 rounded-full" style={{ background: "#E0F2FE", color: "#075985" }}>Mặc định</span>}
              </div>

              <dl className="grid grid-cols-2 gap-3 text-sm" style={{ color: "#475569" }}>
                <div>
                  <dt className="font-medium">Mã module</dt>
                  <dd><code>{module.code}</code></dd>
                </div>
                <div>
                  <dt className="font-medium">Nguồn</dt>
                  <dd>{sourceLabel(module.source)}</dd>
                </div>
              </dl>

              {!active && (
                <p className="text-sm" style={{ color: "#64748B" }}>
                  {module.locked_reason || "Module này chưa được kích hoạt trong gói hiện tại."}
                </p>
              )}

              <div>
                {active && module.route_path ? (
                  <Link href={module.route_path} className="inline-flex px-4 py-2 rounded-xl text-sm font-semibold" style={{ background: "#0F766E", color: "white" }}>
                    Mở {label}
                  </Link>
                ) : (
                  <button type="button" disabled className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-70" style={{ background: "#E2E8F0", color: "#475569" }}>
                    {(module.cta_label_vi || "Yêu cầu kích hoạt") + ` ${label}`}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
