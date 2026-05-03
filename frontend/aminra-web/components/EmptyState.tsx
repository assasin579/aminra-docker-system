"use client";

import { type ReactNode } from "react";
import Link from "next/link";

interface Props {
  /** Icon hiển thị ở giữa (svg/emoji/element). Mặc định folder icon. */
  icon?: ReactNode;
  /** Tiêu đề chính (vd: "Chưa có tài liệu nào") */
  title: string;
  /** Mô tả phụ (1-2 câu giải thích) */
  description?: string;
  /** Nút CTA chính (text + href hoặc onClick). Optional. */
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  /** Action phụ (link nhỏ, vd: "Xem hướng dẫn") */
  secondaryAction?: { label: string; href: string };
  /** Compact variant — dùng trong card nhỏ */
  compact?: boolean;
}

/**
 * Empty state chuẩn — tận dụng .animate-empty-icon (float bob) + .animate-section.
 *
 * Usage:
 *   <EmptyState
 *     title="Chưa có submission nào"
 *     description="Tạo hồ sơ đầu tiên để bắt đầu quy trình chứng nhận."
 *     action={{ label: "Tạo hồ sơ mới", href: "/create-document" }}
 *   />
 */
export default function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  compact = false,
}: Props) {
  const defaultIcon = (
    <svg
      className="w-full h-full"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );

  const iconSize = compact ? "w-10 h-10" : "w-16 h-16";
  const padding = compact ? "py-8" : "py-16";

  return (
    <div
      className={`flex flex-col items-center text-center ${padding} px-4 animate-section`}
    >
      <div
        className={`${iconSize} mb-4 animate-empty-icon`}
        style={{ color: "var(--text-muted)" }}
        aria-hidden="true"
      >
        {icon ?? defaultIcon}
      </div>
      <h3
        className={
          compact ? "text-base font-semibold" : "text-lg font-semibold mb-2"
        }
        style={{ color: "var(--text-primary)" }}
      >
        {title}
      </h3>
      {description && (
        <p
          className={`${compact ? "text-sm" : "text-base"} max-w-md mb-6`}
          style={{ color: "var(--text-secondary)" }}
        >
          {description}
        </p>
      )}
      {(action || secondaryAction) && (
        <div className="flex items-center gap-3 flex-wrap justify-center">
          {action &&
            (action.href ? (
              <Link
                href={action.href}
                className="btn-shine glow-hover-gold inline-flex items-center px-5 py-2.5 rounded-xl font-semibold text-sm"
                style={{ background: "var(--accent)", color: "var(--primary)" }}
              >
                {action.label}
              </Link>
            ) : (
              <button
                type="button"
                onClick={action.onClick}
                className="btn-shine glow-hover-gold inline-flex items-center px-5 py-2.5 rounded-xl font-semibold text-sm"
                style={{ background: "var(--accent)", color: "var(--primary)" }}
              >
                {action.label}
              </button>
            ))}
          {secondaryAction && (
            <Link
              href={secondaryAction.href}
              className="text-sm font-medium underline-offset-2 hover:underline"
              style={{ color: "var(--text-secondary)" }}
            >
              {secondaryAction.label}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
