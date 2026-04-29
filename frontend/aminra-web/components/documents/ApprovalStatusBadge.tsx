"use client";

import {
  type ApprovalStatus,
  approvalStatusColors,
  approvalStatusLabel,
} from "@/lib/documentVersioning";

interface Props {
  status: ApprovalStatus;
  /** Optional version number — shown after the label as `· v3` */
  versionNumber?: number;
  /** Smaller variant for inline use in tables */
  compact?: boolean;
}

/**
 * Small pill showing approval state. Used in document list rows + detail header.
 */
export default function ApprovalStatusBadge({
  status,
  versionNumber,
  compact = false,
}: Props) {
  const colors = approvalStatusColors(status);
  const padding = compact ? "px-2 py-0.5" : "px-3 py-1";
  const fontSize = compact ? "text-xs" : "text-sm";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${padding} ${fontSize}`}
      style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.text,
      }}
      data-approval-status={status}
    >
      <span>{approvalStatusLabel(status)}</span>
      {versionNumber !== undefined && versionNumber > 1 && (
        <span style={{ opacity: 0.65 }}>· v{versionNumber}</span>
      )}
    </span>
  );
}
