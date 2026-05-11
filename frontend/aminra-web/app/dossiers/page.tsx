"use client";

/**
 * Dossier list page — show all tenant's hồ sơ với standard + status.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";

interface DossierListItem {
  id: string;
  title: string;
  status: string;
  standard_code: string | null;
  standard_name_vi: string | null;
  doc_types: Array<{ doc_type: string; required: boolean }>;
  documents?: Array<{ id: string }>;
  created_at: string;
  updated_at: string;
}

const STATUS_LABEL: Record<string, { vi: string; color: string }> = {
  draft: { vi: "Bản nháp", color: "#6B7280" },
  in_progress: { vi: "Đang chuẩn bị", color: "#0A1F44" },
  submitted: { vi: "Đã nộp", color: "#0891B2" },
  cert_issued: { vi: "Đã cấp cert", color: "#16A34A" },
  cancelled: { vi: "Đã hủy", color: "#DC2626" },
};

export default function DossierListPage() {
  const router = useRouter();
  const { token, isAuthenticated, user, loading: authLoading } = useUserAuth();
  const [dossiers, setDossiers] = useState<DossierListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !token) {
      router.replace("/business/login");
      return;
    }
    if (user?.role === "business" && user.is_owner && !user.industry_schema_id) {
      router.replace("/business/onboarding/industry-select");
      return;
    }

    (async () => {
      try {
        const res = await fetch("/api/dossiers", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setDossiers(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không tải được danh sách");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, user, router]);

  if (loading || authLoading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" style={{ color: "#6B7280" }}>Đang tải...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "#FFFFFF" }}>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
              Hồ sơ chứng nhận
            </h1>
            <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
              Mỗi hồ sơ thuộc 1 tiêu chuẩn cụ thể. Trong tiêu chuẩn quy định
              số lượng và loại tài liệu cần có.
            </p>
          </div>
          <Link
            href="/dossiers/new"
            className="px-4 py-2.5 rounded-xl font-semibold text-sm text-white btn-lift"
            style={{ background: "#0A1F44" }}
            data-testid="dossier-create-cta"
          >
            + Tạo hồ sơ mới
          </Link>
        </div>

        {error && (
          <div
            className="rounded-lg px-4 py-3 text-xs mb-4"
            style={{
              background: "rgba(239,68,68,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            {error}
          </div>
        )}

        {dossiers.length === 0 ? (
          <div
            className="rounded-2xl p-12 text-center"
            style={{
              background: "rgba(10,31,68,0.04)",
              border: "1px dashed #E2E8F0",
            }}
          >
            <div className="text-5xl mb-4">📂</div>
            <p className="text-sm mb-4" style={{ color: "#6B7280" }}>
              Chưa có hồ sơ nào. Tạo hồ sơ đầu tiên để bắt đầu chuẩn bị tài
              liệu theo tiêu chuẩn.
            </p>
            <Link
              href="/dossiers/new"
              className="inline-block px-5 py-2.5 rounded-xl font-semibold text-sm text-white"
              style={{ background: "#0A1F44" }}
            >
              Tạo hồ sơ đầu tiên
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {dossiers.map((d) => {
              const st = STATUS_LABEL[d.status] ?? { vi: d.status, color: "#6B7280" };
              return (
                <Link
                  key={d.id}
                  href={`/dossiers/${d.id}`}
                  className="block rounded-2xl p-5 hover:shadow-md transition-shadow"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                  }}
                  data-testid={`dossier-row-${d.id}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-base font-semibold mb-1 truncate"
                        style={{ color: "#0A1F44" }}
                      >
                        {d.title}
                      </div>
                      {d.standard_name_vi && (
                        <div className="text-xs" style={{ color: "#6B7280" }}>
                          Tiêu chuẩn:{" "}
                          <strong>{d.standard_name_vi.split(" — ")[0]}</strong>
                          {" · "}
                          {d.doc_types.length} loại tài liệu yêu cầu
                        </div>
                      )}
                      <div className="text-[11px] mt-2" style={{ color: "#94A3B8" }}>
                        Cập nhật:{" "}
                        {new Date(d.updated_at).toLocaleDateString("vi-VN", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })}
                      </div>
                    </div>
                    <span
                      className="text-[11px] font-semibold px-2.5 py-1 rounded-full whitespace-nowrap"
                      style={{
                        background: `${st.color}15`,
                        color: st.color,
                      }}
                    >
                      {st.vi}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
