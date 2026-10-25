"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { readAdminToken } from "@/lib/adminAuth";
import { AccessibleBarChart, DashboardCard, MonthlyBarChart, completeMonthlySeries } from "@/components/dashboard/DashboardCharts";

type Analytics = {
  cert_buckets: { healthy: number; expiring_90d: number; expiring_60d: number; expiring_30d: number; expired: number; suspended: number; revoked: number; total: number };
  funnel: Record<string, number>;
  monthly_trend: { month: string; issued: number }[];
  top_actions: { action: string; count: number }[];
  heatmap: { dow: number; hour: number; count: number }[];
  generated_at: string;
};

const STATUS_LABELS: Record<string, string> = { pending: "Đang chờ", assigned: "Đã giao", reviewing: "Đang đánh giá", returned: "Bị trả lại", approved: "Đã duyệt", rejected: "Bị từ chối" };
const ACTION_LABELS: Record<string, string> = { "login.success": "Đăng nhập thành công", "submission.submit": "Gửi hồ sơ", "submission.approve": "Duyệt hồ sơ", "submission.reject": "Từ chối hồ sơ", "certificate.issue": "Cấp chứng chỉ" };

export default function AdminAnalyticsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { setToken(readAdminToken()); }, []);

  const load = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/auth/admin/analytics", { headers: { Authorization: `Bearer ${token}` } });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
      setData(body);
    } catch (err) { setError(err instanceof Error ? err.message : "Không thể tải dữ liệu phân tích."); }
    finally { setLoading(false); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  const buckets = data?.cert_buckets;
  const bucketCards = buckets ? [
    { label: "Khỏe mạnh · ≥90 ngày", value: buckets.healthy, tone: "text-emerald-700", surface: "bg-emerald-50" },
    { label: "Còn 60–90 ngày", value: buckets.expiring_90d, tone: "text-sky-700", surface: "bg-sky-50" },
    { label: "Còn 30–60 ngày", value: buckets.expiring_60d, tone: "text-amber-700", surface: "bg-amber-50" },
    { label: "Còn 0–30 ngày", value: buckets.expiring_30d, tone: "text-orange-700", surface: "bg-orange-50" },
    { label: "Đã hết hạn", value: buckets.expired, tone: "text-red-700", surface: "bg-red-50" },
    { label: "Đình chỉ", value: buckets.suspended, tone: "text-slate-700", surface: "bg-slate-100" },
    { label: "Thu hồi", value: buckets.revoked, tone: "text-slate-700", surface: "bg-slate-100" },
  ] : [];
  const statusData = data ? Object.entries(STATUS_LABELS).map(([key, label]) => ({ label, value: Math.max(0, data.funnel[key] ?? 0) })) : [];
  const monthData = data ? completeMonthlySeries(data.monthly_trend) : [];

  return <main className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8" data-page data-dashboard="admin-analytics">
    <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">AMINRA · OPERATIONS</p><h1 className="text-3xl font-bold tracking-tight text-slate-950">Tổng quan vận hành</h1><p className="mt-2 max-w-2xl text-sm text-slate-600">Tình trạng chứng chỉ, hồ sơ và hoạt động hệ thống — chỉ số được cập nhật từ dữ liệu vận hành.</p>{data && <p className="mt-2 text-xs text-slate-500">Cập nhật: {new Date(data.generated_at).toLocaleString("vi-VN")}</p>}</div>
      <Link href="/admin" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">← Quay lại Admin</Link>
    </header>

    {!token && !loading && <div role="alert" className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">Cần đăng nhập bằng tài khoản Admin. <Link href="/admin" className="font-semibold underline">Mở cổng đăng nhập Admin</Link></div>}
    {error && <div role="alert" className="mb-5 flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900 sm:flex-row sm:items-center sm:justify-between"><span>{error}</span><button type="button" onClick={() => void load()} className="min-h-10 rounded-lg bg-red-900 px-4 font-semibold text-white">Thử tải lại</button></div>}
    {loading && <div role="status" aria-live="polite" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div key={index} className="h-28 animate-pulse rounded-2xl bg-slate-100" />)}<span className="sr-only">Đang tải dữ liệu phân tích…</span></div>}
    {data && !loading && <div className="space-y-6">
      <section aria-labelledby="cert-status-title"><div className="mb-3 flex items-end justify-between gap-3"><div><h2 id="cert-status-title" className="text-lg font-bold text-slate-900">Sức khỏe chứng chỉ <span className="font-medium text-slate-500">({buckets?.total ?? 0} tổng)</span></h2><p className="mt-1 text-sm text-slate-500">Các khoảng ngày không chồng lấn, tính từ ngày hiện tại.</p></div></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">{bucketCards.map((card) => <article key={card.label} className={`rounded-2xl border border-slate-200 p-4 ${card.surface}`}><p className="min-h-10 text-xs font-medium leading-5 text-slate-600">{card.label}</p><p className={`mt-2 text-3xl font-bold tabular-nums ${card.tone}`}>{card.value}</p></article>)}</div></section>
      <div className="grid gap-6 xl:grid-cols-2"><DashboardCard title="Phân bố trạng thái hồ sơ" description="Số lượng hồ sơ hiện ở mỗi trạng thái; đây không phải funnel chuyển đổi."><AccessibleBarChart title="Phân bố trạng thái hồ sơ" data={statusData} /></DashboardCard><DashboardCard title="Hoạt động nổi bật · 7 ngày" description="Số sự kiện audit theo loại hành động.">{data.top_actions.length ? <ol className="space-y-3">{data.top_actions.map((action) => <li key={action.action} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-3 last:border-0"><span className="text-sm font-medium text-slate-700">{ACTION_LABELS[action.action] || action.action.replace(/[._-]+/g, " ")}</span><span className="rounded-lg bg-slate-100 px-3 py-1 text-sm font-bold tabular-nums text-slate-900">{action.count}</span></li>)}</ol> : <p className="rounded-xl bg-slate-50 p-5 text-center text-sm text-slate-500">Chưa có hoạt động trong khoảng thời gian này.</p>}</DashboardCard></div>
      <DashboardCard title="Chứng chỉ được cấp theo tháng" description="12 tháng gần nhất; tháng không có bản ghi được hiển thị là 0."><MonthlyBarChart title="Số chứng chỉ cấp theo tháng trong 12 tháng gần nhất" data={monthData} /></DashboardCard>
      <DashboardCard title="Nhịp hoạt động hệ thống" description="Sự kiện audit theo ngày trong tuần và giờ ghi nhận."><Heatmap cells={data.heatmap} /></DashboardCard>
    </div>}
  </main>;
}

const DAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];
function Heatmap({ cells }: { cells: Analytics["heatmap"] }) {
  const grid = new Map(cells.map((cell) => [`${cell.dow}-${cell.hour}`, Math.max(0, cell.count)]));
  const max = Math.max(1, ...cells.map((cell) => cell.count));
  return <div className="overflow-x-auto pb-1"><table className="min-w-[760px] w-full border-separate border-spacing-1 text-xs"><thead><tr><th className="w-24 text-left font-medium text-slate-500">Ngày · giờ</th>{Array.from({ length: 24 }, (_, hour) => <th key={hour} className="font-normal text-slate-500">{hour}</th>)}</tr></thead><tbody>{DAYS.map((day, dow) => <tr key={day}><th scope="row" className="pr-2 text-left font-medium text-slate-600">{day}</th>{Array.from({ length: 24 }, (_, hour) => { const value = grid.get(`${dow}-${hour}`) ?? 0; return <td key={hour} aria-label={`${day}, ${hour}:00 — ${value} sự kiện`} title={`${day}, ${hour}:00 — ${value} sự kiện`} className="h-7 min-w-5 rounded-sm" style={{ backgroundColor: value === 0 ? "#F1F5F9" : `rgba(29,138,122,${0.18 + (value / max) * 0.82})` }} />; })}</tr>)}</tbody></table><p className="mt-3 text-xs text-slate-500">Múi giờ theo thời điểm ghi nhận của hệ thống. Màu đậm hơn = nhiều sự kiện hơn.</p></div>;
}
