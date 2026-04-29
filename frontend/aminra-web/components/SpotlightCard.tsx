'use client';

import type { CSSProperties, ReactNode } from 'react';
import { useCardSpotlight } from '@/lib/motion';

interface SpotlightCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  onClick?: () => void;
}

/**
 * Card with cursor-following gold spotlight glow.
 * Wraps `.spotlight-card` styling + the useCardSpotlight hook in one component.
 */
export default function SpotlightCard({ children, className = '', style, onClick }: SpotlightCardProps) {
  const ref = useCardSpotlight<HTMLDivElement>();
  return (
    <div ref={ref} onClick={onClick} className={`spotlight-card ${className}`} style={style}>
      {children}
    </div>
  );
}
