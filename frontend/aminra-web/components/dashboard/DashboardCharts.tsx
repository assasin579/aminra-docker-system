"use client";

import type { ReactNode } from "react";

type ChartPoint = { label: string; value: number; color?: string };
const palette = ["#22C77A", "#E2AD32", "#CF5260", "#3974B8", "#7F8B99", "#8A6BB8"];

export function DashboardCard({ title, description, children, className = "" }: { title: string; description?: string; children: ReactNode; className?: string }) {
  return <section data-dashboard-card="true" className={`min-w-0 rounded-xl border border-[#e7e5de] bg-white p-5 shadow-[0_5px_18px_rgba(10,31,68,0.06)] ${className}`}>
    <div className="mb-4 border-b border-slate-100 pb-3"><h2 className="text-sm font-semibold tracking-[0.01em] text-[#0A1F44]">{title}</h2>{description && <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>}</div>{children}
  </section>;
}

/** Screenshot-inspired status ring with visible legend and a screen-reader table alternative. */
export function DonutChart({ title, data, centerLabel = "Tổng" }: { title: string; data: ChartPoint[]; centerLabel?: string }) {
  const safe = data.map((point) => ({ ...point, value: Number.isFinite(point.value) ? Math.max(0, point.value) : 0 }));
  const total = safe.reduce((sum, point) => sum + point.value, 0);
  const format = new Intl.NumberFormat("vi-VN");
  const size = 188, center = size / 2, radius = 65, stroke = 24;
  const circumference = 2 * Math.PI * radius;
  const drawable = safe.map((point, index) => {
    const length = total > 0 ? (point.value / total) * circumference : 0;
    const dash = Math.max(0, length - (point.value > 0 ? 2 : 0));
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

  return <div className="grid min-h-[196px] grid-cols-1 items-center gap-4 sm:grid-cols-[168px_minmax(0,1fr)] sm:gap-5" data-dashboard-chart="donut">
    <div className="relative mx-auto aspect-square w-40 sm:w-[168px]">
      <svg role="img" aria-label={`${title}: ${format.format(total)} total${accessibleSummary ? ` — ${accessibleSummary}` : ""}`} viewBox={`0 0 ${size} ${size}`} className="h-full w-full" focusable="false">
        <circle cx={center} cy={center} r={radius} fill="none" stroke="#edf1f4" strokeWidth={stroke} />
        {hasData && <g transform={`rotate(-90 ${center} ${center})`}>{drawable.map((segment, index) => segment.dash > 0 && <circle key={`${segment.label}-${index}`} cx={center} cy={center} r={radius} fill="none" stroke={segment.color} strokeWidth={stroke} strokeDasharray={`${segment.dash} ${circumference - segment.dash}`} strokeDashoffset={-segment.offset} />)}</g>}
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span data-testid="donut-total" className="text-2xl font-bold tabular-nums tracking-tight text-[#0A1F44]">{format.format(total)}</span>
        <span className="mt-0.5 text-[11px] font-medium text-slate-500">{centerLabel}</span>
      </div>
    </div>
    <div className="min-w-0">
      {hasData ? <ul className="grid gap-2" aria-label={`${title} legend`} data-dashboard-legend="donut">{drawable.map((segment, index) => <li key={`${segment.label}-${index}`} className="flex min-w-0 items-center justify-between gap-3 text-xs">
        <span className="flex min-w-0 items-center gap-2"><span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: segment.color }} /><span className="truncate text-slate-600">{segment.label}</span></span><span className="shrink-0 font-semibold tabular-nums text-slate-800">{format.format(segment.value)}</span>
      </li>)}</ul> : <p className="rounded-lg bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">Chưa có dữ liệu để phân bố.</p>}
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
      {safe.map((point, index) => { const y = index * rowHeight + 5, barWidth = (width - 190) * point.value / max, color = point.color || palette[index % palette.length]; return <g key={`${point.label}-${index}`}>
        <text x="0" y={y + 18} fill="#475569" fontSize="13">{point.label.length > 22 ? `${point.label.slice(0, 20)}…` : point.label}</text><rect x="190" y={y} width={width - 190} height="22" rx="11" fill="#EEF2F6"/><rect x="190" y={y} width={barWidth} height="22" rx="11" fill={color}/><text x={Math.min(width - 8, 198 + barWidth)} y={y + 16} fill={barWidth > 50 ? "#FFFFFF" : "#0F172A"} fontSize="12" fontWeight="600">{point.value}</text>
      </g>; })}
    </svg> : <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">Chưa có dữ liệu để hiển thị.</p>}
    <div className="overflow-x-auto sm:sr-only"><table className="w-full text-sm" aria-label={`${title} — bảng số liệu`}><thead><tr className="border-b text-left text-xs text-slate-500"><th className="py-2 pr-3 font-medium">Nhóm</th><th className="py-2 text-right font-medium">Số lượng</th></tr></thead><tbody>{safe.map((point, index) => <tr key={`${point.label}-${index}`} className="border-b last:border-0"><th scope="row" className="py-2 pr-3 text-left font-medium text-slate-700">{point.label}</th><td className="py-2 text-right tabular-nums text-slate-900">{point.value}</td></tr>)}</tbody></table></div>
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
    {data.length ? <svg role="img" aria-label={title} viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" preserveAspectRatio="none"><line x1="0" x2={width} y1={height - 28} y2={height - 28} stroke="#E2E8F0"/>{data.map((point, index) => { const barHeight = Math.max(0, point.issued) / max * 125, x = index * slot + slot * 0.2, barWidth = slot * 0.6; return <g key={point.month}>{point.issued > 0 && <text x={x + barWidth / 2} y={height - 36 - barHeight} textAnchor="middle" fill="#334155" fontSize="11">{point.issued}</text>}<rect x={x} y={height - 28 - barHeight} width={barWidth} height={barHeight} rx="5" fill={point.issued > 0 ? "#1D8A7A" : "#E8EDF2"}/><text x={x + barWidth / 2} y={height - 8} textAnchor="middle" fill="#64748B" fontSize="10">{point.month.slice(5)}</text></g>; })}</svg> : <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">Chưa có dữ liệu theo tháng.</p>}
    <table className="sr-only" aria-label={`${title} — bảng số liệu`}><thead><tr><th>Tháng</th><th>Số chứng chỉ</th></tr></thead><tbody>{data.map((point) => <tr key={point.month}><th>{point.month}</th><td>{point.issued}</td></tr>)}</tbody></table>
  </div>;
}
