"use client";

import { useEffect, useRef, useState, type ReactNode, type MouseEvent } from "react";
import { createPortal } from "react-dom";

interface Props {
  children: ReactNode;
  onClose?: () => void;
  className?: string;
  ariaLabel?: string;
}

const openDialogs = new Set<HTMLElement>();
let originalBodyOverflow = "";

const focusableSelector = 'button:not([disabled]), a[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Modal({ children, onClose, className = "", ariaLabel = "Hộp thoại" }: Props) {
  const [mounted, setMounted] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (openDialogs.size === 0) originalBodyOverflow = document.body.style.overflow;
    openDialogs.add(dialog);
    document.body.style.overflow = "hidden";
    const isTop = () => Array.from(document.querySelectorAll('[data-aminra-modal]')).at(-1) === dialog;
    const focusables = () => Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector))
      .filter((node) => !node.closest('[hidden], [inert], [aria-hidden="true"]') && getComputedStyle(node).display !== 'none' && getComputedStyle(node).visibility !== 'hidden');
    (focusables()[0] ?? dialog).focus();
    const handler = (event: KeyboardEvent) => {
      if (!isTop()) return;
      if (event.key === "Escape") { event.stopPropagation(); closeRef.current?.(); }
      if (event.key !== "Tab") return;
      const items = focusables();
      const first = items[0];
      const last = items.at(-1);
      if (!first || !last) { event.preventDefault(); dialog.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
        event.preventDefault(); first.focus();
      }
    };
    const keepFocus = (event: FocusEvent) => {
      if (isTop() && event.target instanceof Node && !dialog.contains(event.target)) (focusables()[0] ?? dialog).focus();
    };
    window.addEventListener("keydown", handler);
    document.addEventListener("focusin", keepFocus);
    return () => {
      window.removeEventListener("keydown", handler);
      document.removeEventListener("focusin", keepFocus);
      openDialogs.delete(dialog);
      if (openDialogs.size === 0) document.body.style.overflow = originalBodyOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [mounted]);

  if (!mounted) return null;
  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) onClose?.();
  };
  return createPortal(
    <div ref={dialogRef} data-aminra-modal tabIndex={-1}
      className={`fixed inset-0 z-[100] grid place-items-center p-4 animate-modal-overlay ${className}`}
      onClick={handleBackdropClick} role="dialog" aria-modal="true" aria-label={ariaLabel}>
      {children}
    </div>, document.body,
  );
}
