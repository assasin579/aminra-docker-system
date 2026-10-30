"use client";

import {
  type ReactNode,
  type MouseEvent,
  type ButtonHTMLAttributes,
  useRef,
  useCallback,
} from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Cường độ pull (1.0 = di chuyển 1:1 với cursor; 0.3 default = subtle). */
  strength?: number;
  /** Bán kính ảnh hưởng tính theo px (cursor cách button hơn radius này → reset). */
  radius?: number;
  children: ReactNode;
}

/**
 * Magnetic button — nhẹ nhàng follow cursor khi di gần.
 *
 * Feel "premium" cho hero CTA. KHÔNG dùng tràn lan — chỉ 1-2 button
 * quan trọng nhất per page.
 *
 * Auto-disable nếu user prefers-reduced-motion.
 */
export default function MagneticButton({
  strength = 0.3,
  radius = 100,
  children,
  className = "",
  style,
  onMouseMove,
  onMouseLeave,
  ...rest
}: Props) {
  const ref = useRef<HTMLButtonElement>(null);

  const handleMove = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      onMouseMove?.(e);
      const btn = ref.current;
      if (!btn) return;
      // Respect reduced-motion
      if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
        return;

      const rect = btn.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy);

      if (dist > radius) {
        btn.style.transform = "translate3d(0, 0, 0)";
        return;
      }
      // Normalize falloff: gần center → max pull, gần edge → ít hơn
      const falloff = 1 - dist / radius;
      const tx = dx * strength * falloff;
      const ty = dy * strength * falloff;
      btn.style.transform = `translate3d(${tx}px, ${ty}px, 0)`;
    },
    [strength, radius, onMouseMove],
  );

  const handleLeave = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      onMouseLeave?.(e);
      if (ref.current) {
        ref.current.style.transform = "translate3d(0, 0, 0)";
      }
    },
    [onMouseLeave],
  );

  return (
    <button
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      className={`btn-shine ${className}`}
      style={{
        transition: "transform 0.25s var(--ease-out-expo)",
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
