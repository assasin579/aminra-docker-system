"use client";

/**
 * Business onboarding — industry select (TASK #19 Phase 1).
 *
 * Tenant owner chọn industry schema 1 lần khi onboarding. Phase 1 có
 * 3 schema enabled (food_manufacturing / restaurant_hotel /
 * livestock_slaughter). Sau khi chọn, lock cho đến khi cert đầu tiên
 * issued (admin override required for switch).
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";

interface IndustrySchema {
  id: string;
  code: string;
  name_vi: string;
  name_en: string | null;
  description: string | null;
  jakim_scheme: string | null;
  icon: string | null;
  enabled: boolean;
  doc_types: Array<{ doc_type: string; required: boolean; display_order: number }>;
}

// Icon mapping — emoji fallback since component library yet to standardize
const ICON_MAP: Record<string, string> = {
  factory: "🏭",
  restaurant: "🏨",
  cow: "🐄",
  pharmacy: "💊",
  cosmetic: "💄",
  truck: "🚛",
};

export default function IndustrySelectPage() {
  const router = useRouter();
  const { token, user, refreshProfile } = useUserAuth();
  const [schemas, setSchemas] = useState<IndustrySchema[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      router.replace("/business/login");
      return;
    }
    (async () => {
      try {
        const res = await fetch("/api/industry-schemas", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: IndustrySchema[] = await res.json();
        // Backend already filters enabled=true, but defensive sort by display_order
        setSchemas(data.sort((a, b) => (a.id > b.id ? 1 : -1)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không tải được danh sách ngành");
      } finally {
        setLoading(false);
      }
    })();
  }, [token, router]);

  const handleSelect = async () => {
    if (!selected || !token) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/industry-schemas/business-select", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ schema_id: selected }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        // 409 = already assigned (e.g. retry after partial success).
        // Still refresh profile + redirect — assignment did stick.
        if (res.status !== 409) {
          throw new Error(body.detail || `HTTP ${res.status}`);
        }
      }
      // Refresh /auth/me so dashboard guard sees the new industry_schema_id.
      // Without this, dashboard reads stale localStorage profile → loop back.
      await refreshProfile();
      router.replace("/dashboard/business");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không lưu được lựa chọn");
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" style={{ color: "#6B7280" }}>
          Đang tải danh sách ngành nghề...
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl mx-auto py-12 px-6" data-page>
      <div className="text-center mb-10">
        <h1 className="text-2xl font-bold mb-2" style={{ color: "#0A1F44" }}>
          Chọn ngành nghề doanh nghiệp
        </h1>
        <p className="text-sm" style={{ color: "#6B7280" }}>
          Doanh nghiệp của bạn thuộc nhóm nào? Chọn để AMINRA tạo bộ tài liệu
          chuẩn theo ngành.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {schemas.map((s) => {
          const isSelected = selected === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => setSelected(s.id)}
              className="text-left rounded-2xl p-6 transition-all"
              style={{
                background: isSelected ? "#0A1F44" : "#FFFFFF",
                color: isSelected ? "#FFFFFF" : "#0A1F44",
                border: isSelected
                  ? "2px solid #0A1F44"
                  : "1px solid #E2E8F0",
                boxShadow: isSelected
                  ? "0 8px 24px rgba(10,31,68,0.18)"
                  : "0 2px 8px rgba(0,0,0,0.04)",
                cursor: "pointer",
              }}
              data-testid={`industry-card-${s.code}`}
            >
              <div className="text-4xl mb-3">{ICON_MAP[s.icon ?? ""] ?? "📋"}</div>
              <h3 className="text-base font-semibold mb-2">{s.name_vi}</h3>
              {s.description && (
                <p
                  className="text-xs mb-3"
                  style={{ color: isSelected ? "#E2E8F0" : "#6B7280" }}
                >
                  {s.description}
                </p>
              )}
              {s.jakim_scheme && (
                <p
                  className="text-[11px]"
                  style={{ color: isSelected ? "#94A3B8" : "#94A3B8" }}
                >
                  Chuẩn: <strong>{s.jakim_scheme}</strong>
                </p>
              )}
              <p
                className="text-[11px] mt-2"
                style={{ color: isSelected ? "#94A3B8" : "#94A3B8" }}
              >
                {s.doc_types.length} loại tài liệu chuẩn
              </p>
            </button>
          );
        })}
      </div>

      <div
        className="rounded-xl p-4 mb-6 text-xs"
        style={{
          background: "rgba(10,31,68,0.04)",
          border: "1px solid #E2E8F0",
          color: "#6B7280",
        }}
      >
        ⚠️ <strong>Chỉ chọn 1 nhóm</strong> — không thể đổi sau khi cert đầu tiên
        đã issue. Nếu cần đổi, liên hệ AMINRA admin với lý do chính đáng (sẽ ghi
        vào audit log).
      </div>

      {error && (
        <p
          className="text-xs mb-4 px-3 py-2 rounded-lg"
          style={{
            background: "rgba(239,68,68,0.1)",
            color: "#ef4444",
            border: "1px solid rgba(239,68,68,0.2)",
          }}
        >
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSelect}
          disabled={!selected || submitting}
          className="btn-lift py-3 px-8 rounded-xl font-semibold text-sm"
          style={{
            background: !selected || submitting ? "#E2E8F0" : "#0A1F44",
            color: !selected || submitting ? "#6B7280" : "white",
            cursor: !selected || submitting ? "not-allowed" : "pointer",
          }}
          data-testid="industry-confirm-button"
        >
          {submitting ? "Đang lưu..." : "Tiếp tục"}
        </button>
      </div>
    </div>
  );
}
