'use client';

import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from 'react';

interface RevealProps {
  children: ReactNode;
  /** Animation delay in ms (use small ints for natural stagger) */
  delay?: number;
  /** Threshold of element visible before triggering (0-1) */
  threshold?: number;
  /** Top margin for early-trigger before scroll reaches; px */
  rootMargin?: string;
  /** Element tag (default 'div') */
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}

/**
 * IntersectionObserver-driven reveal. Element starts hidden (`opacity:0,
 * translateY(18px)`) and animates to visible the first time it enters the
 * viewport. Honors prefers-reduced-motion (snaps visible immediately).
 */
export default function RevealOnScroll({
  children,
  delay = 0,
  threshold = 0.12,
  rootMargin = '0px 0px -8% 0px',
  as: Tag = 'div',
  className = '',
  style,
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      setVisible(true);
      return;
    }

    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.disconnect();
            break;
          }
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  const inlineStyle: CSSProperties = {
    transitionDelay: delay ? `${delay}ms` : undefined,
    ...style,
  };

  return (
    <Tag
      ref={ref as React.Ref<HTMLElement>}
      className={`reveal ${visible ? 'is-visible' : ''} ${className}`}
      style={inlineStyle}
    >
      {children}
    </Tag>
  );
}
