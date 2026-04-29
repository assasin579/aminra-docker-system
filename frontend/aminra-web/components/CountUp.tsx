'use client';

import { useEffect, useRef, useState } from 'react';

interface CountUpProps {
  value: number;
  duration?: number;        // ms
  decimals?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  /** Format helper for locale-formatted output (e.g. (n) => n.toLocaleString('vi-VN')) */
  format?: (n: number) => string;
}

const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4);

/**
 * Smoothly counts from previous value to `value`. On first paint counts up
 * from 0. Honors prefers-reduced-motion (snaps directly to final value).
 */
export default function CountUp({
  value,
  duration = 900,
  decimals = 0,
  prefix = '',
  suffix = '',
  className,
  format,
}: CountUpProps) {
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !Number.isFinite(value)) {
      fromRef.current = value;
      setDisplay(value);
      return;
    }

    const from = fromRef.current;
    const to = value;
    if (from === to) return;

    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = easeOutQuart(t);
      const current = from + (to - from) * eased;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  const out = format
    ? format(Number(display.toFixed(decimals)))
    : display.toFixed(decimals);

  return <span className={`count-up ${className ?? ''}`}>{prefix}{out}{suffix}</span>;
}
