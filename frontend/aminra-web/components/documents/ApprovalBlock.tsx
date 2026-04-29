"use client";

import type { ApprovalBlock as ApprovalData } from "@/lib/documentVersioning";
import ApprovalStatusBadge from "./ApprovalStatusBadge";

interface Props {
  data: ApprovalData;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

function isPast(iso: string | null): boolean {
  if (!iso) return false;
  try {
    return new Date(iso).getTime() < Date.now();
  } catch {
    return false;
  }
}

/**
 * Read-only display of approval metadata. Shows different content based on
 * approval state. Highlights overdue review dates in amber.
 */
export default function ApprovalBlock({ data }: Props) {
  const reviewOverdue = isPast(data.next_review_date);
  const retentionExpiringSoon = (() => {
    if (!data.retention_expires_at) return false;
    const ms = new Date(data.retention_expires_at).getTime() - Date.now();
    return ms > 0 && ms < 90 * 86400_000; // < 90 days remaining
  })();

  return (
    <div
      className="rounded-xl p-4 animate-section"
      style={{
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        boxShadow: "0 2px 8px rgba(10,31,68,0.04)",
      }}
      data-testid="approval-block"
    >
      {/* Header: status badge + version */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
          Trạng thái phê duyệt
        </h3>
        <ApprovalStatusBadge
          status={data.approval_status}
          versionNumber={data.version_number}
        />
      </div>

      {/* Approval details — only when relevant */}
      {data.approval_status === "approved" && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div>
            <dt className="text-xs" style={{ color: "#6B7280" }}>
              Người phê duyệt
            </dt>
            <dd style={{ color: "#0A1F44" }}>
              {data.approver_name || data.approver_email || "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs" style={{ color: "#6B7280" }}>
              Ngày phê duyệt
            </dt>
            <dd style={{ color: "#0A1F44" }}>{formatDate(data.approved_at)}</dd>
          </div>
          <div>
            <dt className="text-xs" style={{ color: "#6B7280" }}>
              Hiệu lực từ
            </dt>
            <dd style={{ color: "#0A1F44" }}>
              {formatDate(data.effective_date)}
            </dd>
          </div>
          <div>
            <dt className="text-xs" style={{ color: "#6B7280" }}>
              Đánh giá lại trước
            </dt>
            <dd style={{ color: reviewOverdue ? "#DC2626" : "#0A1F44" }}>
              {formatDate(data.next_review_date)}
              {reviewOverdue && (
                <span
                  className="ml-1 text-xs px-1.5 py-0.5 rounded"
                  style={{
                    background: "rgba(220,38,38,0.1)",
                    color: "#DC2626",
                  }}
                >
                  quá hạn
                </span>
              )}
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="text-xs" style={{ color: "#6B7280" }}>
              Lưu trữ đến
            </dt>
            <dd style={{ color: "#0A1F44" }}>
              {formatDate(data.retention_expires_at)}
              <span className="ml-2 text-xs" style={{ color: "#94A3B8" }}>
                ({data.retention_period_days} ngày · JAKIM yêu cầu tối thiểu 5
                năm)
              </span>
              {retentionExpiringSoon && (
                <span
                  className="ml-2 text-xs px-1.5 py-0.5 rounded"
                  style={{
                    background: "rgba(245,158,11,0.12)",
                    color: "#B45309",
                  }}
                >
                  sắp hết hạn lưu trữ
                </span>
              )}
            </dd>
          </div>
        </dl>
      )}

      {data.approval_status === "pending_approval" && (
        <p className="text-sm" style={{ color: "#6B7280" }}>
          Tài liệu đang chờ phê duyệt từ chủ tài khoản hoặc thành viên IHC.
        </p>
      )}

      {data.approval_status === "draft" && (
        <p className="text-sm" style={{ color: "#6B7280" }}>
          Bản nháp chưa được trình duyệt. Khi sẵn sàng, hãy bấm{" "}
          <strong>Trình duyệt</strong>.
        </p>
      )}

      {data.approval_status === "obsolete" && (
        <p className="text-sm" style={{ color: "#6B7280" }}>
          Phiên bản này đã được thay thế bằng tài liệu mới.
          {data.superseded_by_id && (
            <span
              className="ml-2 font-mono text-xs"
              style={{ color: "#94A3B8" }}
            >
              ({data.superseded_by_id.slice(0, 8)}…)
            </span>
          )}
        </p>
      )}
    </div>
  );
}
