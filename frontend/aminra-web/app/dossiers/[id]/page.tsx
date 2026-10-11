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

interface ReadinessItem {
  id?: string;
  code?: string;
  title?: string;
  label?: string;
  doc_type?: string;
  filename?: string;
  reason?: string;
  description?: string;
  deadline?: string | null;
  severity?: string;
}

interface DossierReadiness {
  state?: string;
  readiness_percent: number;
  certificate_issue_blocked: boolean;
  safe_public_trace_available: boolean;
  next_action: string | null;
  next_actor_role: string | null;
  next_action_owner_role?: string | null;
  due_date?: string | null;
  required_documents: Array<string | ReadinessItem>;
  missing_required_documents: Array<string | ReadinessItem>;
  unreviewed_documents: ReadinessItem[];
  rejected_documents: ReadinessItem[];
  open_ncrs: ReadinessItem[];
  blocking_ncrs?: ReadinessItem[];
  certification_decision: unknown | null;
  certificate: unknown | null;
  blocking_reasons: Array<string | ReadinessItem>;
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

function readinessItemLabel(item: string | ReadinessItem): string {
  if (typeof item === "string") return DOC_TYPE_LABEL_VI[item] ?? item;
  return item.label || item.title || item.filename || item.description || (item.doc_type ? (DOC_TYPE_LABEL_VI[item.doc_type] ?? item.doc_type) : null) || item.code || item.id || "Mục cần xử lý";
}

function readinessDocDetail(item: ReadinessItem): string | null {
  const parts = [item.filename, item.reason].filter(Boolean);
  return parts.length ? parts.join(" — ") : null;
}

const NEXT_ACTION_LABEL: Record<string, string> = {
  configure_required_documents: "Cấu hình danh mục tài liệu bắt buộc",
  upload_required_documents: "Tải lên tài liệu bắt buộc",
  replace_rejected_documents: "Thay thế tài liệu bị từ chối",
  review_uploaded_documents: "Chờ đơn vị chứng nhận xem xét tài liệu",
  submit_capa_evidence: "Gửi bằng chứng khắc phục (CAPA)",
  verify_capa_evidence: "Chờ xác minh bằng chứng CAPA",
  finalize_certification_decision: "Hoàn tất quyết định chứng nhận",
  certification_ready: "Hồ sơ sẵn sàng chứng nhận",
  issue_certificate_artifact: "Phát hành chứng thư chính thức",
};

const ACTOR_ROLE_LABEL: Record<string, string> = {
  business: "Doanh nghiệp",
  business_owner: "Doanh nghiệp",
  reviewer: "Chuyên viên thẩm định",
  provider: "Đơn vị chứng nhận",
  auditor: "Chuyên gia đánh giá",
  decision_maker: "Người ra quyết định chứng nhận",
  admin: "Quản trị viên",
  platform_admin: "Quản trị nền tảng",
};

const DOSSIER_STATE_LABEL: Record<string, string> = {
  requirements_unconfigured: "Chưa cấu hình checklist",
  requirements_pending: "Còn thiếu hồ sơ",
  documents_rejected: "Cần sửa tài liệu bị từ chối",
  documents_in_review: "Tài liệu đang được thẩm định",
  ncr_open: "Còn điểm không phù hợp cần khắc phục",
  capa_in_review: "CAPA đang được xác minh",
  ready_for_decision: "Sẵn sàng ra quyết định",
  certificate_pending: "Đã duyệt — chờ phát hành chứng thư",
  certified: "Đã chứng nhận",
};

const BLOCKER_LABEL: Record<string, string> = {
  required_document_checklist_unconfigured: "Quản trị viên cần cấu hình checklist cho tiêu chuẩn này.",
  active_certificate_missing: "Quyết định đã được duyệt nhưng chưa có chứng thư đang hiệu lực.",
  missing_required_document: "Thiếu tài liệu bắt buộc",
  rejected_document: "Tài liệu bắt buộc cần được sửa và nộp lại",
  document_not_approved: "Tài liệu bắt buộc chưa được thẩm định/chấp thuận",
  open_ncr: "Cần đóng điểm không phù hợp trước khi ra quyết định",
  certification_decision_not_approved: "Chưa có quyết định chứng nhận được phê duyệt",
};

function safeBlockerLabel(item: string | ReadinessItem): string {
  if (typeof item === "string") return item;
  if (item.code && BLOCKER_LABEL[item.code]) return BLOCKER_LABEL[item.code];
  return [item.title, item.label, item.reason, item.doc_type ? (DOC_TYPE_LABEL_VI[item.doc_type] ?? item.doc_type) : null]
    .filter((part): part is string => typeof part === "string" && part.length > 0)
    .join(" — ") || "Mục cần xử lý";
}

function isReadinessItem(value: unknown): value is ReadinessItem {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  const textFields = ["id", "code", "title", "label", "doc_type", "filename", "reason", "description", "severity"];
  if (textFields.some((field) => item[field] !== undefined && typeof item[field] !== "string")) return false;
  return item.deadline === undefined
    || item.deadline === null
    || (typeof item.deadline === "string" && Number.isFinite(new Date(item.deadline).getTime()));
}

function isReadinessItemList(value: unknown): value is ReadinessItem[] {
  return Array.isArray(value) && value.every(isReadinessItem);
}

function isReadinessItemOrLabelList(value: unknown): value is Array<string | ReadinessItem> {
  return Array.isArray(value) && value.every((item) => typeof item === "string" || isReadinessItem(item));
}

function isDossierReadiness(value: unknown): value is DossierReadiness {
  if (!value || typeof value !== "object") return false;
  const payload = value as Record<string, unknown>;
  const percent = payload.readiness_percent;
  const dueDate = payload.due_date;

  return typeof percent === "number"
    && Number.isFinite(percent)
    && percent >= 0
    && percent <= 100
    && typeof payload.certificate_issue_blocked === "boolean"
    && typeof payload.safe_public_trace_available === "boolean"
    && (payload.next_action === null || typeof payload.next_action === "string")
    && (payload.next_actor_role === null || typeof payload.next_actor_role === "string")
    && (payload.state === undefined || typeof payload.state === "string")
    && (payload.next_action_owner_role === undefined || payload.next_action_owner_role === null || typeof payload.next_action_owner_role === "string")
    && (dueDate === undefined || dueDate === null || (typeof dueDate === "string" && Number.isFinite(new Date(dueDate).getTime())))
    && isReadinessItemOrLabelList(payload.required_documents)
    && isReadinessItemOrLabelList(payload.missing_required_documents)
    && isReadinessItemList(payload.unreviewed_documents)
    && isReadinessItemList(payload.rejected_documents)
    && isReadinessItemList(payload.open_ncrs)
    && (payload.blocking_ncrs === undefined || isReadinessItemList(payload.blocking_ncrs))
    && isReadinessItemOrLabelList(payload.blocking_reasons);
}

export default function DossierDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const { id } = use(params);
  const { token, isAuthenticated, loading: authLoading } = useUserAuth();
  const [dossier, setDossier] = useState<DossierDetail | null>(null);
  const [readiness, setReadiness] = useState<DossierReadiness | null>(null);
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
        const authHeaders = { Authorization: `Bearer ${token}` };
        const [res, readinessRes] = await Promise.all([
          fetch(`/api/dossiers/${id}`, {
            headers: authHeaders,
          }),
          fetch(`/api/dossiers/${id}/readiness`, {
            headers: authHeaders,
          }),
        ]);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!readinessRes.ok) throw new Error(`HTTP ${readinessRes.status}`);
        const readinessPayload: unknown = await readinessRes.json();
        if (!isDossierReadiness(readinessPayload)) throw new Error("INVALID_READINESS_RESPONSE");
        setDossier(await res.json());
        setReadiness(readinessPayload);
      } catch (e) {
        setError(e instanceof Error && e.message === "INVALID_READINESS_RESPONSE"
          ? "Không tải được trạng thái sẵn sàng"
          : e instanceof Error ? e.message : "Không tải được hồ sơ");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, id, router]);

  if (loading || authLoading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" role="status" aria-live="polite" style={{ color: "#6B7280" }}>Đang tải hồ sơ…</p>
      </div>
    );
  }

  if (error || !dossier || !readiness) {
    return (
      <div className="min-h-screen grid place-items-center px-6">
        <div className="text-center">
          <p
            role="alert"
            className="text-sm mb-4 px-4 py-3 rounded-lg"
            style={{
              background: "rgba(239,68,68,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            {error || (!dossier ? "Không tìm thấy hồ sơ" : "Không tải được trạng thái sẵn sàng")}
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
  const blockingNcrs = readiness.blocking_ncrs ?? readiness.open_ncrs;
  const blockingNcrIds = new Set(blockingNcrs.map((ncr) => ncr.id).filter(Boolean));
  const nonBlockingNcrs = readiness.open_ncrs.filter((ncr) => !ncr.id || !blockingNcrIds.has(ncr.id));

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
          role="group"
          aria-label="Tiến độ hồ sơ"
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

        {readiness && (
          <div
            className="rounded-2xl p-5 mb-6"
            style={{ background: readiness.certificate_issue_blocked ? "#FFF7ED" : "#F0FDF4", border: `1px solid ${readiness.certificate_issue_blocked ? "#FED7AA" : "#BBF7D0"}` }}
            data-testid="certification-readiness-panel"
            aria-labelledby="readiness-heading"
          >
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h2 id="readiness-heading" className="text-base font-semibold" style={{ color: "#0A1F44" }}>
                  Mức sẵn sàng chứng nhận
                </h2>
                {readiness.state && (
                  <p className="mt-2 inline-flex rounded-full px-3 py-1 text-xs font-semibold" data-testid="dossier-readiness-state" role="status">
                    {DOSSIER_STATE_LABEL[readiness.state] ?? "Đang cập nhật trạng thái hồ sơ"}
                  </p>
                )}
                <p className="text-xs mt-1" style={{ color: "#92400E" }}>
                  Nguồn xác thực từ readiness endpoint của backend.
                </p>
              </div>
              <div className="text-3xl font-bold" style={{ color: readiness.certificate_issue_blocked ? "#B45309" : "#15803D" }} aria-label={`Sẵn sàng ${readiness.readiness_percent} phần trăm`}>
                {readiness.readiness_percent}%
              </div>
            </div>

            <div className="grid gap-3 mb-4 sm:grid-cols-2">
              <div className="rounded-xl p-3" style={{ background: "#FFFFFF", border: "1px solid #FDE68A" }}>
                <div className="text-[11px] font-semibold uppercase" style={{ color: "#92400E" }}>
                  Hành động tiếp theo
                </div>
                <div className="text-sm mt-1" style={{ color: "#0A1F44" }}>
                  {readiness.next_action ? NEXT_ACTION_LABEL[readiness.next_action] ?? "Đang cập nhật bước tiếp theo" : "Chưa có hành động tiếp theo"}
                </div>
              </div>
              <div className="rounded-xl p-3" style={{ background: "#FFFFFF", border: "1px solid #FDE68A" }}>
                <div className="text-[11px] font-semibold uppercase" style={{ color: "#92400E" }}>
                  Vai trò phụ trách
                </div>
                <div className="text-sm mt-1" style={{ color: "#0A1F44" }}>
                  {(readiness.next_action_owner_role || readiness.next_actor_role) ? ACTOR_ROLE_LABEL[readiness.next_action_owner_role || readiness.next_actor_role || ""] ?? "Đang xác định vai trò" : "Chưa chỉ định"}
                </div>
              </div>
              <div className="rounded-xl p-3" style={{ background: "#FFFFFF", border: "1px solid #FDE68A" }}>
                <div className="text-[11px] font-semibold uppercase" style={{ color: "#92400E" }}>
                  Hạn xử lý
                </div>
                <div className="text-sm mt-1" style={{ color: "#0A1F44" }} data-testid="readiness-due-date">
                  {readiness.due_date ? new Date(readiness.due_date).toLocaleDateString("vi-VN", { timeZone: "UTC" }) : "Chưa có hạn được thiết lập"}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {readiness.certificate_issue_blocked && (
                <div role="alert" className="rounded-lg px-3 py-2 text-sm font-semibold" style={{ color: "#9A3412", background: "#FFEDD5" }}>
                  Chưa thể cấp chứng nhận — cần xử lý các mục chặn bên dưới.
                </div>
              )}
              {!readiness.safe_public_trace_available && (
                <div role="status" className="text-sm" style={{ color: "#92400E" }}>
                  Chưa có trang truy xuất công khai cho hồ sơ này.
                </div>
              )}

              {readiness.missing_required_documents.length > 0 && (
                <div>
                  <div className="text-xs font-semibold mb-1" style={{ color: "#92400E" }}>
                    Tài liệu bắt buộc còn thiếu
                  </div>
                  <ul className="list-disc pl-5 text-sm" style={{ color: "#0A1F44" }}>
                    {readiness.missing_required_documents.map((item, index) => (
                      <li key={`missing-${index}`}>{readinessItemLabel(item)}</li>
                    ))}
                  </ul>
                </div>
              )}

              {readiness.rejected_documents.length > 0 && (
                <div>
                  <div className="text-xs font-semibold mb-1" style={{ color: "#92400E" }}>
                    Tài liệu bị từ chối
                  </div>
                  <ul className="list-disc pl-5 text-sm" style={{ color: "#0A1F44" }}>
                    {readiness.rejected_documents.map((item, index) => (
                      <li key={item.id || `rejected-${index}`}>
                        {readinessItemLabel(item)}
                        {readinessDocDetail(item) ? ` — ${readinessDocDetail(item)}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {blockingNcrs.length > 0 && (
                <div>
                  <div className="text-xs font-semibold mb-1" style={{ color: "#92400E" }}>
                    NCR/CAPA đang chặn quyết định
                  </div>
                  <ul className="list-disc pl-5 text-sm" style={{ color: "#0A1F44" }}>
                    {blockingNcrs.map((item, index) => (
                      <li key={item.id || `ncr-${index}`}>
                        {[item.code, item.title || item.description || readinessItemLabel(item), item.severity].filter(Boolean).join(" — ")}
                        {item.deadline ? ` — Hạn: ${new Date(item.deadline).toLocaleDateString("vi-VN", { timeZone: "UTC" })}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {nonBlockingNcrs.length > 0 && (
                <div role="status" className="rounded-lg px-3 py-2 text-sm" style={{ color: "#334155", background: "#F1F5F9" }}>
                  {nonBlockingNcrs.length} NCR mức nhẹ đang mở; hiện không chặn quyết định chứng nhận.
                </div>
              )}

              {readiness.blocking_reasons.length > 0 && (
                <div>
                  <div className="text-xs font-semibold mb-1" style={{ color: "#92400E" }}>
                    Lý do chặn
                  </div>
                  <ul className="list-disc pl-5 text-sm" style={{ color: "#0A1F44" }}>
                    {readiness.blocking_reasons.map((reason, index) => (
                      <li key={typeof reason === "string" ? reason : String(reason.code ?? reason.id ?? `blocker-${index}`)}>
                        {safeBlockerLabel(reason)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {readiness.next_action && ["upload_required_documents", "replace_rejected_documents"].includes(readiness.next_action) && (
                <Link
                  href={`/documents?dossier=${dossier.id}`}
                  className="inline-flex min-h-11 items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
                  style={{ background: "#0A1F44" }}
                  data-testid="readiness-recovery-cta"
                >
                  {readiness.next_action === "replace_rejected_documents" ? "Thay tài liệu bị từ chối" : "Tải tài liệu bắt buộc lên"}
                </Link>
              )}
            </div>
          </div>
        )}

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
        <div className="flex flex-col gap-3 sm:flex-row">
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
