"use client";

import type { ReactNode } from "react";

type ChartPoint = { label: string; value: number; color?: string };
export const AMINRA_DASHBOARD_PALETTE = {
  navy900: "var(--navy-900)",
  navy800: "var(--navy-800)",
  navy700: "var(--navy-700)",
  navy600: "var(--navy-600)",
  navy500: "var(--navy-500)",
  navy100: "var(--navy-100)",
  gold700: "var(--gold-700)",
  gold600: "var(--gold-600)",
  gold500: "var(--gold-500)",
  gold400: "var(--gold-400)",
  gold100: "var(--gold-100)",
  cream50: "var(--cream-50)",
  cream100: "var(--cream-100)",
  cream200: "var(--cream-200)",
  ink900: "var(--ink-900)",
  ink700: "var(--ink-700)",
  ink500: "var(--ink-500)",
  ink300: "var(--ink-300)",
} as const;
const palette = [AMINRA_DASHBOARD_PALETTE.navy900, AMINRA_DASHBOARD_PALETTE.navy700, AMINRA_DASHBOARD_PALETTE.navy500, AMINRA_DASHBOARD_PALETTE.gold500, AMINRA_DASHBOARD_PALETTE.gold400, AMINRA_DASHBOARD_PALETTE.ink300];

export function DashboardCard({ title, description, children, className = "" }: { title: string; description?: string; children: ReactNode; className?: string }) {
  return <section data-dashboard-card="true" className={`min-w-0 overflow-hidden rounded-2xl border border-cream-200 bg-gradient-to-b from-cream-50 via-cream-50 to-cream-100 p-5 shadow-sm transition-shadow duration-300 hover:shadow-md ${className}`}>
    <div className="mb-4 flex items-start gap-3 border-b border-cream-200 pb-3"><span aria-hidden="true" className="mt-0.5 h-8 w-1.5 shrink-0 rounded-full bg-gradient-to-b from-gold-700 via-gold-500 to-gold-400"/><div className="min-w-0"><h2 className="text-sm font-bold tracking-[0.01em] text-navy-900">{title}</h2>{description && <p className="mt-1 text-xs leading-5 text-ink-500">{description}</p>}</div></div>{children}
  </section>;
}

/** Large, vivid status ring with a centered total, visible legend and table alternative. */
export function DonutChart({ title, data, centerLabel = "Tổng" }: { title: string; data: ChartPoint[]; centerLabel?: string }) {
  const safe = data.map((point) => ({ ...point, value: Number.isFinite(point.value) ? Math.max(0, point.value) : 0 }));
  const total = safe.reduce((sum, point) => sum + point.value, 0);
  const format = new Intl.NumberFormat("vi-VN");
  const size = 220, center = size / 2, radius = 76, stroke = 28;
  const circumference = 2 * Math.PI * radius;
  const drawable = safe.map((point, index) => {
    const length = total > 0 ? (point.value / total) * circumference : 0;
    const dash = Math.max(0, length - (point.value > 0 ? 2.5 : 0));
    const item = { ...point, color: point.color || palette[index % palette.length], dash, offset: 0 };
    return item;
  });
  let offset = 0;
  for (const segment of drawable) {
    segment.offset = offset;
    offset += total > 0 ? (segment.value / total) * circumference : 0;
  }
  const hasData = total > 0;
  const accessibleSummary = safe.filter((point) => point.value > 0).map((point) => `${point.label}: ${format.format(point.value)}`).join(", ");

  return <div className="flex min-h-[278px] flex-col items-center gap-4" data-dashboard-chart="donut">
    <div className="relative aspect-square w-48 sm:w-[204px]">
      <div aria-hidden="true" className="absolute inset-[8%] rounded-full bg-gradient-to-br from-gold-100/60 via-cream-50 to-navy-100/70 blur-md" />
      <svg role="img" aria-label={`${title}: ${format.format(total)} total${accessibleSummary ? ` — ${accessibleSummary}` : ""}`} viewBox={`0 ${0} ${size} ${size}`} className="relative h-full w-full drop-shadow-sm" focusable="false">
        <circle cx={center} cy={center} r={radius} fill="none" stroke="var(--cream-200)" strokeWidth={stroke} />
        {hasData && <g transform={`rotate(-90 ${center} ${center})`}>{drawable.map((segment, index) => segment.dash > 0 && <circle data-dashboard-color-segment="true" key={`${segment.label}-${index}`} cx={center} cy={center} r={radius} fill="none" stroke={segment.color} strokeWidth={stroke} strokeLinecap="butt" strokeDasharray={`${segment.dash} ${circumference - segment.dash}`} strokeDashoffset={-segment.offset} />)}</g>}
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span data-testid="donut-total" className="text-3xl font-extrabold tabular-nums tracking-tight text-navy-900">{format.format(total)}</span>
        <span className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-500">{centerLabel}</span>
      </div>
    </div>
    <div className="w-full max-w-sm">
      {hasData ? <ul className="grid grid-cols-2 gap-x-3 gap-y-2.5" aria-label={`${title} legend`} data-dashboard-legend="donut">{drawable.map((segment, index) => <li key={`${segment.label}-${index}`} className="flex min-w-0 items-start gap-2 rounded-xl bg-cream-50 px-2.5 py-2 ring-1 ring-cream-200">
        <span aria-hidden="true" className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-cream-50 shadow-sm" style={{ backgroundColor: segment.color }} /><span className="min-w-0 flex-1"><span className="block truncate text-[11px] leading-4 text-ink-700">{segment.label}</span><span className="block text-sm font-bold tabular-nums text-navy-900">{format.format(segment.value)}</span></span>
      </li>)}</ul> : <p className="rounded-xl bg-cream-100 px-3 py-4 text-center text-xs text-ink-500">Chưa có dữ liệu để phân bố.</p>}
      <table className="sr-only" aria-label={`${title} — data table`}><thead><tr><th>Nhóm</th><th>Số lượng</th></tr></thead><tbody>{safe.map((point, index) => <tr key={`${point.label}-${index}`}><th>{point.label}</th><td>{format.format(point.value)}</td></tr>)}</tbody><tfoot><tr><th>Tổng</th><td>{format.format(total)}</td></tr></tfoot></table>
    </div>
  </div>;
}

/** Responsive SVG bars, with a semantic table alternative for assistive technology and small screens. */
export function AccessibleBarChart({ title, data }: { title: string; data: ChartPoint[] }) {
  const safe = data.map((point) => ({ ...point, value: Number.isFinite(point.value) ? Math.max(0, point.value) : 0 }));
  const max = Math.max(1, ...safe.map((point) => point.value));
  const width = 640, rowHeight = 42, height = Math.max(rowHeight, safe.length * rowHeight);
  return <div className="space-y-3" data-dashboard-chart="bar">
    {safe.length ? <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="hidden h-auto w-full sm:block" preserveAspectRatio="xMinYMin meet">
      {safe.map((point, index) => { const y = index * rowHeight + 5, color = point.color || palette[index % palette.length]; return <g key={`${point.label}-${index}`}>
        <text x="0" y={y + 18} fill="var(--ink-700)" fontSize="13">{point.label.length > 22 ? `${point.label.slice(0, 20)}…` : point.label}</text><rect x="190" y={y} width={width - 270} height="22" rx="11" fill="var(--cream-200)"/><rect x="190" y={y} width={(width - 270) * point.value / max} height="22" rx="11" fill={color}/><text x={width - 24} y={y + 16} textAnchor="end" fill="var(--navy-900)" fontSize="12" fontWeight="600">{point.value}</text>
      </g>; })}
    </svg> : <p className="rounded-xl bg-cream-100 px-4 py-6 text-center text-sm text-ink-500">Chưa có dữ liệu để hiển thị.</p>}
    <div className="overflow-x-auto sm:sr-only"><table className="w-full text-sm" aria-label={`${title} — bảng số liệu`}><thead><tr className="border-b border-cream-200 text-left text-xs text-ink-500"><th className="py-2 pr-3 font-medium">Nhóm</th><th className="py-2 text-right font-medium">Số lượng</th></tr></thead><tbody>{safe.map((point, index) => <tr key={`${point.label}-${index}`} className="border-b border-cream-200 last:border-0"><th scope="row" className="py-2 pr-3 text-left font-medium text-ink-700">{point.label}</th><td className="py-2 text-right tabular-nums text-ink-900">{point.value}</td></tr>)}</tbody></table></div>
  </div>;
}

export function completeMonthlySeries(points: { month: string; issued: number }[], now = new Date(), months = 12) {
  const count = Math.max(1, Math.min(24, Math.floor(months)));
  const current = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const start = new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() - count + 1, 1));
  const byMonth = new Map(points.map((point) => [point.month, Number.isFinite(point.issued) ? Math.max(0, point.issued) : 0]));
  return Array.from({ length: count }, (_, index) => { const date = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + index, 1)); const month = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`; return { month, issued: byMonth.get(month) ?? 0 }; });
}

export function MonthlyBarChart({ title, data }: { title: string; data: { month: string; issued: number }[] }) {
  const max = Math.max(1, ...data.map((point) => Math.max(0, point.issued))), width = 720, slot = width / Math.max(1, data.length), height = 190;
  return <div data-dashboard-chart="monthly" className="space-y-3">
    {data.length ? <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" preserveAspectRatio="none"><line x1="0" x2={width} y1={height - 28} y2={height - 28} stroke="var(--cream-200)"/>{data.map((point, index) => { const barHeight = Math.max(0, point.issued) / max * 125, x = index * slot + slot * 0.2, barWidth = slot * 0.6; return <g key={point.month}>{point.issued > 0 && <text x={x + barWidth / 2} y={height - 36 - barHeight} textAnchor="middle" fill="var(--navy-900)" fontSize="11">{point.issued}</text>}<rect x={x} y={height - 28 - barHeight} width={barWidth} height={barHeight} rx="5" fill={point.issued > 0 ? "var(--navy-700)" : "var(--cream-200)"}/><text x={x + barWidth / 2} y={height - 8} textAnchor="middle" fill="var(--ink-500)" fontSize="10">{point.month.slice(5)}</text></g>; })}</svg> : <p className="rounded-xl bg-cream-100 px-4 py-6 text-center text-sm text-ink-500">Chưa có dữ liệu theo tháng.</p>}
    <table className="sr-only" aria-label={`${title} — bảng số liệu`}><thead><tr><th>Tháng</th><th>Số chứng chỉ</th></tr></thead><tbody>{data.map((point) => <tr key={point.month}><th>{point.month}</th><td>{point.issued}</td></tr>)}</tbody></table>
  </div>;
}
