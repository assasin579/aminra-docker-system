"use client";

/**
 * Modal — render qua React Portal vào document.body để escape mọi containing
 * block do parent có transform/filter/perspective/contain. Fix triệt để bug
 * "modal bị kéo tụt xuống" khi parent có animation/transform.
 *
 * Backwards-compatible: dùng cùng class system (.animate-modal-overlay,
 * .animate-modal-content) như các modal cũ. Chỉ wrap.
 *
 * Usage:
 *   {showModal && (
 *     <Modal onClose={() => setShowModal(false)}>
 *       <div className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
 *            style={{ background: "#FFFFFF" }}>
 *         ...form content...
 *       </div>
 *     </Modal>
 *   )}
 */

import { useEffect, useState, type ReactNode, type MouseEvent } from "react";
import { createPortal } from "react-dom";

interface Props {
  children: ReactNode;
  /** Click backdrop để đóng. Truyền undefined nếu không muốn click-outside-to-close. */
  onClose?: () => void;
  /** Extra className cho backdrop wrapper (Tailwind / CSS) */
  className?: string;
}

export default function Modal({ children, onClose, className = "" }: Props) {
  const [mounted, setMounted] = useState(false);

  // Mount-after-hydration: createPortal cần document tồn tại
  useEffect(() => {
    setMounted(true);
    // Khoá scroll body khi modal mở
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  // ESC key đóng modal
  useEffect(() => {
    if (!onClose) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!mounted) return null;

  const handleBackdropClick = (e: MouseEvent<HTMLDivElement>) => {
    // Chỉ đóng khi click vào backdrop, KHÔNG đóng khi click vào content trong
    if (e.target === e.currentTarget && onClose) onClose();
  };

  return createPortal(
    <div
      className={`fixed inset-0 z-[100] grid place-items-center p-4 animate-modal-overlay ${className}`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
    >
      {children}
    </div>,
    document.body,
  );
}
