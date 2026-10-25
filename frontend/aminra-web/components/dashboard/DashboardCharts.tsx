"use client";

import type { ReactNode } from "react";

type ChartPoint = { label: string; value: number; color?: string };
const palette = ["#174A7E", "#1D8A7A", "#E2A33A", "#D66A55", "#6E7FBD", "#4D9270"];

export function DashboardCard({ title, description, children, className = "" }: { title: string; description?: string; children: ReactNode; className?: string }) {
  return <section className={`min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_8px_30px_rgba(15,35,60,0.04)] ${className}`}>
    <div className="mb-4"><h2 className="text-base font-semibold tracking-tight text-slate-900">{title}</h2>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</div>{children}
  </section>;
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
