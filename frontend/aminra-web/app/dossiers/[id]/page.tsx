"use client";

/**
 * Dossier detail — info + standard + doc_types required + uploaded documents.
 */

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";

interface DocTypeReq {
  doc_type: string;
  required: boolean;
  display_order: number;
}

interface DocumentInDossier {
  id: string;
  doc_type: string | null;
  filename: string;
  original_filename: string;
  status: string | null;
  compliance_score: number | null;
  version_number: number;
  uploaded_at: string;
}

interface DossierDetail {
  id: string;
  title: string;
  status: string;
  notes: string | null;
  standard_code: string | null;
  standard_name_vi: string | null;
  doc_types: DocTypeReq[];
  documents: DocumentInDossier[];
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

const DOC_TYPE_LABEL_VI: Record<string, string> = {
  company_profile: "Hồ sơ năng lực công ty",
  halal_policy: "Chính sách Halal",
  has_manual: "Sổ tay HAS / Halal Manual",
  internal_halal_committee: "Quyết định thành lập IHC",
  ingredient_raw_material: "Danh mục nguyên vật liệu",
  process_flow_chart: "Lưu đồ quy trình sản xuất",
  sop_personal_hygiene: "SOP — Vệ sinh cá nhân",
  sop_cleaning_sanitation: "SOP — Vệ sinh cơ sở",
  sop_pest_control: "SOP — Kiểm soát côn trùng",
  sop_supplier_evaluation: "SOP — Đánh giá nhà cung cấp",
  sop_traceability: "SOP — Truy xuất nguồn gốc",
  sop_complaint_handling: "SOP — Xử lý khiếu nại",
  generic: "Tài liệu khác",
};

export default function DossierDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const { id } = use(params);
  const { token, isAuthenticated, loading: authLoading } = useUserAuth();
  const [dossier, setDossier] = useState<DossierDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !token) {
      router.replace("/business/login");
      return;
    }
    (async () => {
      try {
        const res = await fetch(`/api/dossiers/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setDossier(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không tải được hồ sơ");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, id, router]);

  if (loading || authLoading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" style={{ color: "#6B7280" }}>Đang tải...</p>
      </div>
    );
  }

  if (error || !dossier) {
    return (
      <div className="min-h-screen grid place-items-center px-6">
        <div className="text-center">
          <p
            className="text-sm mb-4 px-4 py-3 rounded-lg"
            style={{
              background: "rgba(239,68,68,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            {error || "Không tìm thấy hồ sơ"}
          </p>
          <Link
            href="/dossiers"
            className="inline-block px-5 py-2.5 rounded-xl text-sm text-white"
            style={{ background: "#0A1F44" }}
          >
            Quay lại danh sách
          </Link>
        </div>
      </div>
    );
  }

  const st = STATUS_LABEL[dossier.status] ?? { vi: dossier.status, color: "#6B7280" };
  const uploadedDocTypes = new Set(
    dossier.documents.filter((d) => d.doc_type).map((d) => d.doc_type),
  );
  const completed = dossier.doc_types.filter((dt) =>
    uploadedDocTypes.has(dt.doc_type),
  ).length;

  return (
    <div className="min-h-screen" style={{ background: "#FFFFFF" }}>
      <div className="max-w-4xl mx-auto px-6 py-8">
        <Link href="/dossiers" className="text-xs" style={{ color: "#6B7280" }}>
          ← Danh sách hồ sơ
        </Link>

        <div className="mt-3 mb-6 flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h1
              className="text-xl font-bold truncate"
              style={{ color: "#0A1F44" }}
            >
              {dossier.title}
            </h1>
            {dossier.standard_name_vi && (
              <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
                Tiêu chuẩn: <strong>{dossier.standard_name_vi}</strong>
              </p>
            )}
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

        {/* Progress */}
        <div
          className="rounded-2xl p-5 mb-6"
          style={{ background: "rgba(10,31,68,0.04)", border: "1px solid #E2E8F0" }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
              Tiến độ tài liệu
            </span>
            <span className="text-sm" style={{ color: "#6B7280" }}>
              {completed}/{dossier.doc_types.length} loại đã có tài liệu
            </span>
          </div>
          <div
            className="h-2 rounded-full overflow-hidden"
            style={{ background: "#E2E8F0" }}
          >
            <div
              className="h-full transition-all"
              style={{
                width: `${(completed / Math.max(dossier.doc_types.length, 1)) * 100}%`,
                background: "#0A1F44",
              }}
            />
          </div>
        </div>

        {/* Required doc_types */}
        <div className="mb-6">
          <h2
            className="text-sm font-semibold mb-3"
            style={{ color: "#0A1F44" }}
          >
            Tài liệu cần chuẩn bị
          </h2>
          <div className="space-y-2">
            {dossier.doc_types.map((dt) => {
              const matching = dossier.documents.filter(
                (d) => d.doc_type === dt.doc_type,
              );
              const done = matching.length > 0;
              return (
                <div
                  key={dt.doc_type}
                  className="rounded-xl p-4 flex items-start gap-3"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                  }}
                  data-testid={`doc-type-row-${dt.doc_type}`}
                >
                  <div className="text-xl leading-none">
                    {done ? "✅" : "⬜"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-sm font-medium"
                      style={{ color: "#0A1F44" }}
                    >
                      {DOC_TYPE_LABEL_VI[dt.doc_type] ?? dt.doc_type}
                      {dt.required && (
                        <span className="text-[11px] ml-2" style={{ color: "#DC2626" }}>
                          *bắt buộc
                        </span>
                      )}
                    </div>
                    {done ? (
                      <div className="text-xs mt-1" style={{ color: "#6B7280" }}>
                        {matching.length} file đã upload — version {matching[0].version_number}
                      </div>
                    ) : (
                      <div className="text-xs mt-1" style={{ color: "#94A3B8" }}>
                        Chưa có tài liệu
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3">
          <Link
            href={`/create-document?dossier=${dossier.id}`}
            className="flex-1 text-center px-5 py-2.5 rounded-xl font-semibold text-sm"
            style={{
              background: "rgba(10,31,68,0.1)",
              color: "#0A1F44",
              border: "1px solid rgba(10,31,68,0.2)",
            }}
            data-testid="dossier-create-doc-cta"
          >
            ✦ Tạo tài liệu từ mẫu
          </Link>
          <Link
            href={`/documents?dossier=${dossier.id}`}
            className="flex-1 text-center px-5 py-2.5 rounded-xl font-semibold text-sm text-white"
            style={{ background: "#0A1F44" }}
            data-testid="dossier-upload-doc-cta"
          >
            ↑ Upload tài liệu
          </Link>
        </div>

        {dossier.notes && (
          <div className="mt-6">
            <h3 className="text-xs font-semibold mb-2" style={{ color: "#6B7280" }}>
              GHI CHÚ
            </h3>
            <p
              className="text-sm rounded-lg p-3"
              style={{ background: "#F9FAFB", color: "#374151" }}
            >
              {dossier.notes}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
