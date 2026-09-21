"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { apiJson } from "@/lib/apiClient";
import { useUserAuth } from "./UserAuthContext";

type ModuleStatus = "enabled" | "trial" | "disabled" | "locked";

type TenantModule = {
  code: string;
  name_vi?: string | null;
  name_en?: string | null;
  status: ModuleStatus;
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

type Props = {
  moduleCode: string;
  routePath: string;
  children: ReactNode;
};

function moduleLabel(tenantModule?: TenantModule | null, fallback?: string): string {
  return tenantModule?.name_vi || tenantModule?.name_en || tenantModule?.code || fallback || "Module";
}

function normalizeAccessState(tenantModule?: TenantModule | null): string {
  if (!tenantModule) return "locked";
  if (tenantModule.access_state) return tenantModule.access_state;
  if (tenantModule.status === "enabled") return "active";
  if (tenantModule.status === "trial") return "trial";
  return tenantModule.status;
}

function isModuleActive(tenantModule?: TenantModule | null): boolean {
  const state = normalizeAccessState(tenantModule);
  return tenantModule?.status === "enabled" || tenantModule?.status === "trial" || state === "active" || state === "trial";
}

function LockedModuleScreen({ tenantModule, moduleCode, routePath }: { tenantModule?: TenantModule | null; moduleCode: string; routePath: string }) {
  const label = moduleLabel(tenantModule, moduleCode);
  const reason = tenantModule?.locked_reason || "Module này chưa được kích hoạt trong gói hiện tại.";
  const accessLabel = tenantModule?.access_label_vi || (normalizeAccessState(tenantModule) === "locked" ? "Đang khóa" : "Chưa kích hoạt");
  const cta = tenantModule?.cta_label_vi || "Yêu cầu kích hoạt";

  return (
    <main
      data-module-access-gate="locked"
      data-module-code={moduleCode}
      data-route-path={routePath}
      className="min-h-[70vh] p-6 grid place-items-center"
      style={{ background: "#F8FAFC" }}
    >
      <section className="w-full max-w-3xl rounded-3xl p-8 space-y-6" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", boxShadow: "0 20px 60px rgba(15, 23, 42, 0.08)" }}>
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex px-3 py-1 rounded-full text-sm font-semibold" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
            {accessLabel}
          </span>
          <code className="text-xs px-2 py-1 rounded-lg" style={{ background: "#F1F5F9", color: "#475569" }}>{moduleCode}</code>
        </div>

        <div>
          <p className="text-sm uppercase tracking-[0.2em] font-semibold" style={{ color: "#0F766E" }}>AMINRA module access</p>
          <h1 className="text-3xl font-bold mt-2" style={{ color: "#0A1F44" }}>Module chưa kích hoạt</h1>
          <p className="text-lg mt-3" style={{ color: "#334155" }}>{label}</p>
          <p className="mt-3" style={{ color: "#64748B" }}>{reason}</p>
        </div>

        <div className="rounded-2xl p-4 text-sm" style={{ background: "#F8FAFC", color: "#475569", border: "1px solid #E2E8F0" }}>
          Đường dẫn trực tiếp <code>{routePath}</code> đã được chặn ở lớp trải nghiệm người dùng. API backend vẫn fail-closed cho module chưa được cấp quyền.
        </div>

        <div className="flex flex-wrap gap-3">
          <Link href="/modules" className="inline-flex px-4 py-2 rounded-xl text-sm font-semibold" style={{ background: "#0F766E", color: "white" }}>
            Xem gói module của tôi
          </Link>
          <button type="button" disabled className="px-4 py-2 rounded-xl text-sm font-semibold disabled:opacity-70" style={{ background: "#E2E8F0", color: "#475569" }}>
            {cta} {label}
          </button>
        </div>
      </section>
    </main>
  );
}

export default function ModuleAccessGate({ moduleCode, routePath, children }: Props) {
  const { token, isAuthenticated } = useUserAuth();
  const [payload, setPayload] = useState<TenantModulesPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      setPayload(null);
      setError("Vui lòng đăng nhập để truy cập module.");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    apiJson<TenantModulesPayload>("/api/api/me/modules", {
      token,
      fallbackError: "Không kiểm tra được quyền truy cập module.",
    })
      .then((data) => {
        if (!cancelled) setPayload(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Không kiểm tra được quyền truy cập module.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, moduleCode, routePath, token]);

  const tenantModule = useMemo(() => payload?.modules.find((item) => item.code === moduleCode), [moduleCode, payload]);

  if (error) {
    return (
      <main className="min-h-[60vh] p-6 grid place-items-center" style={{ background: "#F8FAFC" }}>
        <section className="w-full max-w-2xl rounded-2xl p-6" style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}>
          <div role="alert" className="rounded-xl p-4 text-sm" style={{ background: "#FEF2F2", color: "#B91C1C", border: "1px solid #FECACA" }}>
            {error}
          </div>
        </section>
      </main>
    );
  }

  if (loading || !payload) {
    return (
      <main className="min-h-[60vh] grid place-items-center" data-module-access-gate="loading">
        <div className="space-y-3 text-center">
          <div className="mx-auto w-8 h-8 border-2 border-[#0A1F44] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm" style={{ color: "#64748B" }}>Đang kiểm tra quyền truy cập module...</p>
        </div>
      </main>
    );
  }

  if (!isModuleActive(tenantModule)) {
    return <LockedModuleScreen tenantModule={tenantModule} moduleCode={moduleCode} routePath={routePath} />;
  }

  return <>{children}</>;
}
