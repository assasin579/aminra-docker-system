'use client';

/**
 * Visual urgency signal for cert expiry. Renders nothing for healthy certs
 * (>90 days), gradually escalates color/icon as days_remaining approaches 0.
 */

interface Props {
  daysRemaining: number;
  status: string;
}

export default function ExpiryUrgency({ daysRemaining, status }: Props) {
  // Only meaningful for active certs
  if (status !== 'active') return null;

  // Already expired
  if (daysRemaining <= 0) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold"
        style={{ background: '#7f1d1d', color: 'white' }}
        data-urgency="expired"
        title="Cert đã hết hạn"
      >
        ⏰ Đã hết hạn
      </span>
    );
  }
  // Critical: ≤30 days
  if (daysRemaining <= 30) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-bold"
        style={{ background: '#dc2626', color: 'white' }}
        data-urgency="critical"
        title={`Còn ${daysRemaining} ngày — gia hạn ngay`}
      >
        🚨 Còn {daysRemaining}d
      </span>
    );
  }
  // Warning: ≤60 days
  if (daysRemaining <= 60) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold"
        style={{ background: 'rgba(234,88,12,0.15)', color: '#9a3412', border: '1px solid rgba(234,88,12,0.3)' }}
        data-urgency="warning"
        title={`Còn ${daysRemaining} ngày — chuẩn bị gia hạn`}
      >
        ⚠ Còn {daysRemaining}d
      </span>
    );
  }
  // Caution: ≤90 days
  if (daysRemaining <= 90) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium"
        style={{ background: 'rgba(245,158,11,0.12)', color: '#92400e' }}
        data-urgency="caution"
        title={`Còn ${daysRemaining} ngày`}
      >
        ⏳ Còn {daysRemaining}d
      </span>
    );
  }
  // Healthy: no badge
  return null;
}
