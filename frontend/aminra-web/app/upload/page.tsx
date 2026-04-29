"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";
import GenerateDocTab, {
  type GenerateState,
  INITIAL_GENERATE_STATE,
} from "@/components/GenerateDocTab";

// ─── Document type definitions ────────────────────────────────────────────────

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

// ─── Types ────────────────────────────────────────────────────────────────────

interface EvalIssue {
  section: string;
  severity: "critical" | "major" | "minor";
  issue: string;
  recommendation: string;
  reference: string;
}

interface GapAnalysis {
  critical_gaps: string[];
  major_gaps: string[];
  minor_gaps: string[];
}

interface RiskFlag {
  text_snippet: string;
  risk_type: string;
  severity: "critical" | "high" | "medium" | "low";
  explanation: string;
}

interface Citation {
  standard: string;
  clause: string;
  text: string;
  relevance: string;
}

interface EvaluationReport {
  filename: string;
  doc_type: string;
  doc_type_label: string;
  word_count: number;
  standards_found: number;
  compliance_score: number;
  overall_status: "compliant" | "needs_review" | "non_compliant";
  summary: string;
  issues: EvalIssue[];
  strengths: string[];
  recommendations: string[];
  standards_checked: string[];
  gap_analysis: GapAnalysis | null;
  risk_flags: RiskFlag[];
  citations: Citation[];
  extracted_text?: string;
}

interface FileVersionEntry {
  version: number;
  score: number;
  status: string;
  doc_type_label: string;
  timestamp: string;
  issues_count: number;
  strengths_count: number;
  summary: string;
}

interface AuditorReview {
  reviewer: string;
  notes: string;
  confirmed_issues: string[];
  false_positives: string[];
  additional_findings: string[];
  issue_comments: Record<string, string>;
  final_score: number | null;
  status: "pending" | "approved" | "rejected";
  reviewed_at?: string;
  filename?: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 80) return "#0A1F44";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

function statusLabel(s: string) {
  if (s === "compliant")
    return {
      label: "Tuân thủ",
      color: "#0A1F44",
      bg: "rgba(10,31,68,0.08)",
      border: "rgba(10,31,68,0.25)",
    };
  if (s === "needs_review")
    return {
      label: "Cần xem xét",
      color: "#f59e0b",
      bg: "rgba(245,158,11,0.08)",
      border: "rgba(245,158,11,0.25)",
    };
  return {
    label: "Không tuân thủ",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.08)",
    border: "rgba(239,68,68,0.25)",
  };
}

function severityBadge(sev: string) {
  const map: Record<string, { color: string; bg: string; label: string }> = {
    critical: {
      color: "#ef4444",
      bg: "rgba(239,68,68,0.15)",
      label: "Nghiêm trọng",
    },
    high: { color: "#f97316", bg: "rgba(249,115,22,0.15)", label: "Cao" },
    major: { color: "#f59e0b", bg: "rgba(245,158,11,0.15)", label: "Lớn" },
    medium: {
      color: "#eab308",
      bg: "rgba(234,179,8,0.15)",
      label: "Trung bình",
    },
    minor: { color: "#6B7280", bg: "rgba(91,107,125,0.1)", label: "Nhỏ" },
    low: { color: "#6B7280", bg: "rgba(148,163,184,0.1)", label: "Thấp" },
  };
  return map[sev] ?? map.low;
}

function riskTypeLabel(t: string) {
  const map: Record<string, string> = {
    prohibited_ingredient: "Thành phần cấm",
    contamination: "Nguy cơ nhiễm chéo",
    unclear_sourcing: "Nguồn gốc không rõ",
    process_risk: "Rủi ro quy trình",
    missing_certification: "Thiếu chứng nhận",
    cross_contamination: "Nhiễm chéo",
  };
  return map[t] ?? t;
}

function ScoreDial({ score }: { score: number }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = scoreColor(score);
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle
        cx="70"
        cy="70"
        r={r}
        fill="none"
        stroke="#E2E8F0"
        strokeWidth="12"
      />
      <circle
        cx="70"
        cy="70"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dasharray 1s ease" }}
      />
      <text
        x="70"
        y="66"
        textAnchor="middle"
        fill={color}
        fontSize="28"
        fontWeight="bold"
        fontFamily="monospace"
      >
        {score}
      </text>
      <text
        x="70"
        y="84"
        textAnchor="middle"
        fill="#6B7280"
        fontSize="11"
        fontFamily="sans-serif"
      >
        /100
      </text>
    </svg>
  );
}

const TABS = [
  { id: "overview", label: "Tổng quan", icon: "◎" },
  { id: "gaps", label: "Gap & Rủi ro", icon: "⊟" },
  { id: "citations", label: "Trích dẫn", icon: "§" },
  { id: "history", label: "Lịch sử", icon: "⏱" },
  { id: "auditor", label: "Kiểm toán viên", icon: "✎" },
  { id: "generate", label: "Tạo tài liệu mẫu", icon: "✦" },
  { id: "export", label: "Xuất báo cáo", icon: "↓" },
];

// ─── Main Component ───────────────────────────────────────────────────────────

export default function UploadPage() {
  const API = "/api";
  const { i18n } = useTranslation();
  const { token, isAuthenticated, user } = useUserAuth();
  // Role-based access: logged-in users (business/provider) get full access
  const isFullAccess = isAuthenticated && !!user;
  const isProvider = user?.role === "provider";
  const isBusiness = user?.role === "business";

  const [phase, setPhase] = useState<
    "idle" | "uploading" | "analyzing" | "done"
  >("idle");
  const isProcessing = phase === "uploading" || phase === "analyzing";
  const [analyzeProgress, setAnalyzeProgress] = useState(0);

  // Prevent navigation during upload/analyze
  useEffect(() => {
    if (!isProcessing) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isProcessing]);

  // Intercept client-side navigation via click on <a> tags
  useEffect(() => {
    if (!isProcessing) return;
    const handler = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href") || "";
      if (href.startsWith("/") && href !== "/upload") {
        e.preventDefault();
        e.stopPropagation();
        alert(
          "Đang xử lý tài liệu, vui lòng chờ hoàn tất trước khi chuyển trang.",
        );
      }
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [isProcessing]);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [fileName, setFileName] = useState("");
  const analyzeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Doc type selection
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [sopExpanded, setSopExpanded] = useState(false);

  // F-06: Rewrite state
  const [rewriteLoading, setRewriteLoading] = useState<string | null>(null);
  const [rewrites, setRewrites] = useState<
    Record<
      string,
      { rewritten: string; explanation: string; standards_referenced: string[] }
    >
  >({});

  // Per-file version cache
  const [fileVersions, setFileVersions] = useState<FileVersionEntry[]>([]);
  const [previousReport, setPreviousReport] = useState<EvaluationReport | null>(
    null,
  );
  const [showComingSoon, setShowComingSoon] = useState(false);

  // Extracted text for GenerateDocTab
  const [extractedText, setExtractedText] = useState("");

  // GenerateDocTab persisted state
  const [generateState, setGenerateState] = useState<GenerateState>(
    INITIAL_GENERATE_STATE,
  );

  // F-09: Auditor review
  const [review, setReview] = useState<AuditorReview>({
    reviewer: "",
    notes: "",
    confirmed_issues: [],
    false_positives: [],
    additional_findings: [],
    issue_comments: {},
    final_score: null,
    status: "pending",
  });
  const [reviewSaved, setReviewSaved] = useState(false);
  const [existingReview, setExistingReview] = useState<AuditorReview | null>(
    null,
  );

  const safeKey = (filename: string) =>
    filename.replace(/[^a-zA-Z0-9._-]/g, "_");
  const SESSION_KEY = `aminra_eval_${user?.id || "anon"}`;

  // Restore session on mount or user change
  useEffect(() => {
    // Reset state first
    setPhase("idle");
    setReport(null);
    setFileName("");
    setSelectedDocType(null);
    setFileVersions([]);
    setExtractedText("");
    setGenerateState(INITIAL_GENERATE_STATE);
    setExistingReview(null);
    setActiveTab("overview");
    setRewrites({});
    setReviewSaved(false);
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (saved) {
        const s = JSON.parse(saved);
        if (s.report) {
          setReport(s.report);
          setFileName(s.fileName ?? "");
          setSelectedDocType(s.selectedDocType ?? null);
          setFileVersions(s.fileVersions ?? []);
          setActiveTab(s.activeTab ?? "overview");
          if (s.existingReview) setExistingReview(s.existingReview);
          setExtractedText(s.extractedText ?? "");
          if (s.generateState) setGenerateState(s.generateState);
          setPhase("done");
        }
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  // Persist session whenever result is available
  useEffect(() => {
    if (phase === "done" && report) {
      try {
        sessionStorage.setItem(
          SESSION_KEY,
          JSON.stringify({
            report,
            fileName,
            selectedDocType,
            fileVersions,
            activeTab,
            existingReview,
            extractedText,
            generateState,
          }),
        );
      } catch {}
    }
  }, [
    phase,
    report,
    fileName,
    selectedDocType,
    fileVersions,
    activeTab,
    existingReview,
    extractedText,
    generateState,
    SESSION_KEY,
  ]);

  const saveFileVersion = (
    r: EvaluationReport,
    prevVersions: FileVersionEntry[],
  ) => {
    const entry: FileVersionEntry = {
      version: prevVersions.length + 1,
      score: r.compliance_score,
      status: r.overall_status,
      doc_type_label: r.doc_type_label,
      timestamp: new Date().toISOString(),
      issues_count: r.issues.length,
      strengths_count: r.strengths.length,
      summary: r.summary,
    };
    const updated = [entry, ...prevVersions].slice(0, 10);
    setFileVersions(updated);
    const key = safeKey(r.filename);
    try {
      localStorage.setItem(
        `aminra_file_versions_${key}`,
        JSON.stringify(updated),
      );
      localStorage.setItem(`aminra_full_report_${key}`, JSON.stringify(r));
    } catch {}
  };

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      if (!selectedDocType) {
        setError("Vui lòng chọn loại tài liệu trước khi upload.");
        return;
      }
      if (!isFullAccess && selectedDocType !== "halal_policy") {
        setError(
          "Tài khoản của bạn chỉ được phép upload tài liệu Halal Policy.",
        );
        return;
      }
      setError(null);
      setReport(null);
      setRewrites({});
      setReviewSaved(false);
      setExistingReview(null);
      setGenerateState(INITIAL_GENERATE_STATE);
      setFileName(file.name);
      setActiveTab("overview");

      // Load per-file cache
      const fk = safeKey(file.name);
      let prevReport: EvaluationReport | null = null;
      let prevVersions: FileVersionEntry[] = [];
      try {
        const rv = localStorage.getItem(`aminra_file_versions_${fk}`);
        if (rv) prevVersions = JSON.parse(rv);
        const rr = localStorage.getItem(`aminra_full_report_${fk}`);
        if (rr) prevReport = JSON.parse(rr);
      } catch {}
      setFileVersions(prevVersions);
      setPreviousReport(prevReport);

      // Phase 1: Upload + Ingest (background)
      setPhase("uploading");
      const formData = new FormData();
      formData.append("file", file);
      try {
        await fetch(`${API}/ingest`, { method: "POST", body: formData });
      } catch {}

      // Phase 2: Analyze
      setPhase("analyzing");
      setAnalyzeProgress(0);
      analyzeTimerRef.current = setInterval(() => {
        setAnalyzeProgress((p) => Math.min(p + 2, 88));
      }, 400);

      const evalForm = new FormData();
      evalForm.append("file", file);
      if (selectedDocType) evalForm.append("doc_type", selectedDocType);
      evalForm.append("lang", i18n.language || "vi");
      // Pass previous analysis context → backend uses this to focus on changes
      if (prevReport) {
        evalForm.append(
          "previous_context",
          JSON.stringify({
            previous_score: prevReport.compliance_score,
            previous_status: prevReport.overall_status,
            previous_issues_count: prevReport.issues.length,
            previous_issues_summary: prevReport.issues
              .slice(0, 5)
              .map((i: EvalIssue) => i.issue)
              .join("; "),
          }),
        );
      }
      try {
        // Use catch-all proxy to stream directly to backend (avoids body size limits)
        const uploadHeaders: Record<string, string> = {};
        if (token) uploadHeaders["Authorization"] = `Bearer ${token}`;
        const res = await fetch("/api/evaluate", {
          method: "POST",
          headers: uploadHeaders,
          body: evalForm,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || `HTTP ${res.status}`);
        }
        const data: EvaluationReport = await res.json();
        clearInterval(analyzeTimerRef.current!);
        setAnalyzeProgress(100);
        setTimeout(() => {
          setReport(data);
          setExtractedText(data.extracted_text || "");
          setPhase("done");
          saveFileVersion(data, prevVersions);
          // Load existing review
          fetch(`${API}/reviews/${encodeURIComponent(file.name)}`)
            .then((r) => r.json())
            .then((d) => {
              if (d.exists && d.review) setExistingReview(d.review);
            })
            .catch(() => {});
        }, 400);
      } catch (e) {
        clearInterval(analyzeTimerRef.current!);
        setError(e instanceof Error ? e.message : "Lỗi không xác định");
        setPhase("idle");
      }
    },
    [API, selectedDocType],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        [".pptx"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "application/vnd.oasis.opendocument.text": [".odt"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
  });

  // F-06: Suggest rewrite
  const suggestRewrite = async (
    key: string,
    sectionText: string,
    issue: string,
  ) => {
    setRewriteLoading(key);
    try {
      const res = await fetch(`${API}/rewrite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          section_text: sectionText,
          issue,
          doc_type: report?.doc_type ?? "general",
        }),
      });
      const data = await res.json();
      setRewrites((prev) => ({
        ...prev,
        [key]: {
          rewritten: data.rewritten,
          explanation: data.explanation,
          standards_referenced: data.standards_referenced ?? [],
        },
      }));
    } catch {
      setRewrites((prev) => ({
        ...prev,
        [key]: {
          rewritten: "Không thể tạo gợi ý lúc này.",
          explanation: "",
          standards_referenced: [],
        },
      }));
    } finally {
      setRewriteLoading(null);
    }
  };

  // F-09: Save review
  const saveReview = async () => {
    if (!fileName) return;
    try {
      await fetch(`${API}/reviews/${encodeURIComponent(fileName)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...review,
          filename: fileName,
          reviewed_at: new Date().toISOString(),
        }),
      });
      setReviewSaved(true);
    } catch {}
  };

  // F-10: Export
  const exportReport = () => {
    if (!report) return;
    const html = generateReportHTML(report, existingReview);
    const win = window.open("", "_blank");
    if (win) {
      win.document.write(html);
      win.document.close();
      win.print();
    }
  };

  // ── Render phases ────────────────────────────────────────────────────────────

  if (phase === "idle" || phase === "uploading") {
    return (
      <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
        <div className="mb-6 animate-section">
          <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
            Phân tích tài liệu Halal
          </h1>
          <p className="mt-2" style={{ color: "#6B7280" }}>
            Upload tài liệu để nhận đánh giá compliance toàn diện
          </p>
        </div>

        {/* Coming soon toast */}
        {showComingSoon && (
          <div
            className="mb-4 p-3 rounded-xl text-sm text-center"
            style={{
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.3)",
              color: "#f59e0b",
            }}
          >
            Tính năng này sẽ được cập nhật sớm nhất
          </div>
        )}

        {/* ── Step 1: Document type selector ─────────────────────────────── */}
        <div
          className="mb-6 rounded-2xl p-5"
          style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
        >
          <div className="grid grid-flow-col items-center gap-2 mb-4 justify-start">
            <span
              className="w-6 h-6 rounded-full grid place-items-center text-xs font-bold"
              style={{
                background: selectedDocType ? "#0A1F44" : "#E2E8F0",
                color: selectedDocType ? "white" : "#6B7280",
              }}
            >
              {selectedDocType ? "✓" : "1"}
            </span>
            <h2 className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
              Chọn loại tài liệu
            </h2>
            {selectedDocType && (
              <span
                className="ml-auto text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(10,31,68,0.08)",
                  color: "#0A1F44",
                  border: "1px solid rgba(10,31,68,0.2)",
                }}
              >
                {
                  [...DOC_TYPE_OPTIONS, ...SOP_SUB_OPTIONS].find(
                    (o) => o.id === selectedDocType,
                  )?.label
                }
              </span>
            )}
          </div>

          {/* Non-SOP options */}
          <div className="grid grid-cols-2 gap-2 mb-2">
            {DOC_TYPE_OPTIONS.map((opt) => {
              const locked = !isFullAccess && opt.id !== "halal_policy";
              return (
                <button
                  key={opt.id}
                  onClick={() => {
                    if (locked) {
                      setShowComingSoon(true);
                      setTimeout(() => setShowComingSoon(false), 3000);
                      return;
                    }
                    setSelectedDocType(opt.id);
                    setSopExpanded(false);
                  }}
                  className="text-left px-3 py-2.5 rounded-xl text-sm font-medium transition-all"
                  style={{
                    background:
                      selectedDocType === opt.id
                        ? "rgba(10,31,68,0.08)"
                        : "#FFFFFF",
                    border:
                      selectedDocType === opt.id
                        ? "1px solid rgba(10,31,68,0.3)"
                        : "1px solid #E2E8F0",
                    color: locked
                      ? "#94A3B8"
                      : selectedDocType === opt.id
                        ? "#0A1F44"
                        : "#6B7280",
                    cursor: locked ? "not-allowed" : "pointer",
                    opacity: locked ? 0.5 : 1,
                  }}
                >
                  {opt.label}
                  {locked && <span className="ml-1 text-xs">🔒</span>}
                </button>
              );
            })}
          </div>

          {/* SOP group */}
          <div>
            <button
              onClick={() => {
                if (!isFullAccess) {
                  setShowComingSoon(true);
                  setTimeout(() => setShowComingSoon(false), 3000);
                  return;
                }
                setSopExpanded((v) => !v);
                if (!sopExpanded) setSelectedDocType(null);
              }}
              className="w-full grid items-center px-3 py-2.5 rounded-xl text-sm font-medium transition-all mb-1"
              style={{
                gridTemplateColumns: "1fr auto",
                background: SOP_SUB_OPTIONS.some(
                  (o) => o.id === selectedDocType,
                )
                  ? "rgba(10,31,68,0.06)"
                  : "#FFFFFF",
                border: SOP_SUB_OPTIONS.some((o) => o.id === selectedDocType)
                  ? "1px solid rgba(10,31,68,0.25)"
                  : "1px solid #E2E8F0",
                color: !isFullAccess
                  ? "#94A3B8"
                  : SOP_SUB_OPTIONS.some((o) => o.id === selectedDocType)
                    ? "#0A1F44"
                    : "#6B7280",
                cursor: !isFullAccess ? "default" : "pointer",
              }}
            >
              <span>
                SOP Documentation
                {!isFullAccess && (
                  <span className="ml-1 text-xs opacity-50">🔒</span>
                )}
              </span>
              {isFullAccess && (
                <svg
                  className={`w-4 h-4 transition-transform ${sopExpanded ? "rotate-180" : ""}`}
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
              )}
            </button>
            {sopExpanded && isFullAccess && (
              <div className="grid grid-cols-2 gap-2 pl-3 pt-1">
                {SOP_SUB_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setSelectedDocType(opt.id)}
                    className="text-left px-3 py-2 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background:
                        selectedDocType === opt.id
                          ? "rgba(10,31,68,0.08)"
                          : "#FFFFFF",
                      border:
                        selectedDocType === opt.id
                          ? "1px solid rgba(10,31,68,0.3)"
                          : "1px solid #E2E8F0",
                      color: selectedDocType === opt.id ? "#0A1F44" : "#6B7280",
                    }}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Step 2: Upload ──────────────────────────────────────────────── */}
        <div className="mb-1 flex items-center gap-2">
          <span
            className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: "#E2E8F0", color: "#6B7280" }}
          >
            2
          </span>
          <h2 className="text-sm font-semibold text-[#0A1F44]">
            Tải lên tài liệu
          </h2>
        </div>

        {error && (
          <div
            className="mb-4 p-4 rounded-xl text-sm"
            style={{
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              color: "#ef4444",
            }}
          >
            {error}
          </div>
        )}

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all grid place-items-center ${
            !selectedDocType
              ? "border-[#E2E8F0] opacity-40 cursor-not-allowed"
              : isDragActive
                ? "border-[#0A1F44] bg-[#DCE3F0]"
                : "border-[#E2E8F0] hover:border-[#0A1F44] bg-[#FFFFFF]"
          }`}
        >
          <input {...getInputProps()} />
          {phase === "uploading" ? (
            <>
              <div className="spinner w-10 h-10 mb-4" />
              <p className="text-[#0A1F44] font-semibold">Đang tải lên…</p>
            </>
          ) : (
            <>
              <div
                className="h-16 w-16 rounded-full grid place-items-center mb-4"
                style={{ background: "rgba(10,31,68,0.12)" }}
              >
                <svg
                  className="w-8 h-8"
                  style={{ color: "#0A1F44" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-[#0A1F44] mb-1">
                {isDragActive ? "Thả file vào đây" : "Kéo & thả file vào đây"}
              </h3>
              <p className="text-[#6B7280] text-sm mb-5">
                PDF, DOCX, PPTX, TXT, MD — tối đa 20 MB
              </p>
              <button
                type="button"
                className="px-6 py-2.5 font-medium rounded-xl transition-all"
                style={{ background: "#0A1F44", color: "white" }}
              >
                Chọn file
              </button>
            </>
          )}
        </div>

        {/* Version history preview — admin only */}
        {isFullAccess && fileVersions.length > 0 && (
          <div className="mt-8">
            <h3
              className="text-sm font-semibold mb-3"
              style={{ color: "#6B7280" }}
            >
              Lịch sử phiên bản
            </h3>
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid #E2E8F0" }}
            >
              {fileVersions.slice(0, 5).map((v, i) => {
                const st = statusLabel(v.status);
                return (
                  <div
                    key={i}
                    className="grid items-center gap-3 px-4 py-3"
                    style={{
                      gridTemplateColumns: "auto 1fr",
                      borderBottom:
                        i < Math.min(4, fileVersions.length - 1)
                          ? "1px solid #E2E8F0"
                          : "none",
                    }}
                  >
                    <span
                      className="text-lg font-bold tabular-nums"
                      style={{ color: scoreColor(v.score), width: 36 }}
                    >
                      {v.score}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm text-[#0A1F44] truncate">
                        v{v.version} · {v.doc_type_label}
                      </p>
                      <p className="text-xs" style={{ color: "#6B7280" }}>
                        {v.issues_count} vấn đề ·{" "}
                        {new Date(v.timestamp).toLocaleDateString("vi-VN")}
                      </p>
                    </div>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: st.bg,
                        color: st.color,
                        border: `1px solid ${st.border}`,
                      }}
                    >
                      {st.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (phase === "analyzing") {
    return (
      <div className="flex-1 lg:min-h-0 w-full grid place-items-center">
        <div className="w-full text-center">
          <div className="mb-6 relative w-fit mx-auto">
            <svg width="120" height="120" viewBox="0 0 120 120">
              <circle
                cx="60"
                cy="60"
                r="50"
                fill="none"
                stroke="#DCE3F0"
                strokeWidth="8"
              />
              <circle
                cx="60"
                cy="60"
                r="50"
                fill="none"
                stroke="#0A1F44"
                strokeWidth="8"
                strokeDasharray={`${(analyzeProgress / 100) * 314} 314`}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
                style={{ transition: "stroke-dasharray 0.4s ease" }}
              />
            </svg>
            <div className="absolute inset-0 grid place-items-center">
              <span className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
                {analyzeProgress}%
              </span>
            </div>
          </div>
          <h2 className="text-xl font-bold mb-2" style={{ color: "#0A1F44" }}>
            Đang phân tích tài liệu…
          </h2>
          <p className="text-sm mb-1" style={{ color: "#6B7280" }}>
            AI đang đọc và đối chiếu với tiêu chuẩn JAKIM/HDC
          </p>
          {previousReport && (
            <p className="text-xs mb-6" style={{ color: "#0A1F44" }}>
              ↺ Phát hiện phiên bản trước (điểm{" "}
              {previousReport.compliance_score}) · Đang so sánh thay đổi
            </p>
          )}
          {!previousReport && <div className="mb-6" />}
          <div className="space-y-2 text-sm" style={{ color: "#6B7280" }}>
            {[
              "Trích xuất nội dung văn bản",
              "Đối chiếu tiêu chuẩn Halal",
              "Phân tích rủi ro inline",
              "Tổng hợp Gap Analysis",
            ].map((step, i) => (
              <div
                key={i}
                className="grid grid-flow-col items-center gap-2 justify-center"
              >
                {analyzeProgress > i * 22 ? (
                  <span style={{ color: "#0A1F44" }}>✓</span>
                ) : (
                  <span className="w-3.5 h-3.5 rounded-full border border-[#E2E8F0] inline-block" />
                )}
                <span>{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Done: Full results ────────────────────────────────────────────────────────
  if (!report) return null;
  const st = statusLabel(report.overall_status);

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* Saved banner */}
      {isFullAccess && (
        <div
          className="grid items-center mb-4 px-4 py-2.5 rounded-xl text-sm"
          style={{
            gridTemplateColumns: "1fr auto",
            background: "rgba(34,197,94,0.07)",
            border: "1px solid rgba(10,31,68,0.15)",
          }}
        >
          <span style={{ color: "#0A1F44" }}>
            ✓ Tài liệu đã được lưu và đánh giá thành công
          </span>
          {isBusiness && (
            <Link
              href="/documents"
              className="text-xs font-medium hover:underline"
              style={{ color: "#0A1F44" }}
            >
              Xem tất cả tài liệu →
            </Link>
          )}
        </div>
      )}

      {/* Header */}
      <div
        className="grid items-start mb-6 gap-3"
        style={{ gridTemplateColumns: "1fr auto" }}
      >
        <div>
          <h1 className="text-xl font-bold text-[#0A1F44]">
            {report.filename}
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "#6B7280" }}>
            {report.doc_type_label} · {report.word_count.toLocaleString()} từ ·{" "}
            {report.standards_found} tiêu chuẩn tham chiếu
          </p>
        </div>
        <button
          onClick={() => {
            try {
              sessionStorage.removeItem(SESSION_KEY);
            } catch {}
            setPhase("idle");
            setReport(null);
            setFileName("");
            setSelectedDocType(null);
            setSopExpanded(false);
            setRewrites({});
            setFileVersions([]);
            setPreviousReport(null);
            setExistingReview(null);
            setReview({
              reviewer: "",
              notes: "",
              confirmed_issues: [],
              false_positives: [],
              additional_findings: [],
              issue_comments: {},
              final_score: null,
              status: "pending",
            });
            setActiveTab("overview");
          }}
          className="grid items-center gap-2 text-sm px-5 py-2.5 rounded-xl font-semibold transition-all hover:scale-105 active:scale-95"
          style={{
            gridTemplateColumns: "auto 1fr",
            background: "#0A1F44",
            color: "white",
            boxShadow: "0 4px 12px rgba(10,31,68,0.3)",
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
              d="M5 13l4 4L19 7"
            />
          </svg>
          Hoàn thành
        </button>
      </div>

      {/* Tabs */}
      {(() => {
        const visibleTabs = TABS.filter((t) => {
          if (t.id === "auditor") return isProvider;
          if (t.id === "history") return isFullAccess;
          return true;
        });
        return (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${visibleTabs.length}, 1fr)`,
              gap: 4,
              padding: 4,
              borderRadius: 12,
              marginBottom: "1.5rem",
              background: "#F5F1E8",
              border: "1px solid #E2E8F0",
            }}
          >
            {visibleTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: "10px 4px",
                  textAlign: "center",
                  fontSize: "0.875rem",
                  fontWeight: activeTab === tab.id ? 600 : 500,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  cursor: "pointer",
                  transition: "all 0.15s",
                  borderRadius: 8,
                  border: "none",
                  color: activeTab === tab.id ? "#FFFFFF" : "#6B7280",
                  background: activeTab === tab.id ? "#0A1F44" : "transparent",
                  boxShadow:
                    activeTab === tab.id
                      ? "0 2px 8px rgba(10,31,68,0.25)"
                      : "none",
                }}
              >
                <span style={{ marginRight: 4, fontSize: "0.75rem" }}>
                  {tab.icon}
                </span>
                {tab.label}
              </button>
            ))}
          </div>
        );
      })()}

      {/* ── Tab: Overview (F-01, F-04) ───────────────────────────────────────────── */}
      {activeTab === "overview" && (
        <div className="space-y-5">
          {/* Score + Status */}
          <div
            className="rounded-2xl p-6 grid gap-6 items-center"
            style={{
              gridTemplateColumns: "auto 1fr",
              background: "#F5F1E8",
              border: "1px solid #E2E8F0",
            }}
          >
            <ScoreDial score={report.compliance_score} />
            <div className="min-w-0">
              <span
                className="inline-block text-sm px-3 py-1 rounded-full font-semibold mb-3"
                style={{
                  background: st.bg,
                  color: st.color,
                  border: `1px solid ${st.border}`,
                }}
              >
                {st.label}
              </span>
              <p className="text-[#0A1F44] text-base leading-relaxed">
                {report.summary}
              </p>
            </div>
          </div>

          {/* Strengths */}
          {report.strengths.length > 0 && (
            <div
              className="rounded-xl p-5"
              style={{
                background: "rgba(10,31,68,0.06)",
                border: "1px solid rgba(10,31,68,0.15)",
              }}
            >
              <h3
                className="text-sm font-semibold mb-3"
                style={{ color: "#0A1F44" }}
              >
                ✓ Điểm mạnh
              </h3>
              <ul className="space-y-2">
                {report.strengths.map((s, i) => (
                  <li
                    key={i}
                    className="grid gap-2 text-sm text-[#0A1F44]"
                    style={{ gridTemplateColumns: "auto 1fr" }}
                  >
                    <span style={{ color: "#0A1F44" }}>·</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Diff vs previous version */}
          {previousReport && (
            <div
              className="rounded-xl p-5"
              style={{
                background: "rgba(10,31,68,0.06)",
                border: "1px solid rgba(10,31,68,0.2)",
              }}
            >
              <h3
                className="text-sm font-semibold mb-3"
                style={{ color: "#6B7280" }}
              >
                ↺ So sánh với lần phân tích trước
              </h3>
              <div className="grid grid-flow-col items-center gap-6 mb-3 justify-start">
                <div className="text-center">
                  <p className="text-xs mb-1" style={{ color: "#6B7280" }}>
                    Lần trước
                  </p>
                  <span
                    className="text-2xl font-bold"
                    style={{
                      color: scoreColor(previousReport.compliance_score),
                    }}
                  >
                    {previousReport.compliance_score}
                  </span>
                </div>
                <span style={{ color: "#6B7280", fontSize: 18 }}>→</span>
                <div className="text-center">
                  <p className="text-xs mb-1" style={{ color: "#6B7280" }}>
                    Lần này
                  </p>
                  <span
                    className="text-2xl font-bold"
                    style={{ color: scoreColor(report.compliance_score) }}
                  >
                    {report.compliance_score}
                  </span>
                </div>
                {report.compliance_score !==
                  previousReport.compliance_score && (
                  <span
                    className="text-sm font-bold"
                    style={{
                      color:
                        report.compliance_score >
                        previousReport.compliance_score
                          ? "#0A1F44"
                          : "#ef4444",
                    }}
                  >
                    {report.compliance_score > previousReport.compliance_score
                      ? "▲"
                      : "▼"}{" "}
                    {Math.abs(
                      report.compliance_score - previousReport.compliance_score,
                    )}{" "}
                    điểm
                  </span>
                )}
                {report.compliance_score ===
                  previousReport.compliance_score && (
                  <span className="text-sm" style={{ color: "#6B7280" }}>
                    = Không thay đổi
                  </span>
                )}
              </div>
              <div
                className="flex flex-wrap gap-4 text-xs"
                style={{ color: "#6B7280" }}
              >
                <span>
                  Vấn đề:{" "}
                  <strong
                    style={{
                      color:
                        report.issues.length < previousReport.issues.length
                          ? "#0A1F44"
                          : report.issues.length > previousReport.issues.length
                            ? "#ef4444"
                            : "#6B7280",
                    }}
                  >
                    {previousReport.issues.length} → {report.issues.length}
                  </strong>
                </span>
                <span>
                  Điểm mạnh:{" "}
                  <strong style={{ color: "#6B7280" }}>
                    {previousReport.strengths.length} →{" "}
                    {report.strengths.length}
                  </strong>
                </span>
                {report.overall_status !== previousReport.overall_status && (
                  <span>
                    Trạng thái:{" "}
                    <strong style={{ color: "#f59e0b" }}>
                      {statusLabel(previousReport.overall_status).label} →{" "}
                      {statusLabel(report.overall_status).label}
                    </strong>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Issues summary */}
          {report.issues.length > 0 && (
            <div
              className="rounded-xl p-5"
              style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
            >
              <h3 className="text-sm font-semibold mb-3 text-[#0A1F44]">
                Vấn đề phát hiện ({report.issues.length})
              </h3>
              <div className="space-y-3">
                {report.issues.map((issue, i) => {
                  const sev = severityBadge(issue.severity);
                  const key = `issue-${i}`;
                  return (
                    <div
                      key={i}
                      className="rounded-xl p-4"
                      style={{
                        background: "#FFFFFF",
                        border: "1px solid #E2E8F0",
                      }}
                    >
                      <div className="flex items-start gap-3 flex-wrap">
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0"
                          style={{ background: sev.bg, color: sev.color }}
                        >
                          {sev.label}
                        </span>
                        <span
                          className="text-xs px-2 py-0.5 rounded-full flex-shrink-0"
                          style={{
                            background: "rgba(148,163,184,0.1)",
                            color: "#6B7280",
                          }}
                        >
                          {issue.section}
                        </span>
                      </div>
                      <p className="text-sm text-[#0A1F44] mt-2">
                        {issue.issue}
                      </p>
                      <p
                        className="text-xs mt-1.5"
                        style={{ color: "#6B7280" }}
                      >
                        💡 {issue.recommendation}
                      </p>
                      {issue.reference && (
                        <p
                          className="text-xs mt-1"
                          style={{ color: "#0A1F44" }}
                        >
                          § {issue.reference}
                        </p>
                      )}
                      {/* F-06: Rewrite button */}
                      {!rewrites[key] && (
                        <button
                          onClick={() =>
                            suggestRewrite(
                              key,
                              issue.issue + " " + issue.recommendation,
                              issue.issue,
                            )
                          }
                          disabled={rewriteLoading === key}
                          className="mt-3 text-xs px-3 py-1.5 rounded-lg transition-all"
                          style={{
                            background: "rgba(10,31,68,0.1)",
                            color: "#6B7280",
                            border: "1px solid rgba(10,31,68,0.2)",
                          }}
                        >
                          {rewriteLoading === key
                            ? "⏳ Đang tạo gợi ý…"
                            : "✨ Gợi ý viết lại"}
                        </button>
                      )}
                      {rewrites[key] && (
                        <div
                          className="mt-3 rounded-lg p-3"
                          style={{
                            background: "rgba(10,31,68,0.08)",
                            border: "1px solid rgba(10,31,68,0.2)",
                          }}
                        >
                          <p
                            className="text-xs font-medium mb-1"
                            style={{ color: "#6B7280" }}
                          >
                            ✨ Gợi ý viết lại:
                          </p>
                          <p className="text-sm text-[#0A1F44] leading-relaxed">
                            {rewrites[key].rewritten}
                          </p>
                          {rewrites[key].explanation && (
                            <p
                              className="text-xs mt-2"
                              style={{ color: "#6B7280" }}
                            >
                              {rewrites[key].explanation}
                            </p>
                          )}
                          {rewrites[key].standards_referenced?.length > 0 && (
                            <p
                              className="text-xs mt-1"
                              style={{ color: "#0A1F44" }}
                            >
                              § {rewrites[key].standards_referenced.join(", ")}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* F-04: Standards Checklist */}
          {report.standards_checked.length > 0 && (
            <div
              className="rounded-xl p-5"
              style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
            >
              <h3 className="text-sm font-semibold mb-3 text-[#0A1F44]">
                Tiêu chuẩn đã đối chiếu
              </h3>
              <div className="flex flex-wrap gap-2">
                {report.standards_checked.map((s, i) => (
                  <span
                    key={i}
                    className="text-xs px-2.5 py-1 rounded-full"
                    style={{
                      background: "rgba(10,31,68,0.06)",
                      color: "#0A1F44",
                      border: "1px solid rgba(10,31,68,0.15)",
                    }}
                  >
                    ✓ {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {/* Signature detection */}
          {(report as any).signature_detection &&
            (() => {
              const sig = (report as any).signature_detection;
              const status = sig.signature_status || "none";
              const styles: Record<
                string,
                {
                  icon: string;
                  color: string;
                  bg: string;
                  border: string;
                  label: string;
                }
              > = {
                confirmed: {
                  icon: "✓",
                  color: "#0A1F44",
                  bg: "rgba(10,31,68,0.06)",
                  border: "rgba(10,31,68,0.25)",
                  label: "Đã xác nhận",
                },
                likely: {
                  icon: "?",
                  color: "#6B7280",
                  bg: "rgba(10,31,68,0.06)",
                  border: "rgba(10,31,68,0.3)",
                  label: "Cần xác nhận",
                },
                placeholder: {
                  icon: "✕",
                  color: "#f87171",
                  bg: "rgba(239,68,68,0.06)",
                  border: "rgba(239,68,68,0.3)",
                  label: "Chưa có chữ ký thật",
                },
                none: {
                  icon: "—",
                  color: "#6B7280",
                  bg: "rgba(100,116,139,0.06)",
                  border: "rgba(100,116,139,0.3)",
                  label: "Không phát hiện",
                },
              };
              const statusStyle = styles[status] || styles.none;

              return (
                <div
                  className="rounded-2xl overflow-hidden"
                  style={{ border: `1px solid ${statusStyle.border}` }}
                >
                  <div
                    className="px-5 py-4"
                    style={{
                      background: statusStyle.bg,
                      borderBottom: "1px solid rgba(226,232,240,0.6)",
                    }}
                  >
                    <div className="grid grid-flow-col items-center gap-3 justify-start">
                      <div
                        className="w-8 h-8 rounded-lg grid place-items-center text-base font-bold"
                        style={{
                          background: `${statusStyle.color}20`,
                          color: statusStyle.color,
                        }}
                      >
                        {statusStyle.icon}
                      </div>
                      <div>
                        <div className="grid grid-flow-col items-center gap-2 justify-start">
                          <h3 className="text-sm font-semibold text-[#0A1F44]">
                            Chữ ký & Con dấu
                          </h3>
                          <span
                            className="text-xs px-2 py-0.5 rounded-full"
                            style={{
                              background: `${statusStyle.color}20`,
                              color: statusStyle.color,
                            }}
                          >
                            {statusStyle.label}
                          </span>
                        </div>
                        <p
                          className="text-xs mt-1"
                          style={{ color: "#6B7280" }}
                        >
                          {sig.summary}
                        </p>
                      </div>
                    </div>
                  </div>
                  {sig.signature_zones.length > 0 && (
                    <div className="px-5 py-3 space-y-1.5">
                      {sig.signature_zones
                        .slice(0, 8)
                        .map((z: any, i: number) => (
                          <div
                            key={i}
                            className="grid grid-flow-col items-center gap-2 justify-start text-xs"
                          >
                            <span
                              style={{
                                color:
                                  z.type === "image"
                                    ? "#0A1F44"
                                    : z.type === "text_pattern"
                                      ? "#6B7280"
                                      : "#fbbf24",
                              }}
                            >
                              {z.type === "image"
                                ? "🖼"
                                : z.type === "text_pattern"
                                  ? "📝"
                                  : "🔐"}
                            </span>
                            <span
                              style={{
                                color:
                                  z.type === "text_pattern"
                                    ? "#6B7280"
                                    : "#6B7280",
                              }}
                            >
                              {z.description}
                              {z.type === "text_pattern" &&
                                " (chỉ là text, chưa có chữ ký thật)"}
                            </span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              );
            })()}
        </div>
      )}

      {/* ── Tab: Gap Analysis (F-02) ─────────────────────────────────────────────── */}
      {activeTab === "gaps" && (
        <div className="space-y-4">
          {!report.gap_analysis ? (
            <p className="text-[#6B7280] text-sm py-8 text-center">
              Không có dữ liệu Gap Analysis
            </p>
          ) : (
            <>
              {[
                {
                  key: "critical_gaps",
                  label: "Lỗ hổng nghiêm trọng",
                  color: "#ef4444",
                  bg: "rgba(239,68,68,0.06)",
                  border: "rgba(239,68,68,0.2)",
                  icon: "⛔",
                },
                {
                  key: "major_gaps",
                  label: "Lỗ hổng lớn",
                  color: "#f59e0b",
                  bg: "rgba(245,158,11,0.06)",
                  border: "rgba(245,158,11,0.2)",
                  icon: "⚠",
                },
                {
                  key: "minor_gaps",
                  label: "Điểm cải thiện nhỏ",
                  color: "#6B7280",
                  bg: "rgba(91,107,125,0.06)",
                  border: "rgba(91,107,125,0.15)",
                  icon: "ℹ",
                },
              ].map((group) => {
                const items = report.gap_analysis![
                  group.key as keyof GapAnalysis
                ] as string[];
                if (!items?.length) return null;
                const key = `gap-${group.key}`;
                return (
                  <div
                    key={group.key}
                    className="rounded-xl p-5"
                    style={{
                      background: group.bg,
                      border: `1px solid ${group.border}`,
                    }}
                  >
                    <h3
                      className="text-sm font-semibold mb-3 flex items-center gap-2"
                      style={{ color: group.color }}
                    >
                      <span>{group.icon}</span>
                      {group.label} ({items.length})
                    </h3>
                    <ul className="space-y-2">
                      {items.map((gap, i) => {
                        const rewriteKey = `${key}-${i}`;
                        return (
                          <li
                            key={i}
                            className="rounded-lg p-3"
                            style={{ background: "rgba(0,0,0,0.03)" }}
                          >
                            <p className="text-sm text-[#0A1F44]">{gap}</p>
                            {/* F-06: Rewrite for gaps */}
                            {!rewrites[rewriteKey] && (
                              <button
                                onClick={() =>
                                  suggestRewrite(rewriteKey, gap, gap)
                                }
                                disabled={rewriteLoading === rewriteKey}
                                className="mt-2 text-xs px-2.5 py-1 rounded-lg transition-all"
                                style={{
                                  background: "rgba(10,31,68,0.1)",
                                  color: "#6B7280",
                                  border: "1px solid rgba(10,31,68,0.15)",
                                }}
                              >
                                {rewriteLoading === rewriteKey
                                  ? "⏳ Đang tạo…"
                                  : "✨ Gợi ý khắc phục"}
                              </button>
                            )}
                            {rewrites[rewriteKey] && (
                              <div
                                className="mt-2 rounded-lg p-2.5"
                                style={{
                                  background: "rgba(10,31,68,0.08)",
                                  border: "1px solid rgba(10,31,68,0.2)",
                                }}
                              >
                                <p
                                  className="text-xs font-medium mb-1"
                                  style={{ color: "#6B7280" }}
                                >
                                  ✨ Gợi ý:
                                </p>
                                <p className="text-sm text-[#0A1F44]">
                                  {rewrites[rewriteKey].rewritten}
                                </p>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
              {/* Recommendations */}
              {report.recommendations.length > 0 && (
                <div
                  className="rounded-xl p-5"
                  style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
                >
                  <h3 className="text-sm font-semibold mb-3 text-[#0A1F44]">
                    Khuyến nghị tổng quát
                  </h3>
                  <ul className="space-y-2">
                    {report.recommendations.map((r, i) => (
                      <li key={i} className="flex gap-2 text-sm text-[#0A1F44]">
                        <span style={{ color: "#0A1F44" }}>{i + 1}.</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {/* Risk Flags (merged from former Risks tab) */}
          {report.risk_flags.length > 0 && (
            <div className="space-y-4 mt-6">
              <h3 className="text-sm font-semibold text-[#0A1F44] flex items-center gap-2">
                <span style={{ color: "#f87171" }}>⚑</span> Cảnh báo rủi ro (
                {report.risk_flags.length})
              </h3>
              {report.risk_flags.map((flag, i) => {
                const sev = severityBadge(flag.severity);
                const key = `risk-${i}`;
                return (
                  <div
                    key={i}
                    className="rounded-xl p-5"
                    style={{
                      background: "#F5F1E8",
                      border: `1px solid ${sev.color}30`,
                    }}
                  >
                    <div className="flex items-center gap-2 flex-wrap mb-3">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ background: sev.bg, color: sev.color }}
                      >
                        {sev.label}
                      </span>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{
                          background: "rgba(148,163,184,0.1)",
                          color: "#6B7280",
                        }}
                      >
                        {riskTypeLabel(flag.risk_type)}
                      </span>
                    </div>
                    <blockquote
                      className="rounded-lg px-4 py-3 mb-3 text-sm italic border-l-2"
                      style={{
                        background: `${sev.color}12`,
                        borderColor: sev.color,
                        color: "#0A1F44",
                      }}
                    >
                      "{flag.text_snippet}"
                    </blockquote>
                    <p className="text-sm" style={{ color: "#6B7280" }}>
                      {flag.explanation}
                    </p>
                    {!rewrites[key] && (
                      <button
                        onClick={() =>
                          suggestRewrite(
                            key,
                            flag.text_snippet,
                            flag.explanation,
                          )
                        }
                        disabled={rewriteLoading === key}
                        className="mt-3 text-xs px-3 py-1.5 rounded-lg transition-all"
                        style={{
                          background: "rgba(10,31,68,0.1)",
                          color: "#6B7280",
                          border: "1px solid rgba(10,31,68,0.2)",
                        }}
                      >
                        {rewriteLoading === key
                          ? "⏳ Đang tạo gợi ý…"
                          : "✨ Gợi ý viết lại đoạn này"}
                      </button>
                    )}
                    {rewrites[key] && (
                      <div
                        className="mt-3 rounded-lg p-3"
                        style={{
                          background: "rgba(10,31,68,0.08)",
                          border: "1px solid rgba(10,31,68,0.2)",
                        }}
                      >
                        <p
                          className="text-xs font-medium mb-1"
                          style={{ color: "#6B7280" }}
                        >
                          ✨ Đề xuất viết lại:
                        </p>
                        <p className="text-sm text-[#0A1F44] leading-relaxed">
                          {rewrites[key].rewritten}
                        </p>
                        {rewrites[key].explanation && (
                          <p
                            className="text-xs mt-2"
                            style={{ color: "#6B7280" }}
                          >
                            {rewrites[key].explanation}
                          </p>
                        )}
                        {rewrites[key].standards_referenced?.length > 0 && (
                          <p
                            className="text-xs mt-1"
                            style={{ color: "#0A1F44" }}
                          >
                            § {rewrites[key].standards_referenced.join(", ")}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Citations (F-05) ─────────────────────────────────────────────────── */}
      {activeTab === "citations" && (
        <div className="space-y-4">
          {report.citations.length === 0 ? (
            <p className="text-[#6B7280] text-sm py-8 text-center">
              Chưa có trích dẫn tiêu chuẩn
            </p>
          ) : (
            report.citations.map((cit, i) => (
              <div
                key={i}
                className="rounded-xl p-5"
                style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
              >
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <span
                    className="text-xs px-2.5 py-1 rounded-full font-semibold"
                    style={{
                      background: "rgba(10,31,68,0.1)",
                      color: "#6B7280",
                      border: "1px solid rgba(10,31,68,0.2)",
                    }}
                  >
                    {cit.standard}
                  </span>
                  {cit.clause && (
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: "rgba(148,163,184,0.08)",
                        color: "#6B7280",
                      }}
                    >
                      Điều {cit.clause}
                    </span>
                  )}
                </div>
                {/* F-05: Direct citation text */}
                <blockquote
                  className="rounded-lg px-4 py-3 mb-3 text-sm border-l-2"
                  style={{
                    background: "rgba(10,31,68,0.06)",
                    borderColor: "#0A1F44",
                    color: "#374151",
                    fontStyle: "italic",
                  }}
                >
                  "{cit.text}"
                </blockquote>
                <p className="text-xs" style={{ color: "#6B7280" }}>
                  <span style={{ color: "#0A1F44" }}>Áp dụng:</span>{" "}
                  {cit.relevance}
                </p>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Tab: History — per-file versions (admin only) ────────────────────────── */}
      {activeTab === "history" && (
        <div className="space-y-4">
          <div
            className="rounded-xl p-4 text-sm"
            style={{
              background: "rgba(10,31,68,0.06)",
              border: "1px solid rgba(10,31,68,0.2)",
              color: "#6B7280",
            }}
          >
            Lịch sử phiên bản của:{" "}
            <strong className="text-[#0A1F44]">{fileName}</strong>
          </div>

          {/* Score progression */}
          {fileVersions.length > 1 && (
            <div
              className="rounded-xl p-5"
              style={{
                background: "rgba(10,31,68,0.06)",
                border: "1px solid rgba(10,31,68,0.15)",
              }}
            >
              <h3
                className="text-sm font-semibold mb-3"
                style={{ color: "#0A1F44" }}
              >
                Tiến độ cải thiện
              </h3>
              <div className="flex items-center gap-3 flex-wrap">
                {[...fileVersions].reverse().map((v, i, arr) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="text-center">
                      <p
                        className="text-xs mb-0.5"
                        style={{ color: "#6B7280" }}
                      >
                        v{v.version}
                      </p>
                      <span
                        className="text-xl font-bold"
                        style={{ color: scoreColor(v.score) }}
                      >
                        {v.score}
                      </span>
                    </div>
                    {i < arr.length - 1 && (
                      <span style={{ color: "#94A3B8" }}>→</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Version list */}
          {fileVersions.length === 0 ? (
            <p className="text-[#6B7280] text-sm py-8 text-center">
              Chưa có lịch sử phiên bản
            </p>
          ) : (
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid #E2E8F0" }}
            >
              <div
                className="px-4 py-3 text-xs font-semibold"
                style={{
                  color: "#6B7280",
                  background: "#FFFFFF",
                  borderBottom: "1px solid #E2E8F0",
                }}
              >
                {fileVersions.length} phiên bản đã lưu
              </div>
              {fileVersions.map((v, i) => {
                const hst = statusLabel(v.status);
                const isCurrent = i === 0;
                return (
                  <div
                    key={i}
                    className="px-4 py-3"
                    style={{
                      borderBottom:
                        i < fileVersions.length - 1
                          ? "1px solid #E2E8F0"
                          : "none",
                      background: isCurrent
                        ? "rgba(34,197,94,0.04)"
                        : "transparent",
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className="text-lg font-bold tabular-nums w-8"
                        style={{ color: scoreColor(v.score) }}
                      >
                        {v.score}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm text-[#0A1F44] flex items-center gap-2">
                          Phiên bản {v.version}
                          {isCurrent && (
                            <span
                              className="text-xs px-1.5 py-0.5 rounded-full"
                              style={{
                                background: "rgba(10,31,68,0.06)",
                                color: "#0A1F44",
                              }}
                            >
                              mới nhất
                            </span>
                          )}
                        </p>
                        <p className="text-xs" style={{ color: "#6B7280" }}>
                          {v.doc_type_label} · {v.issues_count} vấn đề ·{" "}
                          {new Date(v.timestamp).toLocaleString("vi-VN")}
                        </p>
                      </div>
                      <span
                        className="text-xs px-2 py-0.5 rounded-full flex-shrink-0"
                        style={{
                          background: hst.bg,
                          color: hst.color,
                          border: `1px solid ${hst.border}`,
                        }}
                      >
                        {hst.label}
                      </span>
                    </div>
                    {v.summary && (
                      <p
                        className="text-xs mt-2 pl-11 line-clamp-2"
                        style={{ color: "#6B7280" }}
                      >
                        {v.summary}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {fileVersions.length > 0 && (
            <button
              onClick={() => {
                const key = safeKey(fileName);
                setFileVersions([]);
                setPreviousReport(null);
                try {
                  localStorage.removeItem(`aminra_file_versions_${key}`);
                  localStorage.removeItem(`aminra_full_report_${key}`);
                } catch {}
              }}
              className="text-xs px-3 py-1.5 rounded-lg transition-all"
              style={{
                background: "rgba(239,68,68,0.08)",
                color: "#f87171",
                border: "1px solid rgba(239,68,68,0.2)",
              }}
            >
              Xóa lịch sử file này
            </button>
          )}
        </div>
      )}

      {/* ── Tab: Auditor Review (F-09) ───────────────────────────────────────────── */}
      {activeTab === "auditor" && (
        <div className="space-y-5">
          {/* Header card */}
          <div
            className="rounded-2xl p-5"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <div
              className="grid items-center gap-4"
              style={{ gridTemplateColumns: "auto 1fr auto" }}
            >
              <div
                className="w-12 h-12 rounded-xl grid place-items-center"
                style={{
                  background: "rgba(10,31,68,0.15)",
                  border: "1px solid rgba(10,31,68,0.3)",
                }}
              >
                <svg
                  className="w-6 h-6"
                  style={{ color: "#6B7280" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-[#0A1F44]">
                  Review kiểm toán viên
                </h3>
                <p className="text-sm mt-0.5" style={{ color: "#6B7280" }}>
                  Xem xét kết quả AI, thêm nhận xét, chấm điểm cuối cùng
                </p>
              </div>
              {existingReview && (
                <span
                  className="px-3 py-1 rounded-full text-xs font-medium"
                  style={{
                    background:
                      existingReview.status === "approved"
                        ? "rgba(34,197,94,0.15)"
                        : existingReview.status === "rejected"
                          ? "rgba(239,68,68,0.15)"
                          : "rgba(245,158,11,0.15)",
                    color:
                      existingReview.status === "approved"
                        ? "#0A1F44"
                        : existingReview.status === "rejected"
                          ? "#f87171"
                          : "#fbbf24",
                  }}
                >
                  {existingReview.status === "approved"
                    ? "✓ Đã phê duyệt"
                    : existingReview.status === "rejected"
                      ? "✗ Đã từ chối"
                      : "⏳ Đang xem xét"}
                </span>
              )}
            </div>
          </div>

          {/* AI score vs Final score */}
          <div className="grid grid-cols-2 gap-4">
            <div
              className="rounded-xl p-4 text-center"
              style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
            >
              <p className="text-xs mb-1" style={{ color: "#6B7280" }}>
                Điểm AI
              </p>
              <p
                className="text-2xl font-bold"
                style={{ color: scoreColor(report.compliance_score) }}
              >
                {report.compliance_score}
              </p>
            </div>
            <div
              className="rounded-xl p-4 text-center"
              style={{
                background: "#F5F1E8",
                border: "1px solid rgba(10,31,68,0.3)",
              }}
            >
              <p className="text-xs mb-1" style={{ color: "#6B7280" }}>
                Điểm kiểm toán viên
              </p>
              <input
                type="number"
                min={0}
                max={100}
                value={review.final_score ?? ""}
                onChange={(e) =>
                  setReview((r) => ({
                    ...r,
                    final_score: e.target.value ? Number(e.target.value) : null,
                  }))
                }
                placeholder="—"
                className="w-full text-2xl font-bold text-center outline-none"
                style={{
                  background: "transparent",
                  color:
                    review.final_score != null
                      ? scoreColor(review.final_score)
                      : "#6B7280",
                }}
              />
            </div>
          </div>

          {/* Reviewer info + status */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="text-xs font-medium mb-1.5 block"
                style={{ color: "#6B7280" }}
              >
                Kiểm toán viên *
              </label>
              <input
                value={review.reviewer}
                onChange={(e) =>
                  setReview((r) => ({ ...r, reviewer: e.target.value }))
                }
                placeholder="Họ tên kiểm toán viên"
                className="w-full px-4 py-2.5 rounded-xl text-sm text-[#0A1F44] outline-none"
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              />
            </div>
            <div>
              <label
                className="text-xs font-medium mb-1.5 block"
                style={{ color: "#6B7280" }}
              >
                Quyết định
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(
                  [
                    [
                      "pending",
                      "⏳ Chờ",
                      "rgba(245,158,11,0.15)",
                      "#fbbf24",
                      "rgba(245,158,11,0.3)",
                    ],
                    [
                      "approved",
                      "✓ Duyệt",
                      "rgba(34,197,94,0.15)",
                      "#0A1F44",
                      "rgba(10,31,68,0.25)",
                    ],
                    [
                      "rejected",
                      "✗ Từ chối",
                      "rgba(239,68,68,0.15)",
                      "#f87171",
                      "rgba(239,68,68,0.3)",
                    ],
                  ] as const
                ).map(([val, lbl, bg, color, border]) => (
                  <button
                    key={val}
                    onClick={() =>
                      setReview((r) => ({
                        ...r,
                        status: val as AuditorReview["status"],
                      }))
                    }
                    className="py-2 rounded-xl text-xs font-medium transition-all"
                    style={{
                      background: review.status === val ? bg : "#FFFFFF",
                      color: review.status === val ? color : "#6B7280",
                      border: `1px solid ${review.status === val ? border : "#E2E8F0"}`,
                    }}
                  >
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Review each AI issue */}
          {report.issues.length > 0 && (
            <div>
              <h4 className="text-sm font-bold text-[#0A1F44] mb-3">
                Xem xét từng vấn đề AI phát hiện ({report.issues.length})
              </h4>
              <div className="space-y-3">
                {report.issues.map((issue, i) => {
                  const key = String(i);
                  const isConfirmed = review.confirmed_issues.includes(key);
                  const isFP = review.false_positives.includes(key);
                  const comment = review.issue_comments[key] || "";
                  return (
                    <div
                      key={i}
                      className="rounded-xl overflow-hidden"
                      style={{ border: "1px solid #E2E8F0" }}
                    >
                      <div
                        className="px-4 py-3"
                        style={{ background: "#F5F1E8" }}
                      >
                        <div
                          className="grid items-start gap-3"
                          style={{ gridTemplateColumns: "1fr auto" }}
                        >
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <span
                                className="text-xs font-bold px-2 py-0.5 rounded"
                                style={{
                                  color:
                                    issue.severity === "critical"
                                      ? "#f87171"
                                      : issue.severity === "major"
                                        ? "#fbbf24"
                                        : "#6B7280",
                                  background:
                                    issue.severity === "critical"
                                      ? "rgba(239,68,68,0.12)"
                                      : issue.severity === "major"
                                        ? "rgba(245,158,11,0.12)"
                                        : "rgba(148,163,184,0.1)",
                                }}
                              >
                                {issue.severity?.toUpperCase()}
                              </span>
                              <span
                                className="text-xs"
                                style={{ color: "#6B7280" }}
                              >
                                {issue.section}
                              </span>
                            </div>
                            <p className="text-sm text-[#0A1F44]">
                              {issue.issue}
                            </p>
                            {issue.recommendation && (
                              <p
                                className="text-sm mt-1"
                                style={{ color: "#0A1F44" }}
                              >
                                → {issue.recommendation}
                              </p>
                            )}
                          </div>
                          {/* Confirm / Reject buttons */}
                          <div className="grid grid-flow-col gap-1.5 flex-shrink-0">
                            <button
                              onClick={() =>
                                setReview((r) => ({
                                  ...r,
                                  confirmed_issues: isConfirmed
                                    ? r.confirmed_issues.filter(
                                        (x) => x !== key,
                                      )
                                    : [...r.confirmed_issues, key],
                                  false_positives: r.false_positives.filter(
                                    (x) => x !== key,
                                  ),
                                }))
                              }
                              className="w-8 h-8 rounded-lg grid place-items-center text-xs font-bold transition-all"
                              title="Xác nhận đúng"
                              style={{
                                background: isConfirmed
                                  ? "rgba(10,31,68,0.15)"
                                  : "#F5F1E8",
                                color: isConfirmed ? "#0A1F44" : "#6B7280",
                                border: isConfirmed
                                  ? "1px solid rgba(10,31,68,0.3)"
                                  : "1px solid #E2E8F0",
                              }}
                            >
                              ✓
                            </button>
                            <button
                              onClick={() =>
                                setReview((r) => ({
                                  ...r,
                                  false_positives: isFP
                                    ? r.false_positives.filter((x) => x !== key)
                                    : [...r.false_positives, key],
                                  confirmed_issues: r.confirmed_issues.filter(
                                    (x) => x !== key,
                                  ),
                                }))
                              }
                              className="w-8 h-8 rounded-lg grid place-items-center text-xs font-bold transition-all"
                              title="False positive — AI sai"
                              style={{
                                background: isFP
                                  ? "rgba(239,68,68,0.2)"
                                  : "#F5F1E8",
                                color: isFP ? "#f87171" : "#6B7280",
                                border: isFP
                                  ? "1px solid rgba(239,68,68,0.4)"
                                  : "1px solid #E2E8F0",
                              }}
                            >
                              ✗
                            </button>
                          </div>
                        </div>
                      </div>
                      {/* Auditor comment for this issue */}
                      <div
                        className="px-4 py-2"
                        style={{
                          background: "#FFFFFF",
                          borderTop: "1px solid #E2E8F0",
                        }}
                      >
                        <input
                          value={comment}
                          onChange={(e) =>
                            setReview((r) => ({
                              ...r,
                              issue_comments: {
                                ...r.issue_comments,
                                [key]: e.target.value,
                              },
                            }))
                          }
                          placeholder="Nhận xét của kiểm toán viên về vấn đề này..."
                          className="w-full text-sm text-[#0A1F44] outline-none"
                          style={{
                            background: "transparent",
                            color: "#374151",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
              <div
                className="flex items-center gap-4 mt-2 text-xs"
                style={{ color: "#6B7280" }}
              >
                <span>✓ Xác nhận: {review.confirmed_issues.length}</span>
                <span>✗ False positive: {review.false_positives.length}</span>
                <span>
                  Chưa xem:{" "}
                  {report.issues.length -
                    review.confirmed_issues.length -
                    review.false_positives.length}
                </span>
              </div>
            </div>
          )}

          {/* General notes */}
          <div>
            <label
              className="text-xs font-medium mb-1.5 block"
              style={{ color: "#6B7280" }}
            >
              Nhận xét chung
            </label>
            <textarea
              value={review.notes}
              onChange={(e) =>
                setReview((r) => ({ ...r, notes: e.target.value }))
              }
              placeholder="Nhận xét tổng quát, lưu ý cho doanh nghiệp…"
              rows={4}
              className="w-full px-4 py-3 rounded-xl text-sm text-[#0A1F44] outline-none resize-none"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            />
          </div>

          {/* Additional findings */}
          <div>
            <label
              className="text-xs font-medium mb-1.5 block"
              style={{ color: "#6B7280" }}
            >
              Phát hiện thêm (AI chưa phát hiện)
            </label>
            <textarea
              value={review.additional_findings.join("\n")}
              onChange={(e) =>
                setReview((r) => ({
                  ...r,
                  additional_findings: e.target.value
                    .split("\n")
                    .filter(Boolean),
                }))
              }
              placeholder="Mỗi dòng một vấn đề mà AI bỏ sót…"
              rows={3}
              className="w-full px-4 py-3 rounded-xl text-sm text-[#0A1F44] outline-none resize-none"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            />
          </div>

          {/* Save bar */}
          <div
            className="grid items-center gap-4 rounded-xl p-4"
            style={{
              gridTemplateColumns: "auto 1fr auto",
              background: "#F5F1E8",
              border: "1px solid #E2E8F0",
            }}
          >
            <button
              onClick={saveReview}
              disabled={!review.reviewer.trim()}
              className="px-6 py-2.5 text-sm font-semibold rounded-xl transition-all hover:scale-105"
              style={{
                background: review.reviewer.trim() ? "#0A1F44" : "#E2E8F0",
                color: review.reviewer.trim() ? "white" : "#6B7280",
                boxShadow: review.reviewer.trim()
                  ? "0 4px 12px rgba(22,163,74,0.3)"
                  : "none",
              }}
            >
              Lưu & Hoàn tất Review
            </button>
            <div>
              {reviewSaved && (
                <span
                  className="text-sm font-medium"
                  style={{ color: "#0A1F44" }}
                >
                  ✓ Đã lưu thành công
                </span>
              )}
            </div>
            <span className="text-xs" style={{ color: "#94A3B8" }}>
              {review.confirmed_issues.length + review.false_positives.length}/
              {report.issues.length} vấn đề đã xem xét
            </span>
          </div>
        </div>
      )}

      {/* ── Tab: Export (F-10) ───────────────────────────────────────────────────── */}
      {activeTab === "export" && (
        <div className="space-y-4">
          <div
            className="rounded-xl p-6"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <h3 className="text-base font-semibold mb-2 text-[#0A1F44]">
              Xuất báo cáo đánh giá
            </h3>
            <p className="text-sm mb-5" style={{ color: "#6B7280" }}>
              Tạo báo cáo đầy đủ gồm Compliance Score, Gap Analysis, Risk Flags
              và Citations.
            </p>
            <div className="grid grid-flow-col gap-3 justify-start">
              <button
                onClick={exportReport}
                className="px-5 py-2.5 text-sm font-medium rounded-xl transition-all grid items-center gap-2"
                style={{
                  gridTemplateColumns: "auto 1fr",
                  background: "#0A1F44",
                  color: "white",
                }}
              >
                <span>↓</span> In / Lưu PDF
              </button>
              <button
                onClick={() => {
                  const blob = new Blob([JSON.stringify(report, null, 2)], {
                    type: "application/json",
                  });
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(blob);
                  a.download = `${report.filename.replace(/\.[^.]+$/, "")}_eval.json`;
                  a.click();
                }}
                className="px-5 py-2.5 text-sm font-medium rounded-xl transition-all grid items-center gap-2"
                style={{
                  gridTemplateColumns: "auto 1fr",
                  background: "rgba(10,31,68,0.1)",
                  color: "#6B7280",
                  border: "1px solid rgba(10,31,68,0.25)",
                }}
              >
                <span>{}</span> Xuất JSON
              </button>
            </div>
          </div>

          {/* Report preview */}
          <div
            className="rounded-xl p-5 text-sm"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              fontFamily: "monospace",
              color: "#6B7280",
            }}
          >
            <p className="text-[#0A1F44] font-bold mb-3">
              BÁO CÁO ĐÁNH GIÁ HALAL COMPLIANCE
            </p>
            <p>Tài liệu: {report.filename}</p>
            <p>Loại: {report.doc_type_label}</p>
            <p>
              Điểm: {report.compliance_score}/100 —{" "}
              {statusLabel(report.overall_status).label}
            </p>
            <p>
              Vấn đề: {report.issues.length} (
              {report.issues.filter((i) => i.severity === "critical").length}{" "}
              nghiêm trọng)
            </p>
            <p>Rủi ro inline: {report.risk_flags.length}</p>
            <p>Citations: {report.citations.length} điều khoản</p>
            <p className="mt-3">{report.summary}</p>
          </div>
        </div>
      )}

      {/* ── Tab: Generate Document ──────────────────────────────────────────────── */}
      {activeTab === "generate" && (
        <GenerateDocTab
          report={report}
          extractedText={extractedText}
          token={token}
          persisted={generateState}
          onStateChange={setGenerateState}
        />
      )}
    </div>
  );
}

// ─── F-10: HTML Report Generator ─────────────────────────────────────────────

function generateReportHTML(
  report: EvaluationReport,
  review: AuditorReview | null,
): string {
  const st =
    report.overall_status === "compliant"
      ? "#0A1F44"
      : report.overall_status === "needs_review"
        ? "#f59e0b"
        : "#ef4444";
  const stLabel =
    report.overall_status === "compliant"
      ? "Tuân thủ"
      : report.overall_status === "needs_review"
        ? "Cần xem xét"
        : "Không tuân thủ";
  return `<!DOCTYPE html><html lang="vi"><head>
<meta charset="UTF-8"><title>Báo cáo Halal — ${report.filename}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #111; line-height: 1.6; }
  h1 { color: #166534; border-bottom: 2px solid #166534; padding-bottom: 8px; }
  h2 { color: #0A1F44; margin-top: 28px; font-size: 16px; }
  .score { font-size: 48px; font-weight: bold; color: ${st}; }
  .status { display: inline-block; padding: 4px 12px; border-radius: 20px; background: ${st}22; color: ${st}; font-weight: bold; margin-left: 12px; font-size: 14px; }
  .issue { border-left: 3px solid #dc2626; padding: 10px 16px; margin: 8px 0; background: #fef2f2; border-radius: 4px; }
  .citation { border-left: 3px solid #0A1F44; padding: 10px 16px; margin: 8px 0; background: #eff6ff; border-radius: 4px; }
  .risk { border-left: 3px solid #d97706; padding: 10px 16px; margin: 8px 0; background: #fffbeb; border-radius: 4px; }
  blockquote { font-style: italic; color: #374151; margin: 0; }
  .meta { color: #6b7280; font-size: 13px; }
  @media print { body { margin: 20px; } }
</style></head><body>
<h1>Báo cáo Đánh giá Halal Compliance</h1>
<p class="meta">Tài liệu: <strong>${report.filename}</strong> · ${report.doc_type_label} · ${report.word_count.toLocaleString()} từ</p>
<p class="meta">Ngày: ${new Date().toLocaleDateString("vi-VN", { year: "numeric", month: "long", day: "numeric" })}</p>
<p><span class="score">${report.compliance_score}</span><span>/100</span><span class="status">${stLabel}</span></p>
<p>${report.summary}</p>
${report.strengths.length ? `<h2>Điểm mạnh</h2><ul>${report.strengths.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}
${report.issues.length ? `<h2>Vấn đề phát hiện (${report.issues.length})</h2>${report.issues.map((i) => `<div class="issue"><strong>[${i.severity.toUpperCase()}] ${i.section}</strong><br>${i.issue}<br><em>→ ${i.recommendation}</em><br><small>§ ${i.reference}</small></div>`).join("")}` : ""}
${
  report.gap_analysis
    ? `<h2>Gap Analysis</h2>
${report.gap_analysis.critical_gaps.length ? `<h3 style="color:#dc2626">Nghiêm trọng</h3><ul>${report.gap_analysis.critical_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}
${report.gap_analysis.major_gaps.length ? `<h3 style="color:#d97706">Lớn</h3><ul>${report.gap_analysis.major_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}
${report.gap_analysis.minor_gaps.length ? `<h3 style="color:#0A1F44">Nhỏ</h3><ul>${report.gap_analysis.minor_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}`
    : ""
}
${report.risk_flags.length ? `<h2>Rủi ro Inline (${report.risk_flags.length})</h2>${report.risk_flags.map((r) => `<div class="risk"><span style="color:#d97706;font-weight:bold">[${r.severity.toUpperCase()}] ${r.risk_type}</span><br><blockquote>"${r.text_snippet}"</blockquote><br>${r.explanation}</div>`).join("")}` : ""}
${report.citations.length ? `<h2>Trích dẫn Tiêu chuẩn (${report.citations.length})</h2>${report.citations.map((c) => `<div class="citation"><strong>${c.standard} — Điều ${c.clause}</strong><br><blockquote>"${c.text}"</blockquote><br><small>${c.relevance}</small></div>`).join("")}` : ""}
${review ? `<h2>Review của Kiểm toán viên</h2><p>Reviewer: <strong>${review.reviewer}</strong> · Trạng thái: <strong>${review.status}</strong></p><p>${review.notes}</p>` : ""}
<hr style="margin-top:40px"><p class="meta" style="text-align:center">Được tạo bởi AMINRA — Halal Certification AI · ${new Date().toISOString()}</p>
</body></html>`;
}
