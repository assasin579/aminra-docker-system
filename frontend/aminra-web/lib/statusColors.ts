/**
 * Single source of truth cho semantic colors trên UI.
 *
 * Trước đây mỗi badge component (SlaBadge, ApprovalStatusBadge, ExpiryUrgency,
 * Dashboard inline maps) tự định nghĩa màu cho "success/warning/danger" → 1
 * status có thể có 3 sắc độ khác nhau ở 3 nơi.
 *
 * Dùng helper này thay vì hardcode hex:
 *   const c = semantic("danger");
 *   <span style={{ background: c.bg, color: c.fg, border: `1px solid ${c.border}` }}>
 */

export type SemanticLevel =
  | "success" // approved, valid, healthy
  | "warning" // sắp hết hạn, sắp deadline, attention needed
  | "danger" // overdue, rejected, revoked
  | "info" // pending, queued, in-progress
  | "neutral"; // draft, archived, không trạng thái

export interface SemanticPalette {
  /** Background fill for badge/chip */
  bg: string;
  /** Text color (foreground) */
  fg: string;
  /** Border color (often slightly darker than bg) */
  border: string;
  /** Solid color for icons or accents */
  solid: string;
}

const PALETTES: Record<SemanticLevel, SemanticPalette> = {
  success: {
    bg: "rgba(16, 185, 129, 0.12)",
    fg: "#047857",
    border: "rgba(16, 185, 129, 0.3)",
    solid: "#10b981",
  },
  warning: {
    bg: "rgba(245, 158, 11, 0.12)",
    fg: "#b45309",
    border: "rgba(245, 158, 11, 0.3)",
    solid: "#f59e0b",
  },
  danger: {
    bg: "rgba(220, 38, 38, 0.12)",
    fg: "#b91c1c",
    border: "rgba(220, 38, 38, 0.3)",
    solid: "#dc2626",
  },
  info: {
    // Dùng navy (brand) cho info, không xanh dương lạnh chung
    bg: "rgba(36, 74, 138, 0.1)",
    fg: "#102a5c",
    border: "rgba(36, 74, 138, 0.25)",
    solid: "#234a8a",
  },
  neutral: {
    bg: "rgba(110, 110, 110, 0.1)",
    fg: "#374151",
    border: "rgba(110, 110, 110, 0.22)",
    solid: "#6e6e6e",
  },
};

/** Lấy palette cho 1 semantic level. */
export function semantic(level: SemanticLevel): SemanticPalette {
  return PALETTES[level];
}

/** Solid variant — dùng khi muốn fill đậm (vd: "QUÁ HẠN" badge). */
export function semanticSolid(level: SemanticLevel): {
  bg: string;
  fg: string;
} {
  const p = PALETTES[level];
  return { bg: p.solid, fg: "#ffffff" };
}

/**
 * Map từ submission/document status string → semantic level.
 * Mở rộng khi có status mới — KHÔNG hardcode màu trong component nữa.
 */
const STATUS_TO_SEMANTIC: Record<string, SemanticLevel> = {
  // Submission lifecycle
  draft: "neutral",
  submitted: "info",
  reviewing: "info",
  assigned: "info",
  approved: "success",
  rejected: "danger",
  returned: "warning",
  revision_required: "warning",
  // Audit/cert
  scheduled: "info",
  in_progress: "info",
  completed: "success",
  report_submitted: "success",
  active: "success",
  expired: "danger",
  revoked: "danger",
  expiring_soon: "warning",
  // NCR
  open: "warning",
  pending_verification: "info",
  closed: "success",
};

export function statusToSemantic(status: string): SemanticLevel {
  return STATUS_TO_SEMANTIC[status] ?? "neutral";
}

/** Convenience — gộp `statusToSemantic` + `semantic` thành 1 lookup. */
export function statusPalette(status: string): SemanticPalette {
  return semantic(statusToSemantic(status));
}
