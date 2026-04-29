"use client";

import { useState } from "react";
import {
  type ApprovalBlock as ApprovalData,
  approveDocument,
  rejectDocument,
  submitForApproval,
} from "@/lib/documentVersioning";

interface UserPerms {
  canEdit: boolean;
  canApproveDocuments: boolean;
  isOwner: boolean;
  isIhcMember: boolean;
}

interface Props {
  docId: string;
  approval: ApprovalData;
  perms: UserPerms;
  token: string;
  /** Called after a successful state transition so parent can refetch */
  onChanged: () => void;
}

/**
 * Role-conditional action buttons. Only renders buttons the current user
 * can actually use given their permissions and the document state.
 *
 * State machine cells:
 *   draft + can_edit            → Trình duyệt
 *   pending + can_approve_docs  → Phê duyệt | Từ chối
 *   approved + owner_or_ihc     → Thay thế bằng phiên bản mới (modal in parent)
 *   obsolete / no perm          → no buttons rendered
 */
export default function ApprovalActions({
  docId,
  approval,
  perms,
  token,
  onChanged,
}: Props) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    setPending(true);
    try {
      await submitForApproval(docId, token);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể trình duyệt");
    } finally {
      setPending(false);
    }
  };

  const buttons: React.ReactNode[] = [];

  if (approval.approval_status === "draft" && perms.canEdit) {
    buttons.push(
      <button
        key="submit"
        type="button"
        onClick={handleSubmit}
        disabled={pending}
        className="btn-lift px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
        style={{ background: "#0A1F44" }}
      >
        {pending ? "Đang gửi..." : "Trình duyệt"}
      </button>,
    );
  }

  if (
    approval.approval_status === "pending_approval" &&
    perms.canApproveDocuments
  ) {
    buttons.push(
      <button
        key="approve"
        type="button"
        onClick={() => setShowApproveModal(true)}
        disabled={pending}
        className="btn-lift px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
        style={{ background: "#102A5C" }}
      >
        Phê duyệt
      </button>,
      <button
        key="reject"
        type="button"
        onClick={() => setShowRejectModal(true)}
        disabled={pending}
        className="btn-lift px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
        style={{
          background: "rgba(220,38,38,0.1)",
          color: "#DC2626",
          border: "1px solid rgba(220,38,38,0.3)",
        }}
      >
        Từ chối
      </button>,
    );
  }

  // (Supersede flow is more complex — needs new doc id from upload; deferred
  // to parent page since it touches existing upload UI.)

  if (buttons.length === 0 && !error) return null;

  return (
    <>
      <div className="flex flex-wrap gap-2 items-center">
        {buttons}
        {error && (
          <span
            className="text-xs px-3 py-1 rounded-lg"
            style={{
              background: "rgba(220,38,38,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(220,38,38,0.2)",
            }}
          >
            {error}
          </span>
        )}
      </div>

      {showApproveModal && (
        <ApproveModal
          docId={docId}
          token={token}
          onClose={() => setShowApproveModal(false)}
          onSuccess={() => {
            setShowApproveModal(false);
            onChanged();
          }}
        />
      )}

      {showRejectModal && (
        <RejectModal
          docId={docId}
          token={token}
          onClose={() => setShowRejectModal(false)}
          onSuccess={() => {
            setShowRejectModal(false);
            onChanged();
          }}
        />
      )}
    </>
  );
}

// ── Approve modal ──────────────────────────────────────────────────────────

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function plusYearIso(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

interface ModalCommon {
  docId: string;
  token: string;
  onClose: () => void;
  onSuccess: () => void;
}

function ApproveModal({ docId, token, onClose, onSuccess }: ModalCommon) {
  const [effectiveDate, setEffectiveDate] = useState(todayIso());
  const [nextReviewDate, setNextReviewDate] = useState(plusYearIso());
  const [retentionDays, setRetentionDays] = useState(1825);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPast = new Date(effectiveDate).getTime() < Date.now() - 86_400_000;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (retentionDays < 1825) {
      setError(
        "Thời gian lưu trữ tối thiểu 1825 ngày (5 năm) — yêu cầu của JAKIM",
      );
      return;
    }
    setError(null);
    setPending(true);
    try {
      await approveDocument(
        docId,
        {
          effective_date: effectiveDate,
          next_review_date: nextReviewDate,
          retention_period_days: retentionDays,
        },
        token,
      );
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Phê duyệt thất bại");
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
      style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
        }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
            Phê duyệt tài liệu
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg grid place-items-center"
            style={{ background: "rgba(0,0,0,0.05)" }}
          >
            <span>✕</span>
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Hiệu lực từ
            </label>
            <input
              type="date"
              required
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />
            {isPast && (
              <p className="text-xs mt-1" style={{ color: "#B45309" }}>
                ⚠ Ngày hiệu lực ở quá khứ (backdating). Audit log sẽ ghi lại.
              </p>
            )}
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Đánh giá lại trước
            </label>
            <input
              type="date"
              required
              value={nextReviewDate}
              onChange={(e) => setNextReviewDate(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Lưu trữ (ngày)
            </label>
            <input
              type="number"
              required
              min={1825}
              value={retentionDays}
              onChange={(e) => setRetentionDays(parseInt(e.target.value) || 0)}
              className="w-full px-3 py-2 rounded-lg text-sm"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />
            <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
              Tối thiểu 1825 ngày (5 năm). JAKIM/BPJPH yêu cầu để audit.
            </p>
          </div>

          {error && (
            <p
              className="text-xs px-3 py-2 rounded-lg"
              style={{
                background: "rgba(220,38,38,0.1)",
                color: "#DC2626",
                border: "1px solid rgba(220,38,38,0.2)",
              }}
            >
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 mt-6">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: "rgba(0,0,0,0.05)",
              color: "#6B7280",
            }}
          >
            Huỷ
          </button>
          <button
            type="submit"
            disabled={pending}
            className="btn-lift px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "#102A5C" }}
          >
            {pending ? "Đang phê duyệt..." : "Phê duyệt"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Reject modal ──────────────────────────────────────────────────────────

function RejectModal({ docId, token, onClose, onSuccess }: ModalCommon) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    if (!trimmed) {
      setError("Vui lòng nhập lý do từ chối");
      return;
    }
    if (trimmed.length > 500) {
      setError("Lý do tối đa 500 ký tự");
      return;
    }
    setError(null);
    setPending(true);
    try {
      await rejectDocument(docId, trimmed, token);
      onSuccess();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Từ chối thất bại");
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
      style={{ background: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E2E8F0",
          boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
        }}
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
            Từ chối tài liệu
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg grid place-items-center"
            style={{ background: "rgba(0,0,0,0.05)" }}
          >
            <span>✕</span>
          </button>
        </div>

        <div>
          <label
            className="block text-xs font-medium mb-1.5"
            style={{ color: "#6B7280" }}
          >
            Lý do từ chối *
          </label>
          <textarea
            required
            rows={4}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="VD: Thiếu phần truy xuất nguồn gốc nguyên liệu E471"
            className="w-full px-3 py-2 rounded-lg text-sm"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0A1F44",
              resize: "vertical",
            }}
          />
          <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
            {reason.length}/500 ký tự. Người gửi sẽ thấy lý do này trong audit
            log.
          </p>
        </div>

        {error && (
          <p
            className="text-xs mt-3 px-3 py-2 rounded-lg"
            style={{
              background: "rgba(220,38,38,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(220,38,38,0.2)",
            }}
          >
            {error}
          </p>
        )}

        <div className="flex items-center justify-end gap-2 mt-6">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: "rgba(0,0,0,0.05)",
              color: "#6B7280",
            }}
          >
            Huỷ
          </button>
          <button
            type="submit"
            disabled={pending}
            className="btn-lift px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: "rgba(220,38,38,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(220,38,38,0.3)",
            }}
          >
            {pending ? "Đang từ chối..." : "Xác nhận từ chối"}
          </button>
        </div>
      </form>
    </div>
  );
}
