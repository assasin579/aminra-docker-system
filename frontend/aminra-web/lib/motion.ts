"use client";

import { useEffect, useRef } from "react";

/**
 * Card spotlight: sets --mx/--my CSS vars on the element from cursor position.
 * Pair with `.spotlight-card` class in globals.css.
 *
 *   const ref = useCardSpotlight<HTMLDivElement>();
 *   <div ref={ref} className="spotlight-card ..."> ... </div>
 */
export function useCardSpotlight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      el.style.setProperty("--mx", `${x}%`);
      el.style.setProperty("--my", `${y}%`);
    };

    const onLeave = () => {
      el.style.setProperty("--mx", "50%");
      el.style.setProperty("--my", "50%");
    };

    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return ref;
}

/**
 * useTilt: 3D tilt-on-hover via CSS variables. Pair with `.tilt-hover`.
 * Cursor offset normalized to [-1, 1] in --tx/--ty.
 */
export function useTilt<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const tx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      const ty = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      el.style.setProperty("--tx", tx.toFixed(3));
      el.style.setProperty("--ty", ty.toFixed(3));
    };

    const onLeave = () => {
      el.style.setProperty("--tx", "0");
      el.style.setProperty("--ty", "0");
    };

    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return ref;
}
