"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { parseApiError } from "@/lib/apiError";

type Severity = "minor" | "major" | "critical";

interface DocumentInfo {
  id: string;
  filename: string;
  doc_type?: string | null;
}

type SnapshotDocument = DocumentInfo;

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
  business_response: string | null;
  submitted_document_ids?: string[];
  submitted_documents?: SnapshotDocument[];
}

interface Props {
  submissionId: string;
  status: string;
  role: "business" | "provider";
  documents: DocumentInfo[];
  token: string;
  canResubmit?: boolean;
  onChanged?: () => void; // notify parent to refetch submission
}

export default function RevisionPanel({
  submissionId,
  status,
  role,
  documents,
  token,
  onChanged,
  canResubmit = false,
}: Props) {
  const [history, setHistory] = useState<RevisionRound[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const historyRequest = useRef(0);
  const historyScope = useRef(submissionId);
  const [historyReady, setHistoryReady] = useState(false);
  const fetchHistory = useCallback(async () => {
    const request = ++historyRequest.current;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `/api/api/submissions/${submissionId}/revisions`,
        {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        },
      );
      if (!res.ok) throw new Error(`Lỗi ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data.history)) throw new Error("Dữ liệu lịch sử không hợp lệ");
      if (request === historyRequest.current) {
        setHistory(data.history);
        setHistoryReady(true);
      }
    } catch (err) {
      if (request === historyRequest.current) setError(err instanceof Error ? err.message : "Lỗi tải lịch sử");
    } finally {
      if (request === historyRequest.current) setLoading(false);
    }
  }, [submissionId, token]);

  // Re-fetch on status change too — after a resubmit / request_revision the
  // parent refreshes the submission, status flips, and we want the new round
  // (or the new business_response field) to land without a manual reload.
  useEffect(() => {
    if (historyScope.current !== submissionId) {
      historyScope.current = submissionId;
      setHistory([]);
      setHistoryReady(false);
    }
    void fetchHistory();
    return () => { historyRequest.current++; };
  }, [fetchHistory, status, submissionId]);

  // Determine what the panel can do based on role + status
  const providerCanRequest =
    role === "provider" && (status === "reviewing" || status === "returned");
  const businessCanResubmit =
    role === "business" && canResubmit && status === "revision_required";
  const hasAction = providerCanRequest || businessCanResubmit;
  const hasHistory = history.length > 0;

  // Hide panel entirely when nothing actionable + no history (common on
  // freshly-submitted/approved submissions — avoids visually-dead block).
  if (!loading && !error && !hasAction && !hasHistory && status !== "returned") {
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
          <button type="button" className="ml-3 underline" onClick={() => void fetchHistory()}>Thử tải lại lịch sử</button>
        </div>
      )}

      {/* Provider action — request revision */}
      {providerCanRequest && historyReady && (
        <fieldset disabled={loading || Boolean(error)}>
        <RequestRevisionForm
          submissionId={submissionId}
          documents={documents}
          token={token}
          onRequested={() => {
            fetchHistory();
            onChanged?.();
          }}
        />
        </fieldset>
      )}

      {/* Business action — resubmit */}
      {businessCanResubmit && historyReady && (
        <fieldset disabled={loading || Boolean(error)}>
        <ResubmitForm
          submissionId={submissionId}
          documents={documents}
          token={token}
          onResubmitted={() => {
            fetchHistory();
            onChanged?.();
          }}
        />
        </fieldset>
      )}

      {role === "business" && status === "returned" && (
        <p role="status" className="mb-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          CB đã trả lại hồ sơ. Hãy liên hệ CB để nhận yêu cầu sửa có nội dung cụ thể trước khi gửi lại.
        </p>
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
  const formId = useId();
  const [feedback, setFeedback] = useState("");
  const [docFeedback, setDocFeedback] = useState<DocumentFeedbackItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);
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
    const payload = {
      feedback: feedback.trim(),
      document_feedback: docFeedback.filter((d) => d.issue.trim() && d.document_id),
    };
    const fingerprint = JSON.stringify({ submissionId, payload });
    if (attempt.current?.fingerprint !== fingerprint) {
      attempt.current = { fingerprint, key: crypto.randomUUID() };
    }
    try {
      const res = await fetch(
        `/api/api/submissions/received/${submissionId}/request-revision`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
            "Idempotency-Key": attempt.current.key,
          },
          body: JSON.stringify(payload),
        },
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseApiError(body, `Lỗi ${res.status}`));
      attempt.current = null;
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
          htmlFor={`${formId}-feedback`}
          className="block text-xs font-medium mb-1"
          style={{ color: "#6B7280" }}
        >
          Nội dung yêu cầu sửa
        </label>
        <textarea
          id={`${formId}-feedback`}
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
          <div className="flex flex-wrap gap-2 mb-2">
            <select
              aria-label={`Tài liệu có vấn đề ${i + 1}`}
              value={d.document_id}
              onChange={(e) =>
                updateDocIssue(i, { document_id: e.target.value })
              }
              className="min-w-0 flex-1 px-2 py-1 text-xs rounded border"
              style={{ borderColor: "#E2E8F0" }}
            >
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <select
              aria-label={`Mức độ vấn đề ${i + 1}`}
              value={d.severity}
              onChange={(e) =>
                updateDocIssue(i, { severity: e.target.value as Severity })
              }
              className="px-2 py-1 text-xs rounded border"
              style={{ borderColor: "#E2E8F0" }}
            >
              <option value="minor">Nhẹ</option>
              <option value="major">Nghiêm trọng</option>
              <option value="critical">Tới hạn</option>
            </select>
            <button
              type="button"
              aria-label={`Xóa vấn đề ${i + 1}`}
              onClick={() => removeDocIssue(i)}
              className="text-xs px-2 py-1 rounded"
              style={{ color: "#991b1b" }}
            >
              ×
            </button>
          </div>
          <input
            type="text"
            aria-label={`Nội dung vấn đề ${i + 1}`}
            value={d.issue}
            onChange={(e) => updateDocIssue(i, { issue: e.target.value })}
            placeholder="Vấn đề cụ thể (vd: Thiếu dấu JAKIM)"
            className="w-full px-2 py-1.5 text-sm rounded mb-1"
            style={{ border: "1px solid #E2E8F0" }}
          />
          <input
            type="text"
            aria-label={`Gợi ý khắc phục ${i + 1}`}
            value={d.suggestion ?? ""}
            onChange={(e) => updateDocIssue(i, { suggestion: e.target.value })}
            placeholder="Gợi ý khắc phục (tùy chọn)"
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
        + Thêm vấn đề theo tài liệu
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
  const notesId = useId();
  const [businessNotes, setBusinessNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const idempotencyKey = useRef<string | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const key = idempotencyKey.current ?? crypto.randomUUID();
      idempotencyKey.current = key;
      const res = await fetch(`/api/api/submissions/${submissionId}/resubmit`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": key,
        },
        body: JSON.stringify({ business_notes: businessNotes.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseApiError(body, `Lỗi ${res.status}`));
      idempotencyKey.current = null;
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
      <label htmlFor={notesId} className="block text-sm font-medium">Phản hồi về nội dung đã sửa (tùy chọn)</label>
      <textarea
        id={notesId}
        value={businessNotes}
        onChange={(e) => {
          idempotencyKey.current = null;
          setBusinessNotes(e.target.value);
        }}
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
  const docName = (round: RevisionRound, id: string) =>
    round.submitted_documents?.find((doc) => doc.id === id)?.filename
    ?? documents.find((doc) => doc.id === id)?.filename
    ?? `Tài liệu ${id.slice(0, 8)}… (thiếu tên lịch sử)`;

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

  const latest = history[0];
  const snapshotIds = latest?.submitted_document_ids ?? [];
  const snapshotDocs = latest?.submitted_documents ?? [];
  const hasCompleteSnapshot = snapshotIds.length > 0 && snapshotIds.every((id) => snapshotDocs.some((doc) => doc.id === id));
  const previous = new Map(snapshotDocs.map((doc) => [doc.id, doc]));
  const current = new Map(documents.map((doc) => [doc.id, doc]));
  const retained = [...previous.keys()].filter((id) => current.has(id)).map((id) => previous.get(id)!);
  const removed = [...previous.keys()].filter((id) => !current.has(id)).map((id) => previous.get(id)!);
  const added = [...current.keys()].filter((id) => !previous.has(id)).map((id) => current.get(id)!);
  const replaced: { old: DocumentInfo; next: DocumentInfo }[] = [];
  for (const type of new Set(removed.map((doc) => doc.doc_type).filter((value): value is string => Boolean(value)))) {
    const oldOfType = removed.filter((doc) => doc.doc_type === type);
    const newOfType = added.filter((doc) => doc.doc_type === type);
    if (oldOfType.length === 1 && newOfType.length === 1) {
      replaced.push({ old: oldOfType[0], next: newOfType[0] });
    }
  }
  const replacedOld = new Set(replaced.map((item) => item.old.id));
  const replacedNew = new Set(replaced.map((item) => item.next.id));
  const remainingRemoved = removed.filter((doc) => !replacedOld.has(doc.id));
  const remainingAdded = added.filter((doc) => !replacedNew.has(doc.id));

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium" style={{ color: "#6B7280" }}>
        Lịch sử các vòng sửa
      </h4>
      {hasCompleteSnapshot && latest && (
        <section aria-label={`So sánh bằng chứng vòng ${latest.round}`} className="rounded-lg p-3 bg-slate-50">
          <h5 className="text-sm font-semibold mb-2">Đối chiếu vòng {latest.round} với bộ hồ sơ hiện tại</h5>
          <p>Được giữ nguyên: {retained.map((doc) => doc.filename).join(", ") || "Không có"}</p>
          {replaced.map(({ old, next }) => <p key={old.id}>Đã thay thế: {old.filename} → {next.filename}</p>)}
          <p>Được thêm: {remainingAdded.map((doc) => doc.filename).join(", ") || "Không có"}</p>
          <p>Đã loại bỏ: {remainingRemoved.map((doc) => doc.filename).join(", ") || "Không có"}</p>
        </section>
      )}
      {!hasCompleteSnapshot && latest && snapshotIds.length > 0 && (
        <p role="status">Không đủ metadata snapshot để đối chiếu chính xác vòng {latest.round}.</p>
      )}
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
                  <strong>{docName(r, d.document_id)}:</strong> {d.issue}
                  {d.suggestion && (
                    <div className="ml-6 mt-0.5" style={{ color: "#6B7280" }}>
                      → {d.suggestion}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {r.business_response && (
            <div
              className="mt-3 rounded-lg p-2.5 text-sm"
              style={{
                background: "rgba(38, 194, 154, 0.08)",
                border: "1px solid rgba(38, 194, 154, 0.25)",
              }}
            >
              <div
                className="text-xs font-medium mb-1"
                style={{ color: "#0A6B4F" }}
              >
                Phản hồi từ doanh nghiệp
              </div>
              <p
                className="whitespace-pre-wrap"
                style={{ color: "#0A1F44" }}
              >
                {r.business_response}
              </p>
            </div>
          )}

          {r.resolved_at && (
            <p className="text-xs mt-2" style={{ color: "#102A5C" }}>
              ✓ Doanh nghiệp đã gửi lại:{" "}
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
