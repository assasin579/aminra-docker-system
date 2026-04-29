"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import RevisionPanel from "@/components/submissions/RevisionPanel";
import SlaBadge from "@/components/submissions/SlaBadge";
import { openAuthed } from "@/lib/authedOpen";
import { parseApiError } from "@/lib/apiError";

interface Submission {
  id: string;
  business_tenant?: string;
  company_name: string;
  status: string;
  notes: string | null;
  auditor_notes: string | null;
  doc_count: number;
  document_ids: string[];
  auditor_id: string | null;
  auditor_name: string | null;
  submitted_at: string;
  updated_at: string;
  deadline: string | null;
  // Business view fields
  provider_name?: string;
  provider_email?: string;
}

interface SubDoc {
  id: string;
  original_filename: string;
  doc_type: string | null;
  doc_type_label: string | null;
  compliance_score: number | null;
  overall_status: string | null;
  file_size: number | null;
  uploaded_at: string;
}

interface EvalData {
  checklist: { criteria: string; checked: boolean }[];
  score: number;
  notes: string;
}

interface CertResult {
  cert_number: string;
  pdf_url: string;
}

const HALAL_CHECKLIST = [
  "Nguyên liệu có nguồn gốc Halal",
  "Không sử dụng chất cấm (rượu, mỡ lợn...)",
  "Dụng cụ chế biến được vệ sinh Halal",
  "Quy trình sản xuất tuân thủ Halal",
  "Nhân viên được đào tạo về Halal",
  "Bao bì và nhãn mác đúng quy định",
  "Lưu trữ và vận chuyển riêng biệt",
  "Hệ thống truy xuất nguồn gốc",
];

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> =
  {
    pending: {
      label: "Chờ được audit",
      color: "#F59E0B",
      bg: "rgba(245,158,11,0.12)",
    },
    assigned: { label: "Đã gán auditor", color: "#0EA5E9", bg: "#E0F2FE" },
    reviewing: {
      label: "Đang đánh giá",
      color: "#0EA5E9",
      bg: "rgba(14,165,233,0.12)",
    },
    returned: {
      label: "Cần bổ sung",
      color: "#f87171",
      bg: "rgba(239,68,68,0.12)",
    },
    approved: {
      label: "Đã được duyệt bởi CB",
      color: "#0A1F44",
      bg: "rgba(10,31,68,0.12)",
    },
  };

function scoreColor(s: number | null) {
  if (s === null) return "#6B7280";
  if (s >= 75) return "#0A1F44";
  if (s >= 50) return "#F59E0B";
  return "#f87171";
}

export default function SubmissionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  const [subs, setSubs] = useState<Submission[]>([]);
  const [fetching, setFetching] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Provider folder view: group by company.
  // Reads `?company=...` so deep links from /portfolio land directly on the
  // company folder. Initialize once from URL — back button clears via setter
  // (we deliberately don't re-sync on URL changes so "Quay lại" works).
  const [selectedCompany, setSelectedCompany] = useState<string | null>(
    () => searchParams?.get("company") ?? null,
  );
  const [subDocs, setSubDocs] = useState<SubDoc[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [auditorScore, setAuditorScore] = useState<{
    score: number | null;
    notes: string | null;
  }>({ score: null, notes: null });
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  // Certificate state
  const [certModal, setCertModal] = useState<string | null>(null);
  const [certResult, setCertResult] = useState<CertResult | null>(null);
  const [issuingCert, setIssuingCert] = useState(false);
  const [certExpiryMonths, setCertExpiryMonths] = useState(12);
  const [certNotes, setCertNotes] = useState("");

  // Evaluation state
  const [evaluation, setEvaluation] = useState<Record<string, EvalData>>({});
  const [savingEval, setSavingEval] = useState(false);
  const [evalOpen, setEvalOpen] = useState<string | null>(null);
  const [approvingFinal, setApprovingFinal] = useState(false);

  // Reupload + Finalize state (business)
  const [reuploadDocId, setReuploadDocId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const reuploadRef = useRef<HTMLInputElement>(null);
  const [finalizing, setFinalizing] = useState(false);

  // Revision history (business)
  const [revisionDocType, setRevisionDocType] = useState<string | null>(null);
  const [revisions, setRevisions] = useState<
    Array<{
      id: string;
      original_filename: string;
      compliance_score: number | null;
      overall_status: string | null;
      file_size: number | null;
      uploaded_at: string;
    }>
  >([]);
  const [loadingRevisions, setLoadingRevisions] = useState(false);

  // Deadline state
  const [deadlineModal, setDeadlineModal] = useState<string | null>(null);
  const [deadlineValue, setDeadlineValue] = useState("");

  const isBusiness = user?.role === "business";
  const isProvider = user?.role === "provider";

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace("/business/login");
    if (!loading && isAuthenticated && !isBusiness && !isProvider)
      router.replace("/");
  }, [loading, isAuthenticated, user, router, isBusiness, isProvider]);

  const [auditors, setAuditors] = useState<
    Array<{ id: string; display_name: string; specialty: string | null }>
  >([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);

  // Fetch auditors for assignment dropdown (provider only)
  useEffect(() => {
    if (!token || !isAuthenticated || !isProvider) return;
    fetch("/api/auth/provider/auditors", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setAuditors(d.auditors || []))
      .catch(() => {});
  }, [token, isAuthenticated, user]);

  const assignAuditor = async (subId: string, auditorId: string) => {
    setAssigningId(subId);
    try {
      await fetch(`/api/api/submissions/received/${subId}/assign`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ auditor_id: auditorId }),
      });
      fetchSubs();
    } finally {
      setAssigningId(null);
    }
  };

  const fetchSubs = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const endpoint = isBusiness
        ? "/api/api/submissions/my-submissions"
        : "/api/api/submissions/received";
      const res = await fetch(endpoint, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setSubs(d.submissions || []);
      }
    } finally {
      setFetching(false);
    }
  }, [token, isBusiness]);

  useEffect(() => {
    if (isAuthenticated) fetchSubs();
  }, [isAuthenticated, fetchSubs]);

  const toggleExpand = async (id: string) => {
    if (expanded === id) {
      setExpanded(null);
      return;
    }
    setExpanded(id);
    setLoadingDocs(true);
    try {
      const [docsRes, evalRes] = await Promise.all([
        fetch(`/api/api/submissions/received/${id}/documents`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`/api/api/submissions/received/${id}/evaluation`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);
      if (docsRes.ok) {
        const d = await docsRes.json();
        setSubDocs(d.documents || []);
        setAuditorScore({
          score: d.auditor_score ?? null,
          notes: d.auditor_notes ?? null,
        });
      }
      const defaultChecklist = HALAL_CHECKLIST.map((c) => ({
        criteria: c,
        checked: false,
      }));
      if (evalRes.ok) {
        const d = await evalRes.json();
        if (d.evaluation) {
          // Merge saved checklist with full template — keep saved checked states, add missing items
          const savedMap = new Map(
            (d.evaluation.checklist || []).map(
              (c: { criteria: string; checked: boolean }) => [
                c.criteria,
                c.checked,
              ],
            ),
          );
          const mergedChecklist = defaultChecklist.map((item) => ({
            criteria: item.criteria,
            checked:
              (savedMap.has(item.criteria)
                ? savedMap.get(item.criteria)
                : false) ?? false,
          }));
          setEvaluation((prev) => ({
            ...prev,
            [id]: { ...d.evaluation, checklist: mergedChecklist },
          }));
        } else {
          setEvaluation((prev) => ({
            ...prev,
            [id]: { checklist: defaultChecklist, score: 0, notes: "" },
          }));
        }
      } else {
        setEvaluation((prev) => ({
          ...prev,
          [id]: { checklist: defaultChecklist, score: 0, notes: "" },
        }));
      }
    } finally {
      setLoadingDocs(false);
    }
  };

  // Business: open revision history for a doc
  const openRevisions = async (subId: string, docType: string) => {
    if (!token || !docType) return;
    setRevisionDocType(docType);
    setLoadingRevisions(true);
    try {
      const res = await fetch(
        `/api/api/submissions/received/${subId}/doc-revisions/${encodeURIComponent(docType)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (res.ok) {
        const d = await res.json();
        setRevisions(d.revisions || []);
      }
    } finally {
      setLoadingRevisions(false);
    }
  };

  // Business: select a specific revision to use in submission
  const selectRevision = async (
    subId: string,
    oldDocId: string,
    newDocId: string,
  ) => {
    if (!token) return;
    try {
      const res = await fetch(
        `/api/api/submissions/received/${subId}/replace-document`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ old_doc_id: oldDocId, new_doc_id: newDocId }),
        },
      );
      if (res.ok) {
        setRevisionDocType(null);
        // Reload expanded submission
        const eid = expanded;
        setExpanded(null);
        setTimeout(() => {
          if (eid) toggleExpand(eid);
        }, 100);
      }
    } catch {}
  };

  // Business: reupload a document in submission
  const handleReupload = async (
    subId: string,
    oldDocId: string,
    file: File,
    docType: string | null,
  ) => {
    if (!token || !file) return;
    setUploading(true);
    try {
      // 1. Upload new revision
      const form = new FormData();
      form.append("file", file);
      if (docType) form.append("doc_type", docType);
      const uploadRes = await fetch("/api/api/documents/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!uploadRes.ok) {
        const e = await uploadRes.json().catch(() => ({}));
        alert(e.detail || "Upload thất bại");
        return;
      }
      const { id: newDocId } = await uploadRes.json();

      // 2. Replace in submission
      const replaceRes = await fetch(
        `/api/api/submissions/received/${subId}/replace-document`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ old_doc_id: oldDocId, new_doc_id: newDocId }),
        },
      );
      if (!replaceRes.ok) {
        const e = await replaceRes.json().catch(() => ({}));
        alert(e.detail || "Cập nhật thất bại");
        return;
      }

      // 3. Refresh docs
      toggleExpand(subId); // re-expand to reload
      setTimeout(() => toggleExpand(subId), 100);
    } finally {
      setUploading(false);
    }
  };

  // Business: finalize approved submission
  const handleFinalize = async (subId: string) => {
    if (
      !confirm(
        "Lưu tài liệu đã được duyệt và hoàn tất hồ sơ này? Hồ sơ sẽ được xóa khỏi danh sách.",
      )
    )
      return;
    setFinalizing(true);
    try {
      const res = await fetch(
        `/api/api/submissions/received/${subId}/finalize`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Thất bại");
        return;
      }
      fetchSubs(); // refresh list — this submission will be gone
      setExpanded(null);
    } finally {
      setFinalizing(false);
    }
  };

  const issueCertificate = async (businessTenantId: string) => {
    setIssuingCert(true);
    try {
      const res = await fetch(
        `/api/api/submissions/issue-certificate/${businessTenantId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            expiry_months: certExpiryMonths,
            notes: certNotes,
          }),
        },
      );
      if (res.ok) {
        const d = await res.json();
        setCertResult(d);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(parseApiError(err, "Cấp chứng nhận thất bại"));
      }
    } finally {
      setIssuingCert(false);
    }
  };

  const saveEvaluation = async (subId: string) => {
    const evalData = evaluation[subId];
    if (!evalData) return;
    setSavingEval(true);
    try {
      const res = await fetch(
        `/api/api/submissions/received/${subId}/evaluation`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(evalData),
        },
      );
      if (res.ok) {
        // Refresh submission list (status may have changed) + reload docs (auditor score updated)
        fetchSubs();
        const docsRes = await fetch(
          `/api/api/submissions/received/${subId}/documents`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (docsRes.ok) {
          const d = await docsRes.json();
          setSubDocs(d.documents || []);
          setAuditorScore({
            score: d.auditor_score ?? null,
            notes: d.auditor_notes ?? null,
          });
        }
      }
    } finally {
      setSavingEval(false);
    }
  };

  const approveFinal = async (subId: string) => {
    if (
      !confirm(
        "Xác nhận phê duyệt hồ sơ này? Tất cả tài liệu trong hồ sơ sẽ được đánh dấu CB-approved. Đây là bước trước khi cấp chứng nhận — không phải cấp chứng nhận.",
      )
    )
      return;
    setApprovingFinal(true);
    try {
      const res = await fetch(
        `/api/api/submissions/received/${subId}/approve-final`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      if (res.ok) {
        fetchSubs();
        setExpanded(null);
        setEvalOpen(null);
      } else {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Phê duyệt thất bại");
      }
    } finally {
      setApprovingFinal(false);
    }
  };

  const setDeadline = async (subId: string) => {
    if (!deadlineValue) return;
    try {
      await fetch(`/api/api/submissions/received/${subId}/deadline`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          deadline: new Date(deadlineValue).toISOString(),
        }),
      });
      setDeadlineModal(null);
      fetchSubs();
    } catch {}
  };

  const updateStatus = async (id: string, status: string) => {
    setUpdatingId(id);
    try {
      await fetch(`/api/api/submissions/received/${id}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status }),
      });
      fetchSubs();
    } finally {
      setUpdatingId(null);
    }
  };

  const viewDoc = (docId: string) => {
    openAuthed(`/api/api/documents/${docId}/preview`, token || "");
  };

  if (loading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div
            className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
            style={{ animationDelay: "0.15s" }}
          />
          <div
            className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
            style={{ animationDelay: "0.3s" }}
          />
        </div>
      </div>
    );

  return (
    <div
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden"
      data-page
    >
      {/* Header */}
      <div
        className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        <div className="grid grid-flow-col items-center gap-3 justify-start">
          <div
            className="w-10 h-10 rounded-xl grid place-items-center"
            style={{
              background: "rgba(14,165,233,0.15)",
              border: "1px solid rgba(14,165,233,0.3)",
            }}
          >
            <svg
              className="w-5 h-5"
              style={{ color: "#0EA5E9" }}
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
              {isBusiness
                ? "Hồ sơ đã gửi"
                : selectedCompany
                  ? selectedCompany
                  : "Hồ sơ nhận được"}
            </h1>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              {isBusiness
                ? `${subs.length} hồ sơ`
                : selectedCompany
                  ? `${subs.filter((s) => s.company_name === selectedCompany).length} hồ sơ từ ${selectedCompany}`
                  : `${new Set(subs.map((s) => s.company_name)).size} doanh nghiệp · ${subs.length} hồ sơ`}
            </p>
          </div>
        </div>
      </div>

      {/* Provider: Folder view grouped by company */}
      {isProvider &&
        !selectedCompany &&
        !fetching &&
        subs.length > 0 &&
        (() => {
          const grouped: Record<
            string,
            { company: string; subs: typeof subs }
          > = {};
          subs.forEach((s) => {
            const key = s.company_name || "Không rõ";
            if (!grouped[key]) grouped[key] = { company: key, subs: [] };
            grouped[key].subs.push(s);
          });
          const folders = Object.values(grouped).sort((a, b) =>
            a.company.localeCompare(b.company),
          );
          return (
            <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3 mb-4">
              {folders.map((f, idx) => {
                const pending = f.subs.filter(
                  (s) => s.status === "pending" || s.status === "assigned",
                ).length;
                const approved = f.subs.filter(
                  (s) => s.status === "approved",
                ).length;
                const latest = f.subs[0];
                return (
                  <button
                    key={f.company}
                    onClick={() => setSelectedCompany(f.company)}
                    className={`w-full text-left rounded-xl p-4 doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)} transition-all`}
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    <div className="flex items-center gap-4">
                      <div
                        className="w-11 h-11 rounded-full grid place-items-center flex-shrink-0 text-sm font-bold"
                        style={{
                          background: "rgba(10,31,68,0.1)",
                          color: "#0A1F44",
                          border: "1px solid rgba(10,31,68,0.2)",
                        }}
                      >
                        {f.company.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p
                          className="text-sm font-semibold truncate"
                          style={{ color: "#0A1F44" }}
                        >
                          {f.company}
                        </p>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          <span
                            className="text-xs"
                            style={{ color: "#6B7280" }}
                          >
                            {f.subs.length} hồ sơ
                          </span>
                          {pending > 0 && (
                            <span
                              className="px-2 py-0.5 rounded-full text-xs font-medium"
                              style={{
                                background: "#FEF3C7",
                                color: "#D97706",
                              }}
                            >
                              {pending} chờ xử lý
                            </span>
                          )}
                          {approved > 0 && (
                            <span
                              className="px-2 py-0.5 rounded-full text-xs font-medium"
                              style={{
                                background: "#DCE3F0",
                                color: "#0A1F44",
                              }}
                            >
                              {approved} đã duyệt
                            </span>
                          )}
                          {f.subs.length > 0 &&
                            pending === 0 &&
                            approved === f.subs.length && (
                              <span
                                className="px-2 py-0.5 rounded-full text-xs font-bold"
                                style={{
                                  background: "rgba(10,31,68,0.15)",
                                  color: "#0A1F44",
                                }}
                              >
                                ✓ Đủ điều kiện cấp cert
                              </span>
                            )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {user?.is_owner &&
                          f.subs.length > 0 &&
                          pending === 0 &&
                          approved === f.subs.length && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                const bizTenant = f.subs[0]?.business_tenant;
                                if (bizTenant) {
                                  setCertModal(bizTenant);
                                  setCertResult(null);
                                  setCertNotes("");
                                  setCertExpiryMonths(12);
                                }
                              }}
                              className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all hover:scale-105"
                              style={{
                                background: "#C9A24A",
                                color: "#0A1F44",
                                boxShadow: "0 1px 3px rgba(168,130,36,0.3)",
                              }}
                            >
                              ★ Cấp cert
                            </button>
                          )}
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#94A3B8" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          );
        })()}

      {/* Back to folders button (provider) */}
      {isProvider && selectedCompany && (
        <button
          onClick={() => {
            setSelectedCompany(null);
            setExpanded(null);
            // Strip ?company= from URL so a refresh doesn't drop user back into the folder.
            if (
              typeof window !== "undefined" &&
              window.location.search.includes("company=")
            ) {
              window.history.replaceState(null, "", "/submissions");
            }
          }}
          className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg text-sm font-medium transition-all hover:bg-black/5"
          style={{ color: "#0A1F44" }}
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
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Quay lại · {selectedCompany}
        </button>
      )}

      {/* Submissions list (filtered by company for provider, all for business) */}
      <div
        className={`flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3 ${isProvider && !selectedCompany && subs.length > 0 ? "hidden" : ""}`}
      >
        {fetching ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="rounded-2xl h-24 animate-pulse"
                style={{ background: "#F5F1E8", opacity: 1 - i * 0.2 }}
              />
            ))}
          </div>
        ) : subs.length === 0 ? (
          <div
            className="rounded-2xl p-12 text-center"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
              Chưa có hồ sơ nào
            </p>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              Hồ sơ từ doanh nghiệp sẽ xuất hiện tại đây
            </p>
          </div>
        ) : (
          (isProvider && selectedCompany
            ? subs.filter((s) => s.company_name === selectedCompany)
            : subs
          ).map((sub, idx) => {
            const st = STATUS_MAP[sub.status] || STATUS_MAP.pending;
            const isOpen = expanded === sub.id;
            return (
              <div
                key={sub.id}
                className={`rounded-2xl overflow-hidden animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              >
                {/* Header row */}
                <button
                  onClick={() => toggleExpand(sub.id)}
                  className="w-full px-5 py-4 text-left transition-colors hover:bg-black/[0.02]"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-sm font-semibold"
                        style={{ color: "#0A1F44" }}
                      >
                        {isBusiness
                          ? sub.provider_name || "Tổ chức chứng nhận"
                          : sub.company_name || "Doanh nghiệp"}
                      </p>
                      {isBusiness && sub.auditor_name && (
                        <p
                          className="text-xs mt-0.5"
                          style={{ color: "#F59E0B" }}
                        >
                          Auditor: {sub.auditor_name}
                        </p>
                      )}
                      <p
                        className="text-sm mt-0.5"
                        style={{ color: "#6B7280" }}
                      >
                        {sub.doc_count} tài liệu ·{" "}
                        {new Date(sub.submitted_at).toLocaleString("vi-VN", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                      {sub.notes && (
                        <p
                          className="text-sm mt-1"
                          style={{ color: "#6B7280" }}
                        >
                          "{sub.notes}"
                        </p>
                      )}
                      <div className="mt-1.5">
                        <SlaBadge
                          submittedAt={sub.submitted_at}
                          deadline={sub.deadline}
                          status={sub.status}
                        />
                      </div>
                    </div>
                    <span
                      className="px-3 py-1 rounded-full text-xs font-medium"
                      style={{ background: st.bg, color: st.color }}
                    >
                      {st.label}
                    </span>
                    {sub.deadline &&
                      (() => {
                        const daysLeft = Math.ceil(
                          (new Date(sub.deadline).getTime() - Date.now()) /
                            86400000,
                        );
                        const dlColor =
                          daysLeft < 0
                            ? "#f87171"
                            : daysLeft <= 3
                              ? "#F59E0B"
                              : "#0A1F44";
                        const dlBg =
                          daysLeft < 0
                            ? "rgba(239,68,68,0.12)"
                            : daysLeft <= 3
                              ? "rgba(245,158,11,0.12)"
                              : "rgba(10,31,68,0.12)";
                        const dlLabel =
                          daysLeft < 0
                            ? `Quá hạn ${-daysLeft} ngày`
                            : daysLeft === 0
                              ? "Hôm nay"
                              : `Còn ${daysLeft} ngày`;
                        return (
                          <span
                            className="px-2 py-0.5 rounded-full text-xs font-medium"
                            style={{ background: dlBg, color: dlColor }}
                          >
                            ⏰ {dlLabel}
                          </span>
                        );
                      })()}
                    {isProvider &&
                      !sub.deadline &&
                      user?.is_owner &&
                      isOpen && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeadlineModal(sub.id);
                          }}
                          className="px-2 py-0.5 rounded-full text-xs font-medium transition-all hover:scale-105"
                          style={{
                            background: "rgba(14,165,233,0.1)",
                            color: "#0EA5E9",
                            border: "1px solid rgba(14,165,233,0.2)",
                          }}
                        >
                          + Đặt hạn
                        </button>
                      )}
                    {isProvider && sub.deadline && user?.is_owner && isOpen && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeadlineModal(sub.id);
                          setDeadlineValue(sub.deadline!.slice(0, 10));
                        }}
                        className="px-2 py-0.5 rounded-full text-xs font-medium transition-all hover:scale-105"
                        style={{
                          background: "rgba(14,165,233,0.1)",
                          color: "#0EA5E9",
                          border: "1px solid rgba(14,165,233,0.2)",
                        }}
                      >
                        Sửa hạn
                      </button>
                    )}
                    <svg
                      className={`w-4 h-4 transition-transform ${isOpen ? "rotate-180" : ""}`}
                      style={{ color: "#6B7280" }}
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
                  </div>
                </button>

                {/* Expanded content */}
                {isOpen && (
                  <div
                    className="px-5 pb-5"
                    style={{ borderTop: "1px solid #E2E8F0" }}
                  >
                    {/* Status actions — provider only */}
                    {isProvider && (
                      <div className="flex flex-wrap items-center gap-2 py-3">
                        {(["reviewing", "returned", "approved"] as const).map(
                          (s) => {
                            const cfg = STATUS_MAP[s];
                            return (
                              <button
                                key={s}
                                onClick={() => updateStatus(sub.id, s)}
                                disabled={
                                  updatingId === sub.id || sub.status === s
                                }
                                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                                style={{
                                  background:
                                    sub.status === s
                                      ? cfg.bg
                                      : "rgba(0,0,0,0.03)",
                                  color:
                                    sub.status === s ? cfg.color : "#64748b",
                                  border: `1px solid ${sub.status === s ? cfg.color + "40" : "#E2E8F0"}`,
                                  opacity: sub.status === s ? 1 : 0.7,
                                }}
                              >
                                {cfg.label}
                              </button>
                            );
                          },
                        )}
                      </div>
                    )}

                    {/* Assign auditor — provider owner only */}
                    {isProvider && user?.is_owner && (
                      <div className="flex flex-wrap items-center gap-2 pb-3">
                        <span
                          className="text-xs font-medium"
                          style={{ color: "#6B7280" }}
                        >
                          Auditor:
                        </span>
                        {auditors.length === 0 ? (
                          <>
                            <a
                              href="/auditors"
                              className="text-xs"
                              style={{ color: "#0EA5E9" }}
                            >
                              Chưa có auditor — Tạo auditor →
                            </a>
                            <div />
                          </>
                        ) : (
                          <>
                            <select
                              defaultValue={sub.auditor_id || ""}
                              id={`auditor-${sub.id}`}
                              className="text-sm px-3 py-2 rounded-lg outline-none flex-1 min-w-0"
                              style={{
                                background: "#FFFFFF",
                                border: "1px solid #E2E8F0",
                                color: "#0A1F44",
                              }}
                            >
                              <option value="">— Chọn auditor —</option>
                              {auditors.map((a) => (
                                <option key={a.id} value={a.id}>
                                  {a.display_name}
                                  {a.specialty ? ` (${a.specialty})` : ""}
                                </option>
                              ))}
                            </select>
                            <button
                              onClick={() => {
                                const sel = (
                                  document.getElementById(
                                    `auditor-${sub.id}`,
                                  ) as HTMLSelectElement
                                )?.value;
                                if (sel) assignAuditor(sub.id, sel);
                              }}
                              disabled={assigningId === sub.id}
                              className="px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all hover:scale-105"
                              style={{
                                background: "#0A1F44",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {assigningId === sub.id
                                ? "Đang gán..."
                                : "Lưu & Thông báo"}
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    {isProvider && sub.auditor_name && (
                      <p
                        className="text-xs pb-2 flex items-center gap-2"
                        style={{ color: "#F59E0B" }}
                      >
                        <svg
                          className="w-3.5 h-3.5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                          />
                        </svg>
                        Auditor: {sub.auditor_name}
                      </p>
                    )}

                    {/* Auditor evaluation summary */}
                    {auditorScore.score !== null && (
                      <div
                        className="flex items-center gap-3 py-2 px-4 mb-2 rounded-xl"
                        style={{
                          background: "rgba(124,58,237,0.06)",
                          border: "1px solid rgba(124,58,237,0.15)",
                        }}
                      >
                        <svg
                          className="w-4 h-4 flex-shrink-0"
                          style={{ color: "#7C3AED" }}
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
                        <p className="text-sm" style={{ color: "#6B7280" }}>
                          <strong
                            style={{ color: scoreColor(auditorScore.score) }}
                          >
                            Auditor chấm: {auditorScore.score}/100
                          </strong>
                          {auditorScore.notes && (
                            <span> — {auditorScore.notes}</span>
                          )}
                        </p>
                      </div>
                    )}

                    {/* Documents */}
                    {loadingDocs ? (
                      <div className="flex items-center justify-center gap-1.5 py-4">
                        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
                        <div
                          className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                          style={{ animationDelay: "0.15s" }}
                        />
                        <div
                          className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                          style={{ animationDelay: "0.3s" }}
                        />
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {subDocs.map((doc) => (
                          <div
                            key={doc.id}
                            className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-xl"
                            style={{
                              background: "#FFFFFF",
                              border: "1px solid #E2E8F0",
                            }}
                          >
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                {doc.doc_type_label && (
                                  <span
                                    className="px-2 py-0.5 rounded text-xs font-bold"
                                    style={{
                                      background: "rgba(99,102,241,0.12)",
                                      color: "#a5b4fc",
                                    }}
                                  >
                                    {doc.doc_type_label}
                                  </span>
                                )}
                                <p
                                  className="text-sm truncate"
                                  style={{ color: "#0A1F44" }}
                                >
                                  {doc.original_filename}
                                </p>
                              </div>
                            </div>
                            {auditorScore.score !== null && (
                              <span
                                className="text-sm font-bold"
                                style={{
                                  color: scoreColor(auditorScore.score),
                                }}
                              >
                                {auditorScore.score}%
                                <span
                                  className="text-xs font-normal ml-1"
                                  style={{ color: "#7C3AED" }}
                                >
                                  CB
                                </span>
                              </span>
                            )}
                            <div className="flex items-center gap-1.5">
                              {/* Business: reupload button */}
                              {isBusiness && sub.status !== "approved" && (
                                <button
                                  onClick={() => {
                                    setReuploadDocId(doc.id);
                                    setTimeout(
                                      () => reuploadRef.current?.click(),
                                      50,
                                    );
                                  }}
                                  disabled={uploading}
                                  title="Upload phiên bản mới"
                                  className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                  style={{
                                    background: "rgba(245,158,11,0.1)",
                                    border: "1px solid rgba(245,158,11,0.2)",
                                  }}
                                >
                                  <svg
                                    className="w-3.5 h-3.5"
                                    style={{ color: "#F59E0B" }}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth="2"
                                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                                    />
                                  </svg>
                                </button>
                              )}
                              {/* Xem */}
                              <button
                                onClick={() => viewDoc(doc.id)}
                                title="Xem"
                                className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                style={{
                                  background: "rgba(14,165,233,0.1)",
                                  border: "1px solid rgba(14,165,233,0.2)",
                                }}
                              >
                                <svg
                                  className="w-3.5 h-3.5"
                                  style={{ color: "#0EA5E9" }}
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
                              {/* Lịch sử phiên bản */}
                              {doc.doc_type && (
                                <button
                                  onClick={() =>
                                    openRevisions(sub.id, doc.doc_type!)
                                  }
                                  title="Lịch sử phiên bản"
                                  className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                  style={{
                                    background: "rgba(162,28,175,0.08)",
                                    border: "1px solid rgba(162,28,175,0.2)",
                                  }}
                                >
                                  <svg
                                    className="w-3.5 h-3.5"
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
                              {/* Tải xuống */}
                              <button
                                onClick={() =>
                                  openAuthed(
                                    `/api/api/documents/${doc.id}/file`,
                                    token || "",
                                    {
                                      download: true,
                                      filename: doc.original_filename,
                                    },
                                  )
                                }
                                title="Tải xuống"
                                className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                style={{
                                  background: "rgba(10,31,68,0.1)",
                                  border: "1px solid rgba(10,31,68,0.2)",
                                }}
                              >
                                <svg
                                  className="w-3.5 h-3.5"
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
                            </div>
                          </div>
                        ))}
                        {/* Hidden file input for reupload */}
                        <input
                          ref={reuploadRef}
                          type="file"
                          className="hidden"
                          accept=".pdf,.docx,.pptx,.odt,.txt,.md"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file && reuploadDocId && expanded) {
                              const doc = subDocs.find(
                                (d) => d.id === reuploadDocId,
                              );
                              handleReupload(
                                expanded,
                                reuploadDocId,
                                file,
                                doc?.doc_type || null,
                              );
                            }
                            e.target.value = "";
                          }}
                        />
                      </div>
                    )}

                    {/* Certificate button removed — cert issued at company level from folder view */}

                    {/* Business: Save & Finalize when approved */}
                    {isBusiness && sub.status === "approved" && (
                      <div className="pt-3 pb-1">
                        <div
                          className="flex items-center gap-3 p-4 rounded-xl"
                          style={{
                            background: "#DCE3F0",
                            border: "1px solid rgba(10,31,68,0.2)",
                          }}
                        >
                          <svg
                            className="w-5 h-5 flex-shrink-0"
                            style={{ color: "#0A1F44" }}
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
                          <div className="flex-1">
                            <p
                              className="text-sm font-semibold"
                              style={{ color: "#0A1F44" }}
                            >
                              Hồ sơ đã được duyệt bởi CB
                            </p>
                            <p
                              className="text-xs mt-0.5"
                              style={{ color: "#047857" }}
                            >
                              Nhấn "Lưu & Hoàn tất" để cập nhật tài liệu vào hệ
                              thống
                            </p>
                          </div>
                          <button
                            onClick={() => handleFinalize(sub.id)}
                            disabled={finalizing}
                            className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105 active:scale-95 flex-shrink-0"
                            style={{
                              background:
                                "linear-gradient(135deg, #0A1F44, #0A1F44)",
                              boxShadow: "0 4px 12px rgba(10,31,68,0.3)",
                            }}
                          >
                            {finalizing ? "Đang lưu..." : "Lưu & Hoàn tất"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Revision cycle panel — appears for both personas */}
                    {token && (
                      <div className="pt-4">
                        <RevisionPanel
                          submissionId={sub.id}
                          status={sub.status}
                          role={user?.role as "business" | "provider"}
                          token={token}
                          documents={subDocs.map((d) => ({
                            id: d.id,
                            filename: d.original_filename,
                          }))}
                          onChanged={() => fetchSubs()}
                        />
                      </div>
                    )}

                    {/* Evaluation section (collapsible) */}
                    {isProvider && (
                      <div className="pt-4">
                        <button
                          onClick={() =>
                            setEvalOpen(evalOpen === sub.id ? null : sub.id)
                          }
                          className="flex items-center gap-2 text-sm font-semibold transition-colors"
                          style={{ color: "#0A1F44" }}
                        >
                          <svg
                            className={`w-4 h-4 transition-transform ${evalOpen === sub.id ? "rotate-180" : ""}`}
                            style={{ color: "#6B7280" }}
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
                          📋 Đánh giá Halal
                        </button>
                        {evalOpen === sub.id && evaluation[sub.id] && (
                          <div className="mt-3 space-y-3 animate-list-item">
                            <div className="space-y-2">
                              {evaluation[sub.id].checklist.map((item, ci) => (
                                <label
                                  key={ci}
                                  className="flex items-center gap-2 cursor-pointer px-3 py-2 rounded-lg transition-colors hover:bg-black/[0.02]"
                                  style={{
                                    background: item.checked
                                      ? "rgba(10,31,68,0.06)"
                                      : "transparent",
                                  }}
                                >
                                  <input
                                    type="checkbox"
                                    checked={item.checked}
                                    onChange={() => {
                                      setEvaluation((prev) => {
                                        const e = { ...prev[sub.id] };
                                        const cl = [...e.checklist];
                                        cl[ci] = {
                                          ...cl[ci],
                                          checked: !cl[ci].checked,
                                        };
                                        return {
                                          ...prev,
                                          [sub.id]: { ...e, checklist: cl },
                                        };
                                      });
                                    }}
                                    className="w-4 h-4 rounded accent-[#0A1F44]"
                                  />
                                  <span
                                    className="text-sm"
                                    style={{
                                      color: item.checked
                                        ? "#0A1F44"
                                        : "#6B7280",
                                    }}
                                  >
                                    {item.criteria}
                                  </span>
                                </label>
                              ))}
                            </div>
                            <div className="flex items-center gap-3">
                              <label
                                className="text-sm font-medium"
                                style={{ color: "#0A1F44" }}
                              >
                                Điểm:
                              </label>
                              <input
                                type="number"
                                min={0}
                                max={100}
                                value={evaluation[sub.id].score}
                                onChange={(e) =>
                                  setEvaluation((prev) => ({
                                    ...prev,
                                    [sub.id]: {
                                      ...prev[sub.id],
                                      score: Math.min(
                                        100,
                                        Math.max(0, Number(e.target.value)),
                                      ),
                                    },
                                  }))
                                }
                                className="w-20 text-sm px-3 py-2 rounded-lg outline-none text-center font-bold"
                                style={{
                                  background: "#FFFFFF",
                                  border: "1px solid #E2E8F0",
                                  color: scoreColor(evaluation[sub.id].score),
                                }}
                              />
                              <span
                                className="text-sm"
                                style={{ color: "#94a3b8" }}
                              >
                                /100
                              </span>
                            </div>
                            <textarea
                              value={evaluation[sub.id].notes}
                              onChange={(e) =>
                                setEvaluation((prev) => ({
                                  ...prev,
                                  [sub.id]: {
                                    ...prev[sub.id],
                                    notes: e.target.value,
                                  },
                                }))
                              }
                              placeholder="Ghi chú đánh giá..."
                              rows={2}
                              className="w-full text-sm px-3 py-2 rounded-lg outline-none resize-none"
                              style={{
                                background: "#FFFFFF",
                                border: "1px solid #E2E8F0",
                                color: "#0A1F44",
                              }}
                            />
                            <button
                              onClick={() => saveEvaluation(sub.id)}
                              disabled={savingEval}
                              className="px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all hover:scale-105"
                              style={{ background: "#0A1F44" }}
                            >
                              {savingEval ? "Đang lưu..." : "Lưu đánh giá"}
                            </button>

                            {sub.status !== "approved" && (
                              <div
                                className="mt-4 pt-4"
                                style={{ borderTop: "1px solid #E2E8F0" }}
                              >
                                <p
                                  className="text-xs mb-2"
                                  style={{ color: "#94A3B8" }}
                                >
                                  Khi tất cả tài liệu trong hồ sơ đã đạt yêu
                                  cầu, nhấn nút bên dưới để phê duyệt hồ sơ. Cấp
                                  chứng nhận là bước riêng, chỉ thực hiện khi
                                  mọi hồ sơ active của doanh nghiệp đều đã được
                                  phê duyệt:
                                </p>
                                <button
                                  onClick={() => approveFinal(sub.id)}
                                  disabled={approvingFinal}
                                  className="w-full px-5 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:scale-[1.02] active:scale-[0.98]"
                                  style={{
                                    background:
                                      "linear-gradient(135deg, #0A1F44, #0A1F44)",
                                    boxShadow: "0 4px 12px rgba(10,31,68,0.3)",
                                  }}
                                >
                                  {approvingFinal
                                    ? "Đang phê duyệt..."
                                    : "✅ Phê duyệt hồ sơ"}
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Certificate modal */}
      {certModal && (
        <div
          className="fixed inset-0 z-50 grid place-items-center animate-modal-overlay"
          style={{ background: "rgba(0,0,0,0.4)" }}
          onClick={() => setCertModal(null)}
        >
          <div
            className="bg-white rounded-2xl p-6 w-full max-w-md mx-4 animate-modal-content"
            style={{ border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold mb-4" style={{ color: "#0A1F44" }}>
              Cấp chứng nhận Halal
            </h3>
            {certResult ? (
              <div className="space-y-3">
                <div
                  className="p-5 rounded-xl text-center"
                  style={{
                    background:
                      "linear-gradient(135deg, #F2E6C2 0%, #ffffff 100%)",
                    border: "2px solid #C9A24A",
                    boxShadow: "0 4px 16px rgba(201,162,74,0.15)",
                  }}
                >
                  <div
                    className="inline-flex items-center justify-center w-12 h-12 rounded-full mb-2"
                    style={{ background: "#C9A24A" }}
                  >
                    <span className="text-white text-xl">★</span>
                  </div>
                  <p className="text-sm font-bold" style={{ color: "#0A1F44" }}>
                    Chứng nhận Halal đã được cấp
                  </p>
                  <p
                    className="text-base mt-1 font-mono font-bold tracking-wider"
                    style={{ color: "#A88224" }}
                  >
                    {certResult.cert_number}
                  </p>
                </div>
                <button
                  onClick={() =>
                    openAuthed(certResult.pdf_url, token || "", {
                      download: true,
                      filename: `${certResult.cert_number}.pdf`,
                    })
                  }
                  className="block w-full text-center px-4 py-2.5 rounded-lg text-sm font-bold transition-all hover:scale-105"
                  style={{
                    background: "#0A1F44",
                    color: "#C9A24A",
                    border: "1px solid #C9A24A",
                  }}
                >
                  📥 Tải PDF chứng nhận
                </button>
                <button
                  onClick={() => setCertModal(null)}
                  className="w-full px-4 py-2 rounded-lg text-sm font-medium transition-all"
                  style={{
                    background: "#F5F1E8",
                    color: "#6B7280",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  Đóng
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label
                    className="text-sm font-medium block mb-1"
                    style={{ color: "#0A1F44" }}
                  >
                    Thời hạn (tháng)
                  </label>
                  <select
                    value={certExpiryMonths}
                    onChange={(e) =>
                      setCertExpiryMonths(Number(e.target.value))
                    }
                    className="w-full text-sm px-3 py-2 rounded-lg outline-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  >
                    {[6, 12, 18, 24].map((m) => (
                      <option key={m} value={m}>
                        {m} tháng
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    className="text-sm font-medium block mb-1"
                    style={{ color: "#0A1F44" }}
                  >
                    Ghi chú (tuỳ chọn)
                  </label>
                  <textarea
                    value={certNotes}
                    onChange={(e) => setCertNotes(e.target.value)}
                    rows={2}
                    placeholder="Ghi chú thêm..."
                    className="w-full text-sm px-3 py-2 rounded-lg outline-none resize-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setCertModal(null)}
                    className="flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all"
                    style={{
                      background: "#F5F1E8",
                      color: "#6B7280",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    Huỷ
                  </button>
                  <button
                    onClick={() => issueCertificate(certModal)}
                    disabled={issuingCert}
                    className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:scale-105"
                    style={{ background: "#0A1F44" }}
                  >
                    {issuingCert ? "Đang cấp..." : "Xác nhận cấp"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Deadline modal */}
      {deadlineModal && (
        <div
          className="fixed inset-0 z-50 grid place-items-center animate-modal-overlay"
          style={{ background: "rgba(0,0,0,0.4)" }}
          onClick={() => setDeadlineModal(null)}
        >
          <div
            className="bg-white rounded-2xl p-6 w-full max-w-sm mx-4 animate-modal-content"
            style={{ border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold mb-4" style={{ color: "#0A1F44" }}>
              Đặt hạn chót
            </h3>
            <input
              type="date"
              value={deadlineValue}
              onChange={(e) => setDeadlineValue(e.target.value)}
              className="w-full text-sm px-3 py-2 rounded-lg outline-none mb-4"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setDeadlineModal(null)}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all"
                style={{
                  background: "#F5F1E8",
                  color: "#6B7280",
                  border: "1px solid #E2E8F0",
                }}
              >
                Huỷ
              </button>
              <button
                onClick={() => setDeadline(deadlineModal)}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:scale-105"
                style={{ background: "#0A1F44" }}
              >
                Lưu
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Revision history modal */}
      {revisionDocType && (
        <div
          className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)" }}
          onClick={() => setRevisionDocType(null)}
        >
          <div
            className="w-full max-w-lg rounded-2xl flex flex-col animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
              boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="px-5 py-4 flex items-center justify-between flex-shrink-0"
              style={{ borderBottom: "1px solid #E2E8F0" }}
            >
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                Lịch sử phiên bản
              </h3>
              <button
                onClick={() => setRevisionDocType(null)}
                className="w-8 h-8 rounded-lg grid place-items-center hover:bg-black/5"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-2">
              {loadingRevisions ? (
                <div className="flex items-center justify-center gap-2 py-8">
                  <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
                  <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
                  <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
                </div>
              ) : revisions.length === 0 ? (
                <p
                  className="text-sm text-center py-8"
                  style={{ color: "#94A3B8" }}
                >
                  Chưa có phiên bản nào
                </p>
              ) : (
                revisions.map((rev, i) => {
                  const isLatest = i === 0;
                  const isCurrent = subDocs.some((d) => d.id === rev.id);
                  return (
                    <div
                      key={rev.id}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl animate-list-item stagger-${Math.min(i + 1, 12)}`}
                      style={{
                        background: isCurrent
                          ? "rgba(10,31,68,0.06)"
                          : "#FFFFFF",
                        border: `1px solid ${isCurrent ? "rgba(10,31,68,0.2)" : "#E2E8F0"}`,
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className="text-xs font-bold px-1.5 py-0.5 rounded"
                            style={{ background: "#F3F4F6", color: "#6B7280" }}
                          >
                            v{revisions.length - i}
                          </span>
                          {isLatest && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                background: "#DBEAFE",
                                color: "#2563EB",
                              }}
                            >
                              Mới nhất
                            </span>
                          )}
                          {isCurrent && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded"
                              style={{
                                background: "#DCE3F0",
                                color: "#102A5C",
                              }}
                            >
                              Đang dùng
                            </span>
                          )}
                        </div>
                        <p
                          className="text-sm truncate mt-1"
                          style={{ color: "#0A1F44" }}
                        >
                          {rev.original_filename}
                        </p>
                        <p
                          className="text-xs mt-0.5"
                          style={{ color: "#94A3B8" }}
                        >
                          {new Date(rev.uploaded_at).toLocaleString("vi-VN", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                          {rev.file_size
                            ? ` · ${(rev.file_size / 1024).toFixed(0)} KB`
                            : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button
                          onClick={() => viewDoc(rev.id)}
                          title="Xem"
                          className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                          style={{
                            background: "rgba(14,165,233,0.1)",
                            border: "1px solid rgba(14,165,233,0.2)",
                          }}
                        >
                          <svg
                            className="w-3.5 h-3.5"
                            style={{ color: "#0EA5E9" }}
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
                        {isBusiness && !isCurrent && expanded && (
                          <button
                            onClick={() => {
                              const currentDoc = subDocs.find(
                                (d) => d.doc_type === revisionDocType,
                              );
                              if (currentDoc)
                                selectRevision(expanded, currentDoc.id, rev.id);
                            }}
                            title="Sử dụng phiên bản này"
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:scale-105"
                            style={{ background: "#0A1F44" }}
                          >
                            Chọn
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
