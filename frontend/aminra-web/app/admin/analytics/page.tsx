"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { readAdminToken } from "@/lib/adminAuth";
import { DashboardCard, DonutChart, MonthlyBarChart, completeMonthlySeries } from "@/components/dashboard/DashboardCharts";
import motion from "@/components/dashboard/DashboardMotion.module.css";

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
  const certificateData = buckets ? [
    { label: "Khỏe mạnh · ≥90 ngày", value: buckets.healthy, color: "var(--navy-600)" },
    { label: "Còn 60–90 ngày", value: buckets.expiring_90d, color: "var(--navy-500)" },
    { label: "Còn 30–60 ngày", value: buckets.expiring_60d, color: "var(--gold-500)" },
    { label: "Còn 0–30 ngày", value: buckets.expiring_30d, color: "var(--gold-600)" },
    { label: "Đã hết hạn", value: buckets.expired, color: "var(--gold-700)" },
    { label: "Đình chỉ", value: buckets.suspended, color: "var(--ink-500)" },
    { label: "Thu hồi", value: buckets.revoked, color: "var(--ink-700)" },
  ] : [];
  const statusData = data ? Object.entries(STATUS_LABELS).map(([key, label]) => ({
    label,
    value: Math.max(0, data.funnel[key] ?? 0),
    color: ({ pending: "var(--gold-500)", assigned: "var(--navy-500)", reviewing: "var(--navy-700)", returned: "var(--gold-600)", approved: "var(--navy-600)", rejected: "var(--gold-700)" } as Record<string, string>)[key],
  })) : [];
  const actionData = data ? data.top_actions.slice(0, 5).map((action, index) => ({
    label: ACTION_LABELS[action.action] || action.action.replace(/[._-]+/g, " "),
    value: Math.max(0, action.count),
    color: ["var(--navy-500)", "var(--navy-600)", "var(--gold-500)", "var(--navy-700)", "var(--gold-700)"][index],
  })) : [];
  const monthData = data ? completeMonthlySeries(data.monthly_trend) : [];

  return <main className={`mx-auto w-full max-w-[1440px] bg-cream-100 px-4 py-6 sm:px-6 lg:px-8 ${motion.page}`} data-page data-dashboard="admin-analytics" data-dashboard-motion-root="true">
    <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-gold-700">AMINRA · OPERATIONS</p><h1 className="text-3xl font-bold tracking-tight text-navy-900">Tổng quan vận hành</h1><p className="mt-2 max-w-2xl text-sm text-ink-700">Tình trạng chứng chỉ, hồ sơ và hoạt động hệ thống — chỉ số được cập nhật từ dữ liệu vận hành.</p>{data && <p className="mt-2 text-xs text-ink-500">Cập nhật: {new Date(data.generated_at).toLocaleString("vi-VN")}</p>}</div>
      <Link href="/admin" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-cream-200 px-4 text-sm font-semibold text-ink-700 hover:bg-cream-100">← Quay lại Admin</Link>
    </header>

    {!token && !loading && <div data-dashboard-motion="alert" role="alert" className={`mb-5 rounded-xl border border-gold-600 bg-gold-100 p-4 text-sm text-navy-900 ${motion.alert}`}>Cần đăng nhập bằng tài khoản Admin. <Link href="/admin" className="font-semibold underline">Mở cổng đăng nhập Admin</Link></div>}
    {error && <div data-dashboard-motion="alert" role="alert" className={`mb-5 flex flex-col gap-3 rounded-xl border border-gold-600 bg-gold-100 p-4 text-sm text-navy-900 sm:flex-row sm:items-center sm:justify-between ${motion.alert}`}><span>{error}</span><button type="button" onClick={() => void load()} className="min-h-10 rounded-lg bg-navy-900 px-4 font-semibold text-cream-100">Thử tải lại</button></div>}
    {loading && <div role="status" aria-live="polite" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, index) => <div data-dashboard-motion="skeleton" key={index} className={`h-28 rounded-2xl bg-cream-200 ${motion.skeleton}`} />)}<span className="sr-only">Đang tải dữ liệu phân tích…</span></div>}
    {data && !loading && <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <DashboardCard title="Tình trạng chứng chỉ" description="Phân bố theo hạn và trạng thái; các khoảng ngày không chồng lấn.">
          <DonutChart title="Tình trạng chứng chỉ" data={certificateData} />
        </DashboardCard>
        <DashboardCard title="Hồ sơ theo trạng thái" description="Số lượng hồ sơ hiện tại — không phải funnel chuyển đổi.">
          <DonutChart title="Hồ sơ theo trạng thái" data={statusData} />
        </DashboardCard>
        <DashboardCard title="Hành động phổ biến · 7 ngày" description="Tối đa 5 nhóm đứng đầu; tổng chỉ cộng các nhóm đang hiển thị.">
          <DonutChart title="Hành động phổ biến trong 7 ngày" data={actionData} centerLabel="Sự kiện" />
        </DashboardCard>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <DashboardCard title="Chứng chỉ được cấp theo tháng" description="12 tháng gần nhất; tháng không có bản ghi được hiển thị là 0."><MonthlyBarChart title="Số chứng chỉ cấp theo tháng trong 12 tháng gần nhất" data={monthData} /></DashboardCard>
        <DashboardCard title="Nhịp hoạt động hệ thống" description="Sự kiện audit theo ngày trong tuần và giờ ghi nhận."><Heatmap cells={data.heatmap} /></DashboardCard>
      </div>
    </div>}
  </main>;
}

const DAYS = ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"];
function Heatmap({ cells }: { cells: Analytics["heatmap"] }) {
  const grid = new Map(cells.map((cell) => [`${cell.dow}-${cell.hour}`, Math.max(0, cell.count)]));
  const max = Math.max(1, ...cells.map((cell) => cell.count));
  return <div className="overflow-x-auto pb-1"><table className="min-w-[760px] w-full border-separate border-spacing-1 text-xs"><thead><tr><th className="w-24 text-left font-medium text-ink-500">Ngày · giờ</th>{Array.from({ length: 24 }, (_, hour) => <th key={hour} className="font-normal text-ink-500">{hour}</th>)}</tr></thead><tbody>{DAYS.map((day, dow) => <tr key={day}><th scope="row" className="pr-2 text-left font-medium text-ink-700">{day}</th>{Array.from({ length: 24 }, (_, hour) => { const value = grid.get(`${dow}-${hour}`) ?? 0; return <td key={hour} aria-label={`${day}, ${hour}:00 — ${value} sự kiện`} title={`${day}, ${hour}:00 — ${value} sự kiện`} className={`h-7 min-w-5 rounded-sm ${motion.heatmapCell}`} data-dashboard-motion="heatmap-cell" style={{ backgroundColor: value === 0 ? "var(--cream-200)" : `color-mix(in srgb, var(--navy-700) ${Math.round((0.18 + (value / max) * 0.82) * 100)}%, var(--cream-50))` }} />; })}</tr>)}</tbody></table><p className="mt-3 text-xs text-ink-500">Múi giờ theo thời điểm ghi nhận của hệ thống. Màu đậm hơn = nhiều sự kiện hơn.</p></div>;
}
