"use client";

/**
 * Dossier detail — info + standard + doc_types required + uploaded documents.
 */

import { useEffect, useState, use, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import RevisionPanel from "@/components/submissions/RevisionPanel";
import { DOC_TYPE_LABEL_VI, canEditDossierDocuments } from "@/lib/dossierWorkflow";

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

interface AttachableDocument {
  id: string;
  doc_type: string;
  original_filename: string;
  version_number: number;
}

interface DossierDetail {
  id: string;
  title: string;
  status: string;
  notes: string | null;
  standard_code: string | null;
  standard_name_vi: string | null;
  requirements_binding_status: string;
  doc_types: DocTypeReq[];
  documents: DocumentInDossier[];
  created_at: string;
  updated_at: string;
}

interface ReadinessItem {
  id?: string | null;
  code?: string | null;
  title?: string | null;
  label?: string | null;
  doc_type?: string | null;
  filename?: string | null;
  reason?: string | null;
  description?: string | null;
  deadline?: string | null;
  severity?: string | null;
}

interface DossierReadiness {
  state?: string;
  readiness_percent: number | null;
  certificate_issue_blocked: boolean;
  safe_public_trace_available: boolean;
  requirement_slots?: Array<{ submission_id?: string | null }>;
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
  cert_issued: { vi: "Đã cấp chứng nhận", color: "#16A34A" },
  cancelled: { vi: "Đã hủy", color: "#DC2626" },
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
  submit_dossier_to_cb: "Gửi hồ sơ cho đơn vị chứng nhận",
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
  documents_ready_to_submit: "Đã chuẩn bị tài liệu — chưa gửi đơn vị chứng nhận",
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
  if (textFields.some((field) => item[field] != null && typeof item[field] !== "string")) return false;
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

  return ((typeof percent === "number" && Number.isFinite(percent) && percent >= 0 && percent <= 100)
    || (percent === null && typeof payload.state === "string" && payload.state.startsWith("requirements_")))
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
  const { token, user, isAuthenticated, loading: authLoading } = useUserAuth();
  const [dossier, setDossier] = useState<DossierDetail | null>(null);
  const [readiness, setReadiness] = useState<DossierReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attachableDocuments, setAttachableDocuments] = useState<AttachableDocument[]>([]);
  const [selectedDocumentByType, setSelectedDocumentByType] = useState<Record<string, string>>({});
  const [selectedFileByType, setSelectedFileByType] = useState<Record<string, File | null>>({});
  const [attachmentBusyType, setAttachmentBusyType] = useState<string | null>(null);
  const [attachmentMessage, setAttachmentMessage] = useState<string | null>(null);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const idempotencyBySlot = useRef<Record<string, { signature: string; key: string }>>({});

  const canEditDocuments = canEditDossierDocuments(user, dossier);
  const linkedSubmissionId = Array.isArray(readiness?.requirement_slots)
    ? readiness.requirement_slots.find((slot) => Boolean(slot.submission_id))?.submission_id ?? null : null;
  const hasSubmission = Boolean(linkedSubmissionId);
  const isClosed = dossier ? ["cancelled", "cert_issued"].includes(dossier.status) : false;

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
        if (!res.ok) throw new Error([403, 404].includes(res.status)
          ? "Không tìm thấy hồ sơ hoặc bạn không có quyền xem."
          : "Không tải được hồ sơ. Vui lòng thử lại.");
        const dossierPayload: DossierDetail = await res.json();
        // Cancelled dossiers remain readable, but readiness intentionally returns404.
        // Do not invent readiness or let that response hide an authorized dossier.
        if (dossierPayload.status === "cancelled") {
          setDossier(dossierPayload);
          setReadiness(null);
          setAttachableDocuments([]);
          return;
        }
        if (!readinessRes.ok) throw new Error("Không tải được trạng thái hồ sơ. Vui lòng thử lại.");
        const readinessPayload: unknown = await readinessRes.json();
        if (!isDossierReadiness(readinessPayload)) throw new Error("INVALID_READINESS_RESPONSE");
        setDossier(dossierPayload);
        setReadiness(readinessPayload);
        if (canEditDossierDocuments(user, dossierPayload)) {
          const availableRes = await fetch(`/api/dossiers/${id}/attachable-documents`, { headers: authHeaders });
          if (availableRes.ok) {
            const availablePayload = await availableRes.json();
            setAttachableDocuments(Array.isArray(availablePayload.items) ? availablePayload.items : []);
          } else {
            setAttachableDocuments([]);
            setAttachmentError("Không tải được danh sách tài liệu có thể đính kèm");
          }
        } else {
          setAttachableDocuments([]);
        }
      } catch (e) {
        setError(e instanceof Error && e.message === "INVALID_READINESS_RESPONSE"
          ? "Không tải được trạng thái sẵn sàng"
          : e instanceof Error ? e.message : "Không tải được hồ sơ");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, id, router, user?.role, user?.is_owner, user?.permissions?.can_upload]);

  const attachForSlot = async (docType: string) => {
    if (!token || attachmentBusyType || !canEditDocuments) return;
    const selectedFile = selectedFileByType[docType] ?? null;
    const selectedDocumentId = selectedDocumentByType[docType] ?? "";
    if (Number(Boolean(selectedFile)) + Number(Boolean(selectedDocumentId)) !== 1) {
      setAttachmentError("Chọn một tệp mới hoặc một tài liệu đã có trước khi đính kèm");
      return;
    }
    const signature = selectedFile
      ? `file:${selectedFile.name}:${selectedFile.size}:${selectedFile.lastModified}:${docType}`
      : `reference:${selectedDocumentId}:${docType}`;
    const previousKey = idempotencyBySlot.current[docType];
    const idempotencyKey = previousKey?.signature === signature ? previousKey.key : crypto.randomUUID();
    idempotencyBySlot.current[docType] = { signature, key: idempotencyKey };
    setAttachmentBusyType(docType);
    setAttachmentError(null);
    setAttachmentMessage(null);
    try {
      const form = new FormData();
      form.append("doc_type", docType);
      if (selectedFile) form.append("file", selectedFile);
      else form.append("document_id", selectedDocumentId);
      const response = await fetch(`/api/dossiers/${id}/documents`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Idempotency-Key": idempotencyKey },
        body: form,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `Đính kèm thất bại (HTTP ${response.status})`);
      if (result.attachment_state !== "attached" || !result.document_id) {
        throw new Error("Máy chủ chưa xác nhận tài liệu đã được đính kèm");
      }
      const headers = { Authorization: `Bearer ${token}` };
      const [dossierRes, readinessRes, availableRes] = await Promise.all([
        fetch(`/api/dossiers/${id}`, { headers }),
        fetch(`/api/dossiers/${id}/readiness`, { headers }),
        fetch(`/api/dossiers/${id}/attachable-documents`, { headers }),
      ]);
      if (!dossierRes.ok || !readinessRes.ok || !availableRes.ok) {
        throw new Error("Tài liệu đã được lưu nhưng checklist chưa tải lại được; hãy tải lại trang để xác nhận");
      }
      const [dossierPayload, readinessPayload, availablePayload] = await Promise.all([
        dossierRes.json(), readinessRes.json(), availableRes.json(),
      ]);
      if (!isDossierReadiness(readinessPayload) || !Array.isArray(dossierPayload.documents)) {
        throw new Error("Tệp đã được gửi nhưng phản hồi checklist không hợp lệ; hãy tải lại trang");
      }
      setDossier(dossierPayload);
      setReadiness(readinessPayload);
      setAttachableDocuments(Array.isArray(availablePayload.items) ? availablePayload.items : []);
      setSelectedDocumentByType((previous) => ({ ...previous, [docType]: "" }));
      setSelectedFileByType((previous) => ({ ...previous, [docType]: null }));
      delete idempotencyBySlot.current[docType];
      setAttachmentMessage("Tài liệu đã được đính kèm vào hồ sơ và checklist đã cập nhật.");
    } catch (cause) {
      setAttachmentError(cause instanceof Error ? cause.message : "Không thể đính kèm tài liệu");
    } finally {
      setAttachmentBusyType(null);
    }
  };

  if (loading || authLoading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" role="status" aria-live="polite" style={{ color: "#6B7280" }}>Đang tải hồ sơ…</p>
      </div>
    );
  }

  if (error || !dossier || (!readiness && dossier.status !== "cancelled")) {
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
  const blockingNcrs = readiness?.blocking_ncrs ?? readiness?.open_ncrs ?? [];
  const blockingNcrIds = new Set(blockingNcrs.map((ncr) => ncr.id).filter(Boolean));
  const nonBlockingNcrs = (readiness?.open_ncrs ?? []).filter((ncr) => !ncr.id || !blockingNcrIds.has(ncr.id));

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


        {dossier.status === "cancelled" && <p role="status" className="mb-6 rounded-xl border border-slate-300 bg-slate-50 p-4 text-sm text-slate-700">Hồ sơ đã hủy. Chỉ hiển thị thông tin và tài liệu đã lưu.</p>}

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
                    {isClosed ? st.vi : DOSSIER_STATE_LABEL[readiness.state] ?? "Đang cập nhật trạng thái hồ sơ"}
                  </p>
                )}
                <p className="text-xs mt-1" style={{ color: "#92400E" }}>
                  Chỉ tính bằng chứng đã được bên phụ trách xác nhận.
                </p>
              </div>
              <div className="text-3xl font-bold" style={{ color: readiness.certificate_issue_blocked ? "#B45309" : "#15803D" }} aria-label={readiness.readiness_percent == null ? "Chưa xác định mức sẵn sàng" : `Sẵn sàng ${readiness.readiness_percent} phần trăm`}>
                {readiness.readiness_percent == null ? "Chưa xác định" : `${readiness.readiness_percent}%`}
              </div>
            </div>

            <div className="grid gap-3 mb-4 sm:grid-cols-2">
              <div className="rounded-xl p-3" style={{ background: "#FFFFFF", border: "1px solid #FDE68A" }}>
                <div className="text-[11px] font-semibold uppercase" style={{ color: "#92400E" }}>
                  Hành động tiếp theo
                </div>
                <div className="text-sm mt-1" style={{ color: "#0A1F44" }}>
                  {isClosed ? "Hồ sơ đã đóng; bạn có thể xem lại lịch sử" : readiness.next_action ? NEXT_ACTION_LABEL[readiness.next_action] ?? "Đang cập nhật bước tiếp theo" : "Chưa có hành động tiếp theo"}
                </div>
              </div>
              <div className="rounded-xl p-3" style={{ background: "#FFFFFF", border: "1px solid #FDE68A" }}>
                <div className="text-[11px] font-semibold uppercase" style={{ color: "#92400E" }}>
                  Vai trò phụ trách
                </div>
                <div className="text-sm mt-1" style={{ color: "#0A1F44" }}>
                  {isClosed ? "Không còn thao tác chỉnh sửa" : (readiness.next_action_owner_role || readiness.next_actor_role) ? ACTOR_ROLE_LABEL[readiness.next_action_owner_role || readiness.next_actor_role || ""] ?? "Đang xác định vai trò" : "Chưa chỉ định"}
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
          {attachmentError && <p role="alert" className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-800">{attachmentError}</p>}
          {attachmentMessage && <p role="status" className="mb-3 rounded-lg bg-green-50 p-3 text-sm text-green-800">{attachmentMessage}</p>}
          {user?.role === "business" && dossier.requirements_binding_status !== "bound" && (
            <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Hồ sơ chưa được gắn với phiên bản yêu cầu đã xác minh; không thể đính kèm hoặc tự gắn lại tài liệu cũ.</p>
          )}
          <div id="dossier-document-attachments" className="space-y-2">
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
                    {canEditDocuments && (
                      <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
                        <label className="block text-xs font-medium text-slate-700">
                          Dùng tài liệu đã có
                          <select
                            aria-label={`Tài liệu có sẵn cho ${DOC_TYPE_LABEL_VI[dt.doc_type] ?? dt.doc_type}`}
                            value={selectedDocumentByType[dt.doc_type] ?? ""}
                            onChange={(event) => {
                              setSelectedDocumentByType((previous) => ({ ...previous, [dt.doc_type]: event.target.value }));
                              setSelectedFileByType((previous) => ({ ...previous, [dt.doc_type]: null }));
                              setAttachmentError(null);
                            }}
                            className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-2"
                          >
                            <option value="">Chọn tài liệu cùng loại</option>
                            {attachableDocuments.filter((doc) => doc.doc_type === dt.doc_type).map((doc) => (
                              <option key={doc.id} value={doc.id}>
                                {doc.original_filename} — v{doc.version_number}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="block text-xs font-medium text-slate-700">
                          Hoặc tải tệp mới
                          <input
                            aria-label={`Tệp mới cho ${DOC_TYPE_LABEL_VI[dt.doc_type] ?? dt.doc_type}`}
                            type="file"
                            accept=".pdf,.txt,.md,.docx,.odt,.ppt,.pptx"
                            onChange={(event) => {
                              setSelectedFileByType((previous) => ({ ...previous, [dt.doc_type]: event.target.files?.[0] ?? null }));
                              setSelectedDocumentByType((previous) => ({ ...previous, [dt.doc_type]: "" }));
                              setAttachmentError(null);
                            }}
                            className="mt-1 block min-h-10 w-full text-xs"
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => void attachForSlot(dt.doc_type)}
                          disabled={attachmentBusyType !== null}
                          className="min-h-10 rounded-lg px-3 text-sm font-semibold text-white disabled:opacity-50"
                          style={{ background: "#0A1F44" }}
                        >
                          {attachmentBusyType === dt.doc_type ? "Đang đính kèm…" : "Đính kèm tài liệu"}
                        </button>
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
          {canEditDocuments && user?.is_owner === true && !hasSubmission && dossier.documents.length > 0 && (
              <Link
                href={`/submissions?dossier_id=${dossier.id}`}
                data-testid="dossier-submit-cta"
                className="flex-1 rounded-xl px-5 py-2.5 text-center text-sm font-semibold text-white"
                style={{ background: "#0A1F44" }}
              >
                Gửi hồ sơ cho CB
              </Link>
            )}
          {canEditDocuments && <>
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
          <a
            href="#dossier-document-attachments"
            className="flex-1 text-center px-5 py-2.5 rounded-xl font-semibold text-sm text-white"
            style={{ background: "#0A1F44" }}
            data-testid="dossier-upload-doc-cta"
          >
            ↑ Bổ sung tài liệu vào hồ sơ
          </a>
          </>}
          {hasSubmission && user?.is_owner === true && <Link href="/submissions" className="rounded-xl border border-slate-300 px-5 py-2.5 text-center text-sm font-semibold">Xem hồ sơ đã gửi</Link>}
        </div>

        {linkedSubmissionId && token && user?.role === "business" && user.is_owner !== true && (
          <section id="dossier-submission-history" aria-label="Lịch sử hồ sơ đã gửi" className="mt-6">
            <p className="mb-3 text-sm text-slate-600">Bạn có thể xem lịch sử; chủ tài khoản doanh nghiệp phụ trách gửi và gửi lại hồ sơ.</p>
            <RevisionPanel submissionId={linkedSubmissionId} status="read_only" role="business"
              token={token} canResubmit={false}
              documents={dossier.documents.map((doc) => ({id:doc.id,filename:doc.original_filename,doc_type:doc.doc_type}))} />
          </section>
        )}

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
