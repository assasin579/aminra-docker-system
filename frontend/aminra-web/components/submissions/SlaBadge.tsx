"use client";

/**
 * SLA badge for submission cards.
 *
 * Computes elapsed % from submitted_at + deadline + now (client-side, no API
 * call). Shows visual urgency signal aligned with backend's daily scanner
 * (80% TTL = warning, 100%+ = overdue).
 */

interface Props {
  submittedAt: string | null;
  deadline: string | null;
  status: string;
}

const TERMINAL_STATUSES = new Set(["approved", "rejected", "returned"]);

export default function SlaBadge({ submittedAt, deadline, status }: Props) {
  // No deadline → no SLA tracking
  if (!submittedAt || !deadline) return null;
  // Terminal states → no SLA badge (no longer at-risk)
  if (TERMINAL_STATUSES.has(status)) return null;

  const submittedMs = new Date(submittedAt).getTime();
  const deadlineMs = new Date(deadline).getTime();
  const nowMs = Date.now();

  // Malformed window
  if (isNaN(submittedMs) || isNaN(deadlineMs) || deadlineMs <= submittedMs)
    return null;

  const totalSeconds = (deadlineMs - submittedMs) / 1000;
  const elapsedSeconds = (nowMs - submittedMs) / 1000;
  const elapsedPct = (elapsedSeconds / totalSeconds) * 100;
  const daysRemaining = Math.floor(
    (deadlineMs - nowMs) / (1000 * 60 * 60 * 24),
  );

  // Tier 1: overdue (>= 100%)
  if (elapsedPct >= 100) {
    return (
      <span
        title={`Quá hạn ${Math.abs(daysRemaining)} ngày`}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold"
        style={{ background: "#dc2626", color: "white" }}
        data-sla="overdue"
      >
        🚨 QUÁ HẠN {Math.abs(daysRemaining)}d
      </span>
    );
  }

  // Tier 2: warning (>= 80%)
  if (elapsedPct >= 80) {
    return (
      <span
        title={`Còn ${daysRemaining} ngày tới deadline`}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold"
        style={{
          background: "rgba(245,158,11,0.15)",
          color: "#b45309",
          border: "1px solid rgba(245,158,11,0.3)",
        }}
        data-sla="warning"
      >
        ⚠ Sắp hết hạn ({daysRemaining}d)
      </span>
    );
  }

  // Healthy: no badge (avoid clutter on cards still well within SLA)
  return null;
}
