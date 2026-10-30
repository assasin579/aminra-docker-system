"use client";

/**
 * Loading skeletons — tận dụng .shimmer keyframe đã có trong globals.css.
 *
 * 4 variants chuẩn:
 *   <SkeletonText />        — 1 dòng text
 *   <SkeletonTitle />       — heading lớn
 *   <SkeletonAvatar />      — circle avatar
 *   <SkeletonCard />        — card placeholder
 *
 * Cũng có <Skeleton> generic để custom width/height tùy ý.
 */

interface SkeletonProps {
  /** Tailwind classes thêm */
  className?: string;
  /** Width — default 100% */
  width?: string;
  /** Height — default tùy variant */
  height?: string;
}

function baseStyle(width?: string, height?: string) {
  return {
    width: width ?? "100%",
    height: height ?? "1rem",
    borderRadius: "0.375rem",
  };
}

export function Skeleton({ className = "", width, height }: SkeletonProps) {
  return (
    <div
      className={`shimmer ${className}`}
      style={baseStyle(width, height)}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ className = "", width }: SkeletonProps) {
  return (
    <div
      className={`shimmer ${className}`}
      style={baseStyle(width ?? "100%", "0.875rem")}
      aria-hidden="true"
    />
  );
}

export function SkeletonTitle({ className = "", width }: SkeletonProps) {
  return (
    <div
      className={`shimmer ${className}`}
      style={baseStyle(width ?? "60%", "1.5rem")}
      aria-hidden="true"
    />
  );
}

export function SkeletonAvatar({ className = "" }: { className?: string }) {
  return (
    <div
      className={`shimmer ${className}`}
      style={{
        width: "2.5rem",
        height: "2.5rem",
        borderRadius: "9999px",
        flexShrink: 0,
      }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({
  rows = 3,
  className = "",
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl p-5 space-y-3 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      aria-busy="true"
      aria-live="polite"
    >
      <SkeletonTitle width="40%" />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonText key={i} width={`${90 - i * 8}%`} />
      ))}
    </div>
  );
}

/**
 * Stat card skeleton — match layout dashboard stats (icon + label + number).
 */
export function SkeletonStatCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-2xl p-5 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
      aria-busy="true"
    >
      <div className="flex items-center gap-3 mb-3">
        <SkeletonAvatar />
        <SkeletonText width="50%" />
      </div>
      <SkeletonTitle width="35%" />
    </div>
  );
}

/** Default export — generic skeleton */
export default Skeleton;
