"use client";

import { useEffect, useState } from "react";

type Severity = "minor" | "major" | "critical";

interface DocumentInfo {
  id: string;
  filename: string;
}

interface DocumentFeedbackItem {
  document_id: string;
  issue: string;
  severity: Severity;
  suggestion?: string;
}

interface RevisionRound {
  id: string;
  round: number;
  requester_id: string;
  requester_name: string;
  feedback: string;
  document_feedback: DocumentFeedbackItem[];
  requested_at: string;
  resolved_at: string | null;
}

interface Props {
  submissionId: string;
  status: string;
  role: "business" | "provider";
  documents: DocumentInfo[];
  token: string;
  onChanged?: () => void; // notify parent to refetch submission
}

export default function RevisionPanel({
  submissionId,
  status,
  role,
  documents,
  token,
  onChanged,
}: Props) {
  const [history, setHistory] = useState<RevisionRound[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchHistory = async () => {
    try {
      const res = await fetch(
        `/api/api/submissions/${submissionId}/revisions`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) throw new Error(`Lỗi ${res.status}`);
      const data = await res.json();
      setHistory(data.history ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi tải lịch sử");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [submissionId]);

  // Determine what the panel can do based on role + status
  const providerCanRequest =
    role === "provider" && (status === "reviewing" || status === "returned");
  const businessCanResubmit =
    role === "business" && status === "revision_required";
  const hasAction = providerCanRequest || businessCanResubmit;
  const hasHistory = history.length > 0;

  // Hide panel entirely when nothing actionable + no history (common on
  // freshly-submitted/approved submissions — avoids visually-dead block).
  if (!loading && !hasAction && !hasHistory) {
    return null;
  }

  return (
    <section
      className="rounded-2xl bg-white p-5"
      style={{
        border: "1px solid #E2E8F0",
        boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
      }}
      data-revision-panel
    >
      <header className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold" style={{ color: "#0A1F44" }}>
          Yêu cầu sửa hồ sơ
        </h3>
        {hasHistory && (
          <span
            className="text-xs px-2 py-1 rounded-full"
            style={{ background: "#FFFFFF", color: "#6B7280" }}
          >
            {history.length} vòng
          </span>
        )}
      </header>

      {error && (
        <div
          role="alert"
          className="bg-red-50 border border-red-200 rounded p-3 text-sm mb-3"
          style={{ color: "#991b1b" }}
        >
          {error}
        </div>
      )}

      {/* Provider action — request revision */}
      {providerCanRequest && (
        <RequestRevisionForm
          submissionId={submissionId}
          documents={documents}
          token={token}
          onRequested={() => {
            fetchHistory();
            onChanged?.();
          }}
        />
      )}

      {/* Business action — resubmit */}
      {businessCanResubmit && (
        <ResubmitForm
          submissionId={submissionId}
          documents={documents}
          token={token}
          onResubmitted={() => {
            fetchHistory();
            onChanged?.();
          }}
        />
      )}

      {/* Contextual hint when no form available but workflow could unlock it */}
      {!hasAction &&
        hasHistory &&
        role === "provider" &&
        (status === "pending" || status === "assigned") && (
          <div
            className="rounded-lg p-3 text-xs mb-4"
            style={{
              background: "rgba(245,158,11,0.08)",
              border: "1px solid rgba(245,158,11,0.2)",
              color: "#92400E",
            }}
          >
            Để yêu cầu sửa, đầu tiên chuyển trạng thái hồ sơ sang{" "}
            <strong>“Đang đánh giá”</strong>.
          </div>
        )}

      {/* History — visible to both */}
      <RevisionHistory
        history={history}
        loading={loading}
        documents={documents}
      />
    </section>
  );
}

// ── Provider form: request revision ───────────────────────────────────────

function RequestRevisionForm({
  submissionId,
  documents,
  token,
  onRequested,
}: {
  submissionId: string;
  documents: DocumentInfo[];
  token: string;
  onRequested: () => void;
}) {
  const [feedback, setFeedback] = useState("");
  const [docFeedback, setDocFeedback] = useState<DocumentFeedbackItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const addDocIssue = () => {
    setDocFeedback([
      ...docFeedback,
      {
        document_id: documents[0]?.id ?? "",
        issue: "",
        severity: "minor",
        suggestion: "",
      },
    ]);
  };

  const updateDocIssue = (i: number, patch: Partial<DocumentFeedbackItem>) => {
    setDocFeedback(
      docFeedback.map((d, idx) => (idx === i ? { ...d, ...patch } : d)),
    );
  };

  const removeDocIssue = (i: number) => {
    setDocFeedback(docFeedback.filter((_, idx) => idx !== i));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!feedback.trim()) {
      setError("Vui lòng nhập nội dung yêu cầu");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(
        `/api/api/submissions/received/${submissionId}/request-revision`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            feedback: feedback.trim(),
            document_feedback: docFeedback.filter(
              (d) => d.issue.trim() && d.document_id,
            ),
          }),
        },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
      setFeedback("");
      setDocFeedback([]);
      onRequested();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi gửi yêu cầu");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3 mb-5 pb-5"
      style={{ borderBottom: "1px solid #F1F5F9" }}
      data-form="request-revision"
    >
      <div>
        <label
          className="block text-xs font-medium mb-1"
          style={{ color: "#6B7280" }}
        >
          Nội dung yêu cầu sửa (overall)
        </label>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          placeholder="Mô tả những vấn đề doanh nghiệp cần sửa…"
          className="w-full px-3 py-2 rounded-lg text-sm outline-none"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        />
      </div>

      {docFeedback.map((d, i) => (
        <div
          key={i}
          className="rounded-lg p-3"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          <div className="flex gap-2 mb-2">
            <select
              value={d.document_id}
              onChange={(e) =>
                updateDocIssue(i, { document_id: e.target.value })
              }
              className="flex-1 px-2 py-1 text-xs rounded border"
              style={{ borderColor: "#E2E8F0" }}
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <select
              value={d.severity}
              onChange={(e) =>
                updateDocIssue(i, { severity: e.target.value as Severity })
              }
              className="px-2 py-1 text-xs rounded border"
              style={{ borderColor: "#E2E8F0" }}
            >
              <option value="minor">Minor</option>
              <option value="major">Major</option>
              <option value="critical">Critical</option>
            </select>
            <button
              type="button"
              onClick={() => removeDocIssue(i)}
              className="text-xs px-2 py-1 rounded"
              style={{ color: "#991b1b" }}
            >
              ×
            </button>
          </div>
          <input
            type="text"
            value={d.issue}
            onChange={(e) => updateDocIssue(i, { issue: e.target.value })}
            placeholder="Vấn đề cụ thể (vd: Thiếu dấu JAKIM)"
            className="w-full px-2 py-1.5 text-sm rounded mb-1"
            style={{ border: "1px solid #E2E8F0" }}
          />
          <input
            type="text"
            value={d.suggestion ?? ""}
            onChange={(e) => updateDocIssue(i, { suggestion: e.target.value })}
            placeholder="Gợi ý fix (optional)"
            className="w-full px-2 py-1.5 text-sm rounded"
            style={{ border: "1px solid #E2E8F0" }}
          />
        </div>
      ))}

      <button
        type="button"
        onClick={addDocIssue}
        className="text-xs font-medium"
        style={{ color: "#0A1F44" }}
      >
        + Thêm vấn đề cụ thể trên 1 document
      </button>

      {error && (
        <p role="alert" className="text-xs" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting || !feedback.trim()}
        className="w-full py-2.5 rounded-xl font-semibold text-sm"
        style={{
          background: submitting || !feedback.trim() ? "#E2E8F0" : "#dc2626",
          color: submitting || !feedback.trim() ? "#6B7280" : "white",
          cursor: submitting || !feedback.trim() ? "not-allowed" : "pointer",
        }}
      >
        {submitting ? "Đang gửi…" : "Gửi yêu cầu sửa cho doanh nghiệp"}
      </button>
    </form>
  );
}

// ── Business form: resubmit ──────────────────────────────────────────────

function ResubmitForm({
  submissionId,
  documents,
  token,
  onResubmitted,
}: {
  submissionId: string;
  documents: DocumentInfo[];
  token: string;
  onResubmitted: () => void;
}) {
  const [businessNotes, setBusinessNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`/api/api/submissions/${submissionId}/resubmit`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ business_notes: businessNotes.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
      setBusinessNotes("");
      onResubmitted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi gửi lại");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3 mb-5 pb-5"
      style={{ borderBottom: "1px solid #F1F5F9" }}
      data-form="resubmit"
    >
      <div
        className="bg-amber-50 border border-amber-200 rounded p-3 text-sm"
        style={{ color: "#7c2d12" }}
      >
        Hồ sơ đang ở trạng thái <strong>cần sửa</strong>. Hãy upload tài liệu
        mới (nếu cần) và gửi lại để CB tiếp tục đánh giá.
      </div>
      <textarea
        value={businessNotes}
        onChange={(e) => setBusinessNotes(e.target.value)}
        rows={3}
        placeholder="Mô tả những gì đã sửa (tùy chọn)…"
        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
        style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
      />
      {error && (
        <p role="alert" className="text-xs" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2.5 rounded-xl font-semibold text-sm"
        style={{
          background: submitting ? "#94A3B8" : "#0A1F44",
          color: "white",
          cursor: submitting ? "not-allowed" : "pointer",
        }}
      >
        {submitting ? "Đang gửi lại…" : "Đã sửa — gửi lại cho CB"}
      </button>
    </form>
  );
}

// ── History list (both personas) ─────────────────────────────────────────

function RevisionHistory({
  history,
  loading,
  documents,
}: {
  history: RevisionRound[];
  loading: boolean;
  documents: DocumentInfo[];
}) {
  const docName = (id: string) =>
    documents.find((d) => d.id === id)?.filename ?? id.slice(0, 8) + "…";

  if (loading)
    return (
      <p className="text-sm" style={{ color: "#94A3B8" }}>
        Đang tải…
      </p>
    );
  if (history.length === 0) {
    return (
      <p className="text-sm" style={{ color: "#94A3B8" }}>
        Chưa có vòng sửa nào.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium" style={{ color: "#6B7280" }}>
        Lịch sử các vòng sửa
      </h4>
      {history.map((r) => (
        <div
          key={r.id}
          className="rounded-lg p-3"
          style={{
            background: r.resolved_at ? "#FFFFFF" : "rgba(220,38,38,0.04)",
            border: `1px solid ${r.resolved_at ? "#E2E8F0" : "rgba(220,38,38,0.2)"}`,
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span
                className="text-xs font-bold px-2 py-0.5 rounded"
                style={{
                  background: r.resolved_at ? "#E2E8F0" : "#dc2626",
                  color: r.resolved_at ? "#6B7280" : "white",
                }}
              >
                Vòng {r.round}
              </span>
              <span className="text-xs" style={{ color: "#6B7280" }}>
                {r.requester_name}
              </span>
            </div>
            <span className="text-xs" style={{ color: "#94A3B8" }}>
              {new Date(r.requested_at).toLocaleString("vi-VN", {
                hour12: false,
              })}
            </span>
          </div>

          <p
            className="text-sm mb-2 whitespace-pre-wrap"
            style={{ color: "#0A1F44" }}
          >
            {r.feedback}
          </p>

          {r.document_feedback.length > 0 && (
            <ul className="space-y-1.5 mt-2 ml-2">
              {r.document_feedback.map((d, i) => (
                <li key={i} className="text-xs" style={{ color: "#374151" }}>
                  <span
                    className="font-mono px-1.5 py-0.5 rounded mr-1.5"
                    style={{
                      background:
                        d.severity === "critical"
                          ? "#dc2626"
                          : d.severity === "major"
                            ? "#f59e0b"
                            : "#94A3B8",
                      color: "white",
                      fontSize: "10px",
                    }}
                  >
                    {d.severity}
                  </span>
                  <strong>{docName(d.document_id)}:</strong> {d.issue}
                  {d.suggestion && (
                    <div className="ml-6 mt-0.5" style={{ color: "#6B7280" }}>
                      → {d.suggestion}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {r.resolved_at && (
            <p className="text-xs mt-2" style={{ color: "#102A5C" }}>
              ✓ Đã giải quyết:{" "}
              {new Date(r.resolved_at).toLocaleString("vi-VN", {
                hour12: false,
              })}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
