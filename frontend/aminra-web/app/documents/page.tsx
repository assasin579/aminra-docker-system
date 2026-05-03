"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useDropzone } from "react-dropzone";
import { useUserAuth } from "@/components/UserAuthContext";
import { openAuthed } from "@/lib/authedOpen";
import { useFeature } from "@/lib/featureFlags";
import ApprovalStatusBadge from "@/components/documents/ApprovalStatusBadge";
import ApprovalActions from "@/components/documents/ApprovalActions";
import Modal from "@/components/Modal";
import type {
  ApprovalBlock as ApprovalData,
  ApprovalStatus,
} from "@/lib/documentVersioning";

// ── Doc type options (from upload page) ──────────────────────────────────────

const DOC_TYPE_OPTIONS = [
  { id: "halal_policy", label: "Halal Policy", group: "policy" },
  { id: "has_manual", label: "HAS Manual", group: "policy" },
  { id: "halal_manual", label: "Halal Manual", group: "policy" },
  {
    id: "internal_halal_committee",
    label: "Internal Halal Committee",
    group: "policy",
  },
  { id: "company_profile", label: "Company Profile", group: "policy" },
  {
    id: "ingredient_raw_material",
    label: "Ingredient & Raw Material Documentation",
    group: "tech",
  },
  { id: "process_flow_chart", label: "Process Flow Chart", group: "tech" },
];

const SOP_SUB_OPTIONS = [
  { id: "sop_raw_material_receiving", label: "Raw Material Receiving" },
  { id: "sop_storage_segregation", label: "Storage and Segregation" },
  { id: "sop_production_operation", label: "Production or Service Operation" },
  { id: "sop_cleaning_sanitation", label: "Cleaning and Sanitation" },
  { id: "sop_handling_nonconformances", label: "Handling Non-Conformances" },
  { id: "sop_complaint_recall", label: "Complaint and Recall Management" },
];

const DOC_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  [...DOC_TYPE_OPTIONS, ...SOP_SUB_OPTIONS].map((d) => [d.id, d.label]),
);

interface DocumentItem {
  id: string;
  original_filename: string;
  doc_type: string | null;
  doc_type_label: string | null;
  compliance_score: number | null;
  overall_status: string | null;
  file_size: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string;
  revision_count?: number | null;
  status?: string | null;
  /** Tier-1 #24: included by backend when document_versioning_v1 flag ON. */
  approval_status?: ApprovalStatus | null;
  version_number?: number | null;
}

interface RevisionItem {
  id: string;
  original_filename: string;
  compliance_score: number | null;
  overall_status: string | null;
  file_size: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string;
}

interface RevisionListResponse {
  doc_type: string;
  doc_type_label: string | null;
  revisions: RevisionItem[];
  total: number;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; bg: string; color: string; glow: string }
> = {
  cb_approved: {
    label: "Đã được duyệt bởi CB",
    bg: "#DCE3F0",
    color: "#0A1F44",
    glow: "0 0 8px rgba(10,31,68,0.2)",
  },
  compliant: {
    label: "Đạt chuẩn",
    bg: "#DCE3F0",
    color: "#102A5C",
    glow: "none",
  },
  needs_review: {
    label: "Cần xem xét",
    bg: "#FFFBEB",
    color: "#B45309",
    glow: "none",
  },
  non_compliant: {
    label: "Không đạt",
    bg: "#FEF2F2",
    color: "#DC2626",
    glow: "none",
  },
};

function scoreColor(s: number | null) {
  if (s === null) return "#D1D5DB";
  if (s >= 75) return "#102A5C";
  if (s >= 50) return "#D97706";
  return "#DC2626";
}

function criteriaColor(score: number, weight: number) {
  if (weight <= 0) return "#D1D5DB";
  const pct = (score / weight) * 100;
  if (pct >= 75) return "#102A5C";
  if (pct >= 50) return "#D97706";
  return "#DC2626";
}

function formatSize(bytes: number | null) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return "Hôm nay";
  if (d === 1) return "Hôm qua";
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
}

function MiniScore({ score }: { score: number | null }) {
  if (score === null)
    return (
      <span className="text-sm" style={{ color: "#94A3B8" }}>
        —
      </span>
    );
  const pct = Math.min(score, 100);
  const color = scoreColor(score);
  return (
    <div className="relative w-12 h-12 flex-shrink-0">
      <svg viewBox="0 0 40 40" className="w-full h-full -rotate-90">
        <circle
          cx="20"
          cy="20"
          r="16"
          fill="none"
          stroke="#E2E8F0"
          strokeWidth="3"
        />
        <circle
          cx="20"
          cy="20"
          r="16"
          fill="none"
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${pct * 1.005} 100.5`}
          className="animate-score-fill"
          style={{
            transition: "stroke-dasharray 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />
      </svg>
      <span
        className="absolute inset-0 grid place-items-center text-xs font-bold"
        style={{ color }}
      >
        {score}
      </span>
    </div>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const versioningOn = useFeature("document_versioning_v1");

  // Tier-1 #24 — derived perms for ApprovalActions buttons. Owner has
  // everything; IHC member auto-receives can_approve_documents per
  // JAKIM MS 1500 §5.4 (matches backend auth.permissions logic).
  const userPerms = {
    canEdit: !!(user?.is_owner || user?.permissions?.can_edit),
    canApproveDocuments: !!(
      user?.is_owner ||
      !!user?.ihc_role ||
      user?.permissions?.can_approve_documents
    ),
    isOwner: !!user?.is_owner,
    isIhcMember: !!user?.ihc_role,
  };

  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [fetching, setFetching] = useState(false);

  const [filterStatus, setFilterStatus] = useState("");
  const filterType = "";

  const [removeId, setRemoveId] = useState<string | null>(null);
  const [evalDetail, setEvalDetail] = useState<any | null>(null);
  const [loadingEval, setLoadingEval] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<RevisionListResponse | null>(
    null,
  );
  const [loadingHistory, setLoadingHistory] = useState<string | null>(null);
  const [promotingId, setPromotingId] = useState<string | null>(null);

  // Upload modal
  const [showUpload, setShowUpload] = useState(false);
  const [uploadDocType, setUploadDocType] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [sopExpanded, setSopExpanded] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // AI evaluate
  const [evaluatingId, setEvaluatingId] = useState<string | null>(null);
  const [evalLangModal, setEvalLangModal] = useState<string | null>(null); // doc_id waiting for lang choice

  // Submit to provider
  const [showSubmit, setShowSubmit] = useState(false);
  const [providers, setProviders] = useState<
    Array<{ id: string; company_name: string; email: string }>
  >([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [submitNotes, setSubmitNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const PAGE_SIZE = 15;

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace("/business/login");
    } else if (!loading && isAuthenticated && user?.role !== "business") {
      router.replace(user?.role === "provider" ? "/dashboard/provider" : "/");
    }
  }, [loading, isAuthenticated, user, router]);

  const fetchDocs = useCallback(
    async (p = 1, silent = false) => {
      if (!token) return;
      if (!silent) setFetching(true);
      try {
        const params = new URLSearchParams({
          page: String(p),
          page_size: String(PAGE_SIZE),
        });
        if (filterType) params.set("doc_type", filterType);
        if (filterStatus) params.set("status", filterStatus);
        const res = await fetch(`/api/api/documents?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setDocs(data.documents);
          setTotal(data.total);
          setPage(p);
        }
      } finally {
        if (!silent) setFetching(false);
      }
    },
    [token, filterType, filterStatus],
  );

  useEffect(() => {
    if (isAuthenticated) fetchDocs(1);
  }, [isAuthenticated, fetchDocs]);

  const openEval = async (id: string) => {
    setLoadingEval(id);
    try {
      const res = await fetch(`/api/api/documents/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (!data.extracted_text && data.evaluation_result?.extracted_text) {
          data.extracted_text = data.evaluation_result.extracted_text;
        }
        // Merge criteria_scores from evaluation_result
        if (data.evaluation_result?.criteria_scores) {
          data.criteria_scores = data.evaluation_result.criteria_scores;
        }
        if (data.evaluation_result?.signature_detection) {
          data.signature_detection = data.evaluation_result.signature_detection;
        }
        setEvalDetail(data);
      }
    } finally {
      setLoadingEval(null);
    }
  };

  const openView = (id: string) => {
    openAuthed(`/api/api/documents/${id}/preview`, token || "");
  };

  const openHistory = async (docType: string) => {
    setLoadingHistory(docType);
    try {
      const res = await fetch(
        `/api/api/documents/revisions/${encodeURIComponent(docType)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (res.ok) setHistoryData(await res.json());
    } finally {
      setLoadingHistory(null);
    }
  };

  const handlePromote = async (id: string, docType: string) => {
    if (
      !confirm(
        "Chọn phiên bản này làm tài liệu chính thức? Phiên bản này sẽ thay thế version hiện tại.",
      )
    )
      return;
    setPromotingId(id);
    try {
      const res = await fetch(`/api/api/documents/${id}/promote`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        // Refresh history and doc list
        await openHistory(docType);
        fetchDocs(page);
      }
    } finally {
      setPromotingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Xác nhận xoá tài liệu này?")) return;
    setRemoveId(id);
    try {
      await fetch(`/api/api/documents/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchDocs(page);
    } finally {
      setRemoveId(null);
    }
  };

  const openSubmitModal = async () => {
    try {
      const res = await fetch("/api/api/submissions/providers", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setProviders(d.providers || []);
      }
    } catch {}
    setSelectedDocs(new Set(docs.map((d) => d.id)));
    setShowSubmit(true);
  };

  const handleSubmit = async () => {
    if (!selectedProvider || selectedDocs.size === 0) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/api/submissions/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          provider_id: selectedProvider,
          document_ids: Array.from(selectedDocs),
          notes: submitNotes,
        }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || "Gửi thất bại");
      }
      const d = await res.json();
      alert(d.message);
      setShowSubmit(false);
      setSubmitNotes("");
    } catch (e: any) {
      alert(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Upload handler ──────────────────────────────────────────────────────────
  const handleUpload = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || !uploadDocType || !token) return;
      setUploading(true);
      setUploadError("");
      try {
        const form = new FormData();
        form.append("file", file);
        form.append("doc_type", uploadDocType);
        const res = await fetch("/api/api/documents/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          throw new Error(e.detail || `Upload thất bại (${res.status})`);
        }
        setShowUpload(false);
        setUploadDocType(null);
        setSopExpanded(false);
        setUploadError("");
        fetchDocs(1);
      } catch (e: any) {
        setUploadError(e.message || "Upload thất bại");
      } finally {
        setUploading(false);
      }
    },
    [uploadDocType, token, fetchDocs],
  );

  const dropzone = useDropzone({
    onDrop: handleUpload,
    maxFiles: 1,
    disabled: !uploadDocType || uploading,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        [".pptx"],
      "application/vnd.oasis.opendocument.text": [".odt"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
  });

  // ── AI Evaluate handler ────────────────────────────────────────────────────
  const handleEvaluate = async (docId: string, evalLang: string = "vi") => {
    setEvalLangModal(null);
    setEvaluatingId(docId);
    try {
      const res = await fetch(
        `/api/api/documents/${docId}/evaluate?lang=${evalLang}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Đánh giá thất bại");
        setEvaluatingId(null);
        return;
      }
      // Refresh — doc will show "Đang đánh giá..."
      await fetchDocs(page, true);
    } catch (err) {
      alert("Đánh giá thất bại");
    }
    setEvaluatingId(null);
  };

  // Auto-refresh when there are evaluating documents (poll every 5s)
  // Silent polling when evaluating — no loading skeleton flicker
  const hasEvaluating = docs.some((d) => d.status === "evaluating");
  const pageRef = useRef(page);
  pageRef.current = page;
  const fetchRef = useRef(fetchDocs);
  fetchRef.current = fetchDocs;
  useEffect(() => {
    if (!hasEvaluating) return;
    const interval = setInterval(
      () => fetchRef.current(pageRef.current, true),
      5000,
    );
    return () => clearInterval(interval);
  }, [hasEvaluating]);

  if (loading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
        </div>
      </div>
    );

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Stats
  const compliantCount = docs.filter(
    (d) =>
      d.overall_status === "compliant" || d.overall_status === "cb_approved",
  ).length;
  const reviewCount = docs.filter(
    (d) => d.overall_status === "needs_review",
  ).length;
  const failCount = docs.filter(
    (d) => d.overall_status === "non_compliant",
  ).length;

  return (
    <div
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden"
      data-page
    >
      {/* ── Header ── */}
      <div
        className="rounded-2xl p-6 mb-6 animate-section"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        <div
          className="grid items-center"
          style={{ gridTemplateColumns: "1fr auto" }}
        >
          <div>
            <div className="grid grid-flow-col items-center gap-3 justify-start mb-2">
              <div
                className="w-10 h-10 rounded-xl grid place-items-center"
                style={{
                  background: "rgba(10,31,68,0.15)",
                  border: "1px solid rgba(10,31,68,0.3)",
                }}
              >
                <svg
                  className="w-5 h-5"
                  style={{ color: "#0A1F44" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
                  Tài liệu
                </h1>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {docs.length > 0 && (
              <button
                onClick={openSubmitModal}
                className="grid items-center gap-2 px-3 py-2 sm:px-5 sm:py-3 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-200 ease-out hover:scale-105"
                style={{
                  gridTemplateColumns: "auto 1fr",
                  background: "rgba(14,165,233,0.15)",
                  color: "#0EA5E9",
                  border: "1px solid rgba(14,165,233,0.3)",
                }}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
                Gửi hồ sơ
              </button>
            )}
            <Link
              href="/create-document"
              className="grid items-center gap-2 px-3 py-2 sm:px-5 sm:py-3 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-200 ease-out hover:scale-105"
              style={{
                gridTemplateColumns: "auto 1fr",
                background: "rgba(10,31,68,0.1)",
                color: "#0A1F44",
                border: "1px solid rgba(10,31,68,0.2)",
              }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Tạo tài liệu chuẩn
            </Link>
            <button
              onClick={() => setShowUpload(true)}
              className="grid items-center gap-2 px-3 py-2 sm:px-5 sm:py-3 rounded-xl text-xs sm:text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105 active:scale-[0.97]"
              style={{
                gridTemplateColumns: "auto 1fr",
                background: "linear-gradient(135deg, #0A1F44, #0A1F44)",
                boxShadow: "0 4px 15px rgba(10,31,68,0.3)",
              }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Upload tài liệu
            </button>
          </div>
        </div>
      </div>

      {/* ── Filter ── */}
      <div className="mb-5">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="text-sm px-4 py-2.5 rounded-xl outline-none transition-all"
          style={{
            background: "#F5F1E8",
            border: "1px solid #E2E8F0",
            color: "#374151",
          }}
        >
          <option value="">Tất cả trạng thái</option>
          <option value="compliant">Đạt chuẩn</option>
          <option value="needs_review">Cần xem xét</option>
          <option value="non_compliant">Không đạt</option>
        </select>
      </div>

      {/* ── Document cards ── */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={`rounded-2xl p-5 animate-list-item stagger-${i}`}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              >
                <div className="flex items-center gap-4">
                  <div className="shimmer w-12 h-12 rounded-full flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="shimmer skeleton-text w-32" />
                    <div className="shimmer skeleton-text w-48" />
                    <div className="shimmer skeleton-text w-24" />
                  </div>
                  <div className="flex gap-2">
                    <div className="shimmer w-8 h-8 rounded-lg" />
                    <div className="shimmer w-8 h-8 rounded-lg" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div
            className="rounded-2xl p-16 text-center animate-scale-in"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <svg
              className="w-16 h-16 mx-auto mb-4 animate-empty-icon"
              style={{ color: "#CBD5E1" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
              Chưa có tài liệu nào
            </p>
            <p className="text-sm mb-5" style={{ color: "#6B7280" }}>
              Upload tài liệu đầu tiên để bắt đầu đánh giá Halal
            </p>
            <button
              onClick={() => setShowUpload(true)}
              className="inline-grid items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
              style={{ gridTemplateColumns: "auto 1fr", background: "#0A1F44" }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Upload tài liệu
            </button>
          </div>
        ) : (
          docs.map((doc, i) => {
            const st =
              doc.status === "evaluating"
                ? {
                    label: "Đang đánh giá...",
                    bg: "#F5F3FF",
                    color: "#7C3AED",
                    glow: "none",
                  }
                : doc.compliance_score === null
                  ? {
                      label: "Chưa đánh giá",
                      bg: "#F3F4F6",
                      color: "#6B7280",
                      glow: "none",
                    }
                  : STATUS_CONFIG[doc.overall_status || ""] || {
                      label: "Không rõ",
                      bg: "rgba(100,116,139,0.12)",
                      color: "#9CA3AF",
                      glow: "none",
                    };
            return (
              <div
                key={doc.id}
                className="rounded-2xl p-5 doc-card-hover animate-list-item"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                  animationDelay: `${i * 0.05}s`,
                }}
              >
                {/* Row 1: score + doc type + status + actions */}
                <div
                  className="grid items-center gap-4"
                  style={{ gridTemplateColumns: "auto 1fr auto" }}
                >
                  <MiniScore score={doc.compliance_score} />

                  <div className="min-w-0">
                    {/* Doc type + status badges */}
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <span
                        className="px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide"
                        style={{
                          background: "#F0F9FF",
                          color: "#0369A1",
                          border: "1px solid #BAE6FD",
                          letterSpacing: "0.02em",
                        }}
                      >
                        {(doc.doc_type && DOC_TYPE_LABELS[doc.doc_type]) ||
                          doc.doc_type_label ||
                          "Chưa phân loại"}
                      </span>
                      {st && (
                        <span
                          className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{
                            background: st.bg,
                            color: st.color,
                            boxShadow: st.glow,
                          }}
                        >
                          {st.label}
                        </span>
                      )}
                    </div>
                    {/* Filename */}
                    <h3
                      className="text-sm font-semibold truncate"
                      style={{ color: "#0A1F44" }}
                      title={doc.original_filename}
                    >
                      {doc.original_filename}
                    </h3>
                    {/* Meta */}
                    <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
                      {formatSize(doc.file_size)} ·{" "}
                      {new Date(doc.uploaded_at).toLocaleString("vi-VN", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>

                  {/* Actions — compact icon buttons */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {/* AI Evaluate button */}
                    <button
                      onClick={() => setEvalLangModal(doc.id)}
                      title={
                        doc.status === "evaluating"
                          ? "Đang đánh giá..."
                          : doc.compliance_score === null
                            ? "Đánh giá tài liệu bằng AI"
                            : "Đánh giá lại"
                      }
                      disabled={
                        evaluatingId === doc.id || doc.status === "evaluating"
                      }
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "#F5F3FF",
                        border: "1px solid #DDD6FE",
                      }}
                    >
                      {evaluatingId === doc.id ||
                      doc.status === "evaluating" ? (
                        <svg
                          className="w-4 h-4 animate-spin"
                          style={{ color: "#7C3AED" }}
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8v8z"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#7C3AED" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                          />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => openEval(doc.id)}
                      title="Kết quả đánh giá"
                      disabled={loadingEval === doc.id}
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "#FFFBEB",
                        border: "1px solid #FDE68A",
                      }}
                    >
                      {loadingEval === doc.id ? (
                        <svg
                          className="w-4 h-4 animate-spin"
                          style={{ color: "#B45309" }}
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8v8z"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#B45309" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => openView(doc.id)}
                      title="Xem file gốc"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "#F0F9FF",
                        border: "1px solid #BAE6FD",
                      }}
                    >
                      <svg
                        className="w-4 h-4"
                        style={{ color: "#0369A1" }}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openAuthed(
                          `/api/api/documents/${doc.id}/file`,
                          token || "",
                          { download: true, filename: doc.original_filename },
                        );
                      }}
                      title="Tải xuống"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "rgba(10,31,68,0.1)",
                        border: "1px solid rgba(10,31,68,0.2)",
                      }}
                    >
                      <svg
                        className="w-4 h-4"
                        style={{ color: "#0A1F44" }}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                        />
                      </svg>
                    </button>
                    {doc.doc_type && (doc.revision_count ?? 0) > 1 && (
                      <button
                        onClick={() => openHistory(doc.doc_type!)}
                        title="Lịch sử"
                        disabled={loadingHistory === doc.doc_type}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#FDF4FF",
                          border: "1px solid #F0ABFC",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#A21CAF" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </button>
                    )}
                    {user.is_owner && (
                      <button
                        onClick={() => handleDelete(doc.id)}
                        title="Xoá"
                        disabled={removeId === doc.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "rgba(239,68,68,0.08)",
                          border: "1px solid rgba(239,68,68,0.15)",
                        }}
                      >
                        {removeId === doc.id ? (
                          <svg
                            className="w-4 h-4 animate-spin"
                            style={{ color: "#9CA3AF" }}
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8v8z"
                            />
                          </svg>
                        ) : (
                          <svg
                            className="w-4 h-4"
                            style={{ color: "#9CA3AF" }}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Tier-1 #24: approval row (flag-gated) */}
                {versioningOn && doc.approval_status && (
                  <div
                    className="mt-3 pt-3 grid items-center gap-3"
                    style={{
                      gridTemplateColumns: "auto 1fr auto",
                      borderTop: "1px solid #F1F5F9",
                    }}
                  >
                    <ApprovalStatusBadge
                      status={doc.approval_status}
                      versionNumber={doc.version_number ?? undefined}
                      compact
                    />
                    <span className="text-xs" style={{ color: "#94A3B8" }}>
                      {doc.approval_status === "draft" &&
                        "Bản nháp · trình duyệt khi sẵn sàng"}
                      {doc.approval_status === "pending_approval" &&
                        "Đang chờ phê duyệt"}
                      {doc.approval_status === "approved" &&
                        "Đã phê duyệt — sẵn sàng nộp"}
                      {doc.approval_status === "obsolete" &&
                        "Đã thay thế bằng phiên bản mới"}
                    </span>
                    {token && doc.approval_status !== "obsolete" && (
                      <ApprovalActions
                        docId={doc.id}
                        approval={
                          {
                            approval_status: doc.approval_status,
                            version_number: doc.version_number ?? 1,
                            version_parent_id: null,
                            approver_id: null,
                            approved_at: null,
                            effective_date: null,
                            next_review_date: null,
                            retention_period_days: 1825,
                            retention_expires_at: null,
                            superseded_by_id: null,
                            is_obsolete: false,
                          } as ApprovalData
                        }
                        perms={userPerms}
                        token={token}
                        onChanged={() => fetchDocs(page)}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="grid grid-flow-col items-center gap-3 mt-5 justify-center flex-shrink-0">
          <button
            disabled={page === 1}
            onClick={() => fetchDocs(page - 1)}
            className="px-4 py-2 rounded-xl text-sm transition-all duration-200 ease-out hover:scale-105 disabled:opacity-30"
            style={{
              background: "#F5F1E8",
              border: "1px solid #E2E8F0",
              color: "#6B7280",
            }}
          >
            ← Trước
          </button>
          <span className="text-sm px-3" style={{ color: "#9CA3AF" }}>
            Trang <strong style={{ color: "#0A1F44" }}>{page}</strong> /{" "}
            {totalPages}
          </span>
          <button
            disabled={page === totalPages}
            onClick={() => fetchDocs(page + 1)}
            className="px-4 py-2 rounded-xl text-sm transition-all duration-200 ease-out hover:scale-105 disabled:opacity-30"
            style={{
              background: "#F5F1E8",
              border: "1px solid #E2E8F0",
              color: "#6B7280",
            }}
          >
            Sau →
          </button>
        </div>
      )}

      {/* ── Evaluation Detail Modal ── */}
      {evalDetail && (
        <Modal>
          <div
            className="w-full max-w-[calc(100vw-2rem)] md:max-w-3xl rounded-2xl flex flex-col animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
              boxShadow: "0 25px 60px rgba(0,0,0,0.1)",
            }}
          >
            {/* Header */}
            <div
              className="px-6 py-5 flex-shrink-0"
              style={{
                borderBottom: "1px solid #E2E8F0",
                background: "#FFFFFF",
              }}
            >
              <div
                className="grid items-center gap-4"
                style={{ gridTemplateColumns: "1fr auto" }}
              >
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span
                      className="px-3 py-1 rounded-lg text-xs font-bold"
                      style={{
                        background: "rgba(10,31,68,0.08)",
                        color: "#0A1F44",
                        border: "1px solid rgba(10,31,68,0.25)",
                      }}
                    >
                      {evalDetail.doc_type_label || evalDetail.doc_type}
                    </span>
                    {(() => {
                      const st = STATUS_CONFIG[evalDetail.overall_status || ""];
                      return st ? (
                        <span
                          className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.bg, color: st.color }}
                        >
                          {st.label}
                        </span>
                      ) : null;
                    })()}
                  </div>
                  <h2
                    className="text-base font-bold"
                    style={{ color: "#0A1F44" }}
                  >
                    {evalDetail.original_filename}
                  </h2>
                </div>
                <div className="flex items-center gap-4">
                  {/* Big score */}
                  <div className="text-center">
                    <div
                      className="text-3xl font-bold"
                      style={{ color: scoreColor(evalDetail.compliance_score) }}
                    >
                      {evalDetail.compliance_score ?? "—"}
                    </div>
                    <div className="text-xs" style={{ color: "#6B7280" }}>
                      điểm
                    </div>
                  </div>
                  <button
                    onClick={() => setEvalDetail(null)}
                    className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                    style={{ background: "rgba(0,0,0,0.05)" }}
                  >
                    <span style={{ color: "#6B7280" }}>✕</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
              {/* Summary */}
              {evalDetail.summary && (
                <div
                  className="rounded-xl p-4"
                  style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
                >
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "#374151" }}
                  >
                    {evalDetail.summary}
                  </p>
                </div>
              )}

              {/* Criteria scores */}
              {evalDetail.criteria_scores &&
                evalDetail.criteria_scores.length > 0 && (
                  <div>
                    <h3
                      className="text-sm font-bold mb-3"
                      style={{ color: "#0A1F44" }}
                    >
                      Điểm theo tiêu chí
                    </h3>
                    <div className="space-y-2">
                      {evalDetail.criteria_scores.map((cs: any, i: number) => (
                        <div
                          key={i}
                          className="rounded-xl p-4"
                          style={{
                            background: "#FFFFFF",
                            border: "1px solid #E2E8F0",
                          }}
                        >
                          <div
                            className="grid items-center gap-3"
                            style={{ gridTemplateColumns: "1fr auto" }}
                          >
                            <div>
                              <p
                                className="text-sm font-medium"
                                style={{ color: "#0A1F44" }}
                              >
                                {cs.criterion}
                              </p>
                              {cs.reason && (
                                <p
                                  className="text-sm mt-1"
                                  style={{ color: "#9CA3AF" }}
                                >
                                  {cs.reason}
                                </p>
                              )}
                            </div>
                            <div className="text-right flex-shrink-0">
                              <span
                                className="text-lg font-bold"
                                style={{
                                  color: criteriaColor(cs.score, cs.weight),
                                }}
                              >
                                {cs.score}
                              </span>
                              <span
                                className="text-sm"
                                style={{ color: "#6B7280" }}
                              >
                                /{cs.weight}
                              </span>
                            </div>
                          </div>
                          {/* Progress bar */}
                          <div
                            className="mt-2 h-1.5 rounded-full overflow-hidden"
                            style={{ background: "#E2E8F0" }}
                          >
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: `${cs.weight > 0 ? (cs.score / cs.weight) * 100 : 0}%`,
                                background: criteriaColor(cs.score, cs.weight),
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Issues */}
              {evalDetail.issues && evalDetail.issues.length > 0 && (
                <div>
                  <h3
                    className="text-sm font-bold mb-3"
                    style={{ color: "#0A1F44" }}
                  >
                    Vấn đề phát hiện ({evalDetail.issues.length})
                  </h3>
                  <div className="space-y-2">
                    {evalDetail.issues.map((issue: any, i: number) => (
                      <div
                        key={i}
                        className="rounded-xl p-4"
                        style={{
                          background: "#FFFFFF",
                          border: "1px solid #E2E8F0",
                        }}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className="text-xs font-bold px-2 py-0.5 rounded"
                            style={{
                              color:
                                issue.severity === "critical"
                                  ? "#EF4444"
                                  : issue.severity === "major"
                                    ? "#F59E0B"
                                    : "#94a3b8",
                              background:
                                issue.severity === "critical"
                                  ? "rgba(239,68,68,0.12)"
                                  : issue.severity === "major"
                                    ? "rgba(245,158,11,0.12)"
                                    : "rgba(148,163,184,0.12)",
                            }}
                          >
                            {issue.severity?.toUpperCase()}
                          </span>
                          <span
                            className="text-sm"
                            style={{ color: "#9CA3AF" }}
                          >
                            {issue.section}
                          </span>
                        </div>
                        <p className="text-sm" style={{ color: "#374151" }}>
                          {issue.issue}
                        </p>
                        {issue.recommendation && (
                          <p
                            className="text-sm mt-1.5"
                            style={{ color: "#0A1F44" }}
                          >
                            → {issue.recommendation}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Strengths */}
              {evalDetail.strengths && evalDetail.strengths.length > 0 && (
                <div>
                  <h3
                    className="text-sm font-bold mb-3"
                    style={{ color: "#0A1F44" }}
                  >
                    Điểm mạnh
                  </h3>
                  <div className="space-y-1.5">
                    {evalDetail.strengths.map((s: string, i: number) => (
                      <div
                        key={i}
                        className="grid gap-2 text-sm"
                        style={{
                          gridTemplateColumns: "auto 1fr",
                          color: "#6B7280",
                        }}
                      >
                        <span style={{ color: "#0A1F44" }}>✓</span>
                        {s}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {evalDetail.recommendations &&
                evalDetail.recommendations.length > 0 && (
                  <div>
                    <h3
                      className="text-sm font-bold mb-3"
                      style={{ color: "#0A1F44" }}
                    >
                      Đề xuất cải thiện
                    </h3>
                    <div className="space-y-1.5">
                      {evalDetail.recommendations.map(
                        (r: string, i: number) => (
                          <div
                            key={i}
                            className="grid gap-2 text-sm"
                            style={{
                              gridTemplateColumns: "auto 1fr",
                              color: "#6B7280",
                            }}
                          >
                            <span style={{ color: "#F59E0B" }}>→</span>
                            {r}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}

              {/* Signature */}
              {evalDetail.signature_detection && (
                <div>
                  <h3
                    className="text-sm font-bold mb-3"
                    style={{ color: "#0A1F44" }}
                  >
                    Chữ ký & Con dấu
                  </h3>
                  <div
                    className="rounded-xl p-4"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      borderLeftWidth: 3,
                      borderLeftColor:
                        evalDetail.signature_detection.signature_status ===
                        "confirmed"
                          ? "#0A1F44"
                          : evalDetail.signature_detection.signature_status ===
                              "likely"
                            ? "#0EA5E9"
                            : evalDetail.signature_detection
                                  .signature_status === "placeholder"
                              ? "#EF4444"
                              : "#94A3B8",
                    }}
                  >
                    <p className="text-sm" style={{ color: "#374151" }}>
                      {evalDetail.signature_detection.summary}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* ── History Modal ── */}
      {historyData && (
        <Modal>
          <div
            className="w-full max-w-[calc(100vw-2rem)] md:max-w-2xl rounded-2xl flex flex-col animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
              boxShadow: "0 25px 60px rgba(0,0,0,0.1)",
            }}
          >
            <div
              className="px-6 py-5 flex-shrink-0"
              style={{
                borderBottom: "1px solid #E2E8F0",
                background: "#FFFFFF",
              }}
            >
              <div
                className="grid items-center gap-3"
                style={{ gridTemplateColumns: "1fr auto" }}
              >
                <div>
                  <h2
                    className="text-base font-bold"
                    style={{ color: "#0A1F44" }}
                  >
                    Lịch sử —{" "}
                    {historyData.doc_type_label || historyData.doc_type}
                  </h2>
                  <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
                    {historyData.total} phiên bản
                  </p>
                </div>
                <button
                  onClick={() => setHistoryData(null)}
                  className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                  style={{ background: "rgba(0,0,0,0.05)" }}
                >
                  <span style={{ color: "#6B7280" }}>✕</span>
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto">
              {historyData.revisions.map((rev, i) => {
                const st = STATUS_CONFIG[rev.overall_status || ""];
                const isLatest = i === 0;
                return (
                  <div
                    key={rev.id}
                    className="px-6 py-4 transition-all hover:bg-black/[0.02]"
                    style={{ borderBottom: "1px solid #E2E8F0" }}
                  >
                    <div
                      className="grid items-center gap-4"
                      style={{ gridTemplateColumns: "auto auto 1fr auto auto" }}
                    >
                      {/* Version number */}
                      <div
                        className="w-8 h-8 rounded-lg grid place-items-center text-xs font-bold flex-shrink-0"
                        style={{
                          background: isLatest
                            ? "rgba(10,31,68,0.15)"
                            : "rgba(100,116,139,0.1)",
                          color: isLatest ? "#0A1F44" : "#6B7280",
                          border: isLatest
                            ? "1px solid rgba(10,31,68,0.3)"
                            : "1px solid rgba(100,116,139,0.2)",
                        }}
                      >
                        v{historyData.total - i}
                      </div>
                      <MiniScore score={rev.compliance_score} />
                      <div>
                        <div className="grid grid-flow-col items-center gap-2 justify-start">
                          <p
                            className="text-sm font-medium"
                            style={{ color: "#0A1F44" }}
                          >
                            {rev.original_filename}
                          </p>
                          {isLatest && (
                            <span
                              className="text-xs px-2 py-0.5 rounded-full font-medium"
                              style={{
                                background: "rgba(10,31,68,0.15)",
                                color: "#0A1F44",
                              }}
                            >
                              Hiện tại
                            </span>
                          )}
                        </div>
                        <div
                          className="grid grid-flow-col items-center gap-2 mt-1 justify-start text-sm"
                          style={{ color: "#6B7280" }}
                        >
                          <span>
                            {new Date(rev.uploaded_at).toLocaleString("vi-VN", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                          <span>·</span>
                          <span>{formatSize(rev.file_size)}</span>
                        </div>
                      </div>
                      {st && (
                        <span
                          className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.bg, color: st.color }}
                        >
                          {st.label}
                        </span>
                      )}
                      <div className="grid grid-flow-col gap-2">
                        <button
                          onClick={() => openView(rev.id)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ease-out hover:scale-105"
                          style={{
                            background: "rgba(14,165,233,0.1)",
                            color: "#0EA5E9",
                            border: "1px solid rgba(14,165,233,0.2)",
                          }}
                        >
                          Xem
                        </button>
                        {!isLatest && (
                          <button
                            onClick={() =>
                              handlePromote(rev.id, historyData.doc_type)
                            }
                            disabled={promotingId === rev.id}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ease-out hover:scale-105"
                            style={{
                              background: "rgba(245,158,11,0.1)",
                              color: "#F59E0B",
                              border: "1px solid rgba(245,158,11,0.2)",
                            }}
                          >
                            {promotingId === rev.id ? "..." : "Lựa chọn"}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Modal>
      )}

      {/* ── Submit Modal ── */}
      {showSubmit && (
        <Modal>
          <div
            className="w-full max-w-lg rounded-2xl flex flex-col animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
              boxShadow: "0 25px 60px rgba(0,0,0,0.1)",
            }}
          >
            <div
              className="px-6 py-5 flex-shrink-0"
              style={{
                borderBottom: "1px solid #E2E8F0",
                background: "#FFFFFF",
              }}
            >
              <div
                className="grid items-center gap-3"
                style={{ gridTemplateColumns: "1fr auto" }}
              >
                <div>
                  <h2
                    className="text-base font-bold"
                    style={{ color: "#0A1F44" }}
                  >
                    Gửi hồ sơ đến tổ chức chứng nhận
                  </h2>
                  <p className="text-sm mt-1" style={{ color: "#9CA3AF" }}>
                    Chọn tổ chức và tài liệu cần gửi
                  </p>
                </div>
                <button
                  onClick={() => setShowSubmit(false)}
                  className="w-8 h-8 rounded-lg grid place-items-center"
                  style={{ background: "rgba(0,0,0,0.05)" }}
                >
                  <span style={{ color: "#6B7280" }}>✕</span>
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
              {/* Provider select */}
              <div>
                <label
                  className="text-xs font-medium mb-1.5 block"
                  style={{ color: "#6B7280" }}
                >
                  Tổ chức chứng nhận *
                </label>
                {providers.length === 0 ? (
                  <p className="text-sm" style={{ color: "#6B7280" }}>
                    Chưa có tổ chức nào trong hệ thống
                  </p>
                ) : (
                  <div className="space-y-2">
                    {providers.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => setSelectedProvider(p.id)}
                        className="w-full grid items-center gap-3 px-4 py-3 rounded-xl text-left transition-all"
                        style={{
                          gridTemplateColumns: "auto 1fr",
                          background:
                            selectedProvider === p.id
                              ? "rgba(14,165,233,0.08)"
                              : "#FFFFFF",
                          border: `1px solid ${selectedProvider === p.id ? "rgba(14,165,233,0.4)" : "#E2E8F0"}`,
                        }}
                      >
                        <div
                          className="w-8 h-8 rounded-lg grid place-items-center"
                          style={{
                            background: "rgba(14,165,233,0.15)",
                            color: "#0EA5E9",
                          }}
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                            />
                          </svg>
                        </div>
                        <div>
                          <p
                            className="text-sm font-medium"
                            style={{ color: "#0A1F44" }}
                          >
                            {p.company_name}
                          </p>
                          <p className="text-xs" style={{ color: "#6B7280" }}>
                            {p.email}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Document selection */}
              <div>
                <label
                  className="text-xs font-medium mb-1.5 block"
                  style={{ color: "#6B7280" }}
                >
                  Tài liệu gửi ({selectedDocs.size}/{docs.length})
                </label>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {docs.map((doc) => (
                    <label
                      key={doc.id}
                      className="grid items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all"
                      style={{
                        gridTemplateColumns: "auto 1fr auto",
                        background: selectedDocs.has(doc.id)
                          ? "rgba(10,31,68,0.08)"
                          : "#FFFFFF",
                        border: `1px solid ${selectedDocs.has(doc.id) ? "rgba(10,31,68,0.25)" : "#E2E8F0"}`,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocs.has(doc.id)}
                        onChange={(e) => {
                          const next = new Set(selectedDocs);
                          e.target.checked
                            ? next.add(doc.id)
                            : next.delete(doc.id);
                          setSelectedDocs(next);
                        }}
                        className="rounded"
                      />
                      <span
                        className="text-sm truncate"
                        style={{ color: "#0A1F44" }}
                      >
                        {doc.original_filename}
                      </span>
                      <span className="text-xs" style={{ color: "#6B7280" }}>
                        {doc.doc_type_label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <label
                  className="text-xs font-medium mb-1.5 block"
                  style={{ color: "#6B7280" }}
                >
                  Ghi chú (tuỳ chọn)
                </label>
                <textarea
                  value={submitNotes}
                  onChange={(e) => setSubmitNotes(e.target.value)}
                  placeholder="Thông tin thêm cho tổ chức chứng nhận..."
                  rows={3}
                  className="w-full px-4 py-3 rounded-xl text-sm outline-none resize-none"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    color: "#0A1F44",
                  }}
                />
              </div>
            </div>

            <div
              className="px-6 py-4 flex-shrink-0"
              style={{ borderTop: "1px solid #E2E8F0" }}
            >
              <button
                onClick={handleSubmit}
                disabled={
                  submitting || !selectedProvider || selectedDocs.size === 0
                }
                className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all"
                style={{
                  background:
                    !selectedProvider || selectedDocs.size === 0
                      ? "#E2E8F0"
                      : "linear-gradient(135deg, #1d4ed8, #2563eb)",
                  boxShadow:
                    selectedProvider && selectedDocs.size > 0
                      ? "0 4px 15px rgba(37,99,235,0.3)"
                      : "none",
                  color:
                    !selectedProvider || selectedDocs.size === 0
                      ? "#6B7280"
                      : "white",
                }}
              >
                {submitting
                  ? "Đang gửi..."
                  : `Gửi ${selectedDocs.size} tài liệu`}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Upload Modal ── */}
      {showUpload && (
        <Modal onClose={() => setShowUpload(false)}>
          <div
            className="w-full max-w-[calc(100vw-2rem)] md:max-w-2xl rounded-2xl animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
              boxShadow: "0 25px 60px rgba(0,0,0,0.1)",
            }}
          >
            {/* Header */}
            <div
              className="px-6 py-4 flex items-center justify-between"
              style={{ borderBottom: "1px solid #E2E8F0" }}
            >
              <h2 className="text-lg font-bold" style={{ color: "#0A1F44" }}>
                Upload tài liệu
              </h2>
              <button
                onClick={() => {
                  setShowUpload(false);
                  setUploadDocType(null);
                  setUploadError("");
                  setSopExpanded(false);
                }}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: "rgba(0,0,0,0.05)" }}
              >
                <span style={{ color: "#6B7280" }}>✕</span>
              </button>
            </div>

            {/* Body */}
            <div
              className="px-6 py-5 space-y-5 overflow-y-auto"
              style={{ maxHeight: "calc(100vh - 12rem)" }}
            >
              {/* Step 1: Select doc type */}
              <div>
                <h3
                  className="text-sm font-semibold mb-3"
                  style={{ color: "#0A1F44" }}
                >
                  1. Chọn loại tài liệu
                </h3>
                <div
                  className="grid gap-2"
                  style={{
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(160px, 1fr))",
                  }}
                >
                  {DOC_TYPE_OPTIONS.map((dt) => (
                    <button
                      key={dt.id}
                      onClick={() => setUploadDocType(dt.id)}
                      className="text-left px-3 py-2.5 rounded-lg text-xs font-medium transition-all"
                      style={{
                        background:
                          uploadDocType === dt.id
                            ? "rgba(10,31,68,0.08)"
                            : "#FFFFFF",
                        border: `1.5px solid ${uploadDocType === dt.id ? "#0A1F44" : "#E2E8F0"}`,
                        color: uploadDocType === dt.id ? "#0A1F44" : "#6B7280",
                      }}
                    >
                      {dt.label}
                    </button>
                  ))}
                </div>

                {/* SOP group */}
                <button
                  onClick={() => setSopExpanded(!sopExpanded)}
                  className="mt-2 flex items-center gap-2 text-xs font-medium px-3 py-2 rounded-lg transition-all"
                  style={{
                    color: "#a78bfa",
                    background: "rgba(167,139,250,0.06)",
                    border: "1px solid rgba(167,139,250,0.15)",
                  }}
                >
                  SOP Documents
                  <svg
                    className={`w-3 h-3 transition-transform ${sopExpanded ? "rotate-180" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>
                {sopExpanded && (
                  <div
                    className="grid gap-2 mt-2"
                    style={{
                      gridTemplateColumns:
                        "repeat(auto-fill, minmax(160px, 1fr))",
                    }}
                  >
                    {SOP_SUB_OPTIONS.map((dt) => (
                      <button
                        key={dt.id}
                        onClick={() => setUploadDocType(dt.id)}
                        className="text-left px-3 py-2.5 rounded-lg text-xs font-medium transition-all"
                        style={{
                          background:
                            uploadDocType === dt.id
                              ? "rgba(167,139,250,0.1)"
                              : "#FFFFFF",
                          border: `1.5px solid ${uploadDocType === dt.id ? "#a78bfa" : "#E2E8F0"}`,
                          color:
                            uploadDocType === dt.id ? "#6366F1" : "#6B7280",
                        }}
                      >
                        {dt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Step 2: Dropzone */}
              <div>
                <h3
                  className="text-sm font-semibold mb-3"
                  style={{ color: "#0A1F44" }}
                >
                  2. Chọn file
                </h3>
                {!uploadDocType ? (
                  <div
                    className="rounded-xl p-8 text-center text-xs"
                    style={{
                      background: "#FFFFFF",
                      border: "1px dashed #E2E8F0",
                      color: "#6B7280",
                    }}
                  >
                    Vui lòng chọn loại tài liệu trước
                  </div>
                ) : (
                  <div
                    {...dropzone.getRootProps()}
                    className="rounded-xl p-8 text-center cursor-pointer transition-all"
                    style={{
                      background: dropzone.isDragActive
                        ? "rgba(10,31,68,0.05)"
                        : "#FFFFFF",
                      border: `2px dashed ${dropzone.isDragActive ? "#0A1F44" : "#E2E8F0"}`,
                    }}
                  >
                    <input {...dropzone.getInputProps()} />
                    {uploading ? (
                      <div className="space-y-2">
                        <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin mx-auto" />
                        <p className="text-sm" style={{ color: "#6B7280" }}>
                          Đang upload...
                        </p>
                      </div>
                    ) : (
                      <>
                        <svg
                          className="w-10 h-10 mx-auto mb-3"
                          style={{ color: "#E2E8F0" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="1.5"
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                        <p
                          className="text-sm font-medium"
                          style={{ color: "#0A1F44" }}
                        >
                          Kéo thả file hoặc click để chọn
                        </p>
                        <p
                          className="text-xs mt-1"
                          style={{ color: "#6B7280" }}
                        >
                          PDF, DOCX, PPTX, ODT, TXT, MD (tối đa 50MB)
                        </p>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Upload error */}
              {uploadError && (
                <div
                  className="px-4 py-3 rounded-xl text-sm"
                  style={{
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.2)",
                    color: "#EF4444",
                  }}
                >
                  {uploadError}
                </div>
              )}
            </div>
          </div>
        </Modal>
      )}

      {/* ── Eval Language Modal ── */}
      {evalLangModal && (
        <Modal onClose={() => setEvalLangModal(null)}>
          <div
            className="w-full max-w-sm rounded-2xl p-6 animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 25px 60px rgba(0,0,0,0.1)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              className="text-base font-bold mb-2"
              style={{ color: "#0A1F44" }}
            >
              Chọn ngôn ngữ đánh giá
            </h3>
            <p className="text-xs mb-4" style={{ color: "#9CA3AF" }}>
              AI sẽ sử dụng tài liệu mẫu tham chiếu theo ngôn ngữ bạn chọn
            </p>
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: "1fr 1fr" }}
            >
              <button
                onClick={() => handleEvaluate(evalLangModal, "vi")}
                className="rounded-xl p-4 text-left transition-all duration-200 ease-out hover:scale-[1.02]"
                style={{
                  background: "rgba(239,68,68,0.06)",
                  border: "2px solid rgba(239,68,68,0.2)",
                }}
              >
                <div className="text-lg mb-1">🇻🇳</div>
                <div
                  className="text-sm font-semibold"
                  style={{ color: "#0A1F44" }}
                >
                  Tiếng Việt
                </div>
              </button>
              <button
                onClick={() => handleEvaluate(evalLangModal, "en")}
                className="rounded-xl p-4 text-left transition-all duration-200 ease-out hover:scale-[1.02]"
                style={{
                  background: "rgba(14,165,233,0.06)",
                  border: "2px solid rgba(14,165,233,0.2)",
                }}
              >
                <div className="text-lg mb-1">🇬🇧</div>
                <div
                  className="text-sm font-semibold"
                  style={{ color: "#0A1F44" }}
                >
                  English
                </div>
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
