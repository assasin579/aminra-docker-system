"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";
import CountUp from "@/components/CountUp";
import SpotlightCard from "@/components/SpotlightCard";
import { AccessibleBarChart, DashboardCard, DonutChart } from "@/components/dashboard/DashboardCharts";

/* ── Interfaces ─────────────────────────────────────────────── */

interface CBStats {
  portfolio_size: number;
  certs: {
    total: number;
    active: number;
    expiring_soon: number;
    inactive: number;
  };
  audits: { total: number; completed: number; avg_compliance: number };
  submissions: {
    pending: number;
    reviewing: number;
    approved: number;
    total: number;
    avg_hours: number | null;
  };
  auditor_workload: Array<{
    id: string;
    name: string;
    active_visits: number;
    active_submissions: number;
  }>;
  expiring_certs: Array<{
    cert_number: string;
    company_name: string;
    expiry_date: string;
    days_remaining: number;
  }>;
}

interface AuditorStats {
  pending: number;
  reviewing: number;
  approved: number;
  returned: number;
  total: number;
  overdue: number;
  avg_response_hours: number | null;
  recent: Array<{
    id: string;
    company_name: string;
    status: string;
    doc_count: number;
    submitted_at: string;
    deadline: string | null;
  }>;
}

/* ── Constants ──────────────────────────────────────────────── */

const STATUS_MAP: Record<string, { label: string; bg: string; color: string }> =
  {
    pending: { label: "Chờ duyệt", bg: "var(--cream-100)", color: "var(--ink-500)" },
    reviewing: { label: "Đang xét", bg: "var(--navy-100)", color: "var(--navy-600)" },
    approved: { label: "Đã duyệt", bg: "var(--navy-100)", color: "var(--navy-800)" },
    returned: { label: "Trả lại", bg: "var(--gold-100)", color: "var(--gold-700)" },
  };

/* ── Helpers ────────────────────────────────────────────────── */

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Chào buổi sáng";
  if (h < 18) return "Chào buổi chiều";
  return "Chào buổi tối";
}

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return "Hôm nay";
  if (d === 1) return "Hôm qua";
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
}

function scoreColor(v: number): string {
  if (v >= 75) return "var(--navy-700)";
  if (v >= 50) return "var(--gold-700)";
  return "var(--gold-700)";
}

function daysColor(d: number): { text: string; bg: string } {
  if (d <= 30) return { text: "var(--gold-700)", bg: "var(--gold-100)" };
  if (d <= 90) return { text: "var(--gold-700)", bg: "var(--gold-100)" };
  return { text: "var(--navy-900)", bg: "var(--navy-100)" };
}

/* ── SVG icon paths ─────────────────────────────────────────── */
const ICONS = {
  building:
    "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0H5m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  shield:
    "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  clock: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  clipboard:
    "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
  inbox:
    "M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4",
  chart:
    "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  chat: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
  users:
    "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
  upload:
    "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12",
  cert: "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",
  folder:
    "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z",
};

/* ── Pulse loader ───────────────────────────────────────────── */

function PulseLoader() {
  return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-[var(--navy-900)] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[var(--navy-900)] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[var(--navy-900)] animate-pulse-dot" />
      </div>
    </div>
  );
}

/* ── Shared SVG component ───────────────────────────────────── */

function Icon({
  d,
  color,
  size = 4,
}: {
  d: string;
  color: string;
  size?: number;
}) {
  return (
    <svg
      className={`w-${size} h-${size}`}
      style={{ color }}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        d={d}
      />
    </svg>
  );
}

/* ── Score dial ─────────────────────────────────────────────── */

function ScoreDial({ value }: { value: number }) {
  const clamp = Math.min(100, Math.max(0, value));
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (clamp / 100) * circumference;
  const color = scoreColor(clamp);

  return (
    <div className="relative w-20 h-20 mx-auto">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke="var(--cream-200)"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="animate-score-fill"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-lg font-bold animate-count" style={{ color }}>
          {clamp}%
        </span>
      </div>
    </div>
  );
}

/* ── Horizontal bar ─────────────────────────────────────────── */

function HBar({
  value,
  max,
  color,
  label,
}: {
  value: number;
  max: number;
  color: string;
  label: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-20 truncate" style={{ color: "var(--ink-500)" }}>
        {label}
      </span>
      <div
        className="flex-1 h-2 rounded-full overflow-hidden"
        style={{ background: "var(--cream-200)" }}
      >
        <div
          className="h-full rounded-full animate-progress"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="w-5 text-right font-medium" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════════════════════ */

export default function ProviderDashboard() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading, logout } = useUserAuth();

  const [cbStats, setCbStats] = useState<CBStats | null>(null);
  const [auditorStats, setAuditorStats] = useState<AuditorStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState("");

  /* Auth guard */
  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== "provider")) {
      router.replace("/provider/login");
    }
  }, [loading, isAuthenticated, user, router]);

  /* Fetch CB stats (owner) */
  const fetchCBStats = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/api/submissions/cb-stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Không tải được số liệu CB (${res.status}).`);
      setCbStats(await res.json());
    } catch (error) {
      setStatsError(error instanceof Error ? error.message : "Không thể tải số liệu CB.");
    }
  }, [token]);

  /* Fetch auditor stats (both roles — backward compat) */
  const fetchAuditorStats = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/api/submissions/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Không tải được hàng đợi hồ sơ (${res.status}).`);
      setAuditorStats(await res.json());
    } catch (error) {
      setStatsError(error instanceof Error ? error.message : "Không thể tải hàng đợi.");
    }
  }, [token]);

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    setLoadingStats(true);
    setStatsError("");
    const promises: Promise<void>[] = [fetchAuditorStats()];
    if (user.is_owner) promises.push(fetchCBStats());
    Promise.all(promises).finally(() => setLoadingStats(false));
  }, [isAuthenticated, user, fetchCBStats, fetchAuditorStats]);

  /* ── Loading state ─────────────────────────────────────────── */
  if (loading || !user) return <PulseLoader />;

  const isOwner = user.is_owner;
  const cb = cbStats;
  const au = auditorStats;
  const cbCertificateData = cb ? [
    { label: "Hoạt động", value: cb.certs.active, color: "var(--navy-600)" },
    { label: "Đình chỉ / thu hồi", value: cb.certs.inactive, color: "var(--gold-700)" },
    { label: "Khác / chưa phân loại", value: Math.max(0, cb.certs.total - cb.certs.active - cb.certs.inactive), color: "var(--ink-300)" },
  ] : [];
  const cbAuditData = cb ? [
    { label: "Hoàn thành", value: cb.audits.completed, color: "var(--navy-600)" },
    { label: "Chưa hoàn tất", value: Math.max(0, cb.audits.total - cb.audits.completed), color: "var(--gold-500)" },
  ] : [];
  const cbListedSubmissions = cb ? cb.submissions.pending + cb.submissions.reviewing + cb.submissions.approved : 0;
  const cbSubmissionData = cb ? [
    { label: "Chờ xử lý", value: cb.submissions.pending, color: "var(--gold-500)" },
    { label: "Đang đánh giá", value: cb.submissions.reviewing, color: "var(--navy-500)" },
    { label: "Đã duyệt", value: cb.submissions.approved, color: "var(--navy-600)" },
    { label: "Trạng thái khác", value: Math.max(0, cb.submissions.total - cbListedSubmissions), color: "var(--ink-300)" },
  ] : [];
  const auListedSubmissions = au ? au.pending + au.reviewing + au.approved + au.returned : 0;
  const auditorSubmissionData = au ? [
    { label: "Chờ duyệt", value: au.pending, color: "var(--gold-500)" },
    { label: "Đang xét", value: au.reviewing, color: "var(--navy-500)" },
    { label: "Đã duyệt", value: au.approved, color: "var(--navy-600)" },
    { label: "Trả lại", value: au.returned, color: "var(--gold-600)" },
    { label: "Trạng thái khác", value: Math.max(0, au.total - auListedSubmissions), color: "var(--ink-300)" },
  ] : [];

  /* ══════════════════════════════════════════════════════════════
     OWNER VIEW
     ══════════════════════════════════════════════════════════════ */
  if (isOwner) {
    return (
      <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
        {/* Header */}
        <div className="mb-6 animate-section">
          <p className="text-sm mb-1" style={{ color: "var(--ink-500)" }}>
            {greeting()},
          </p>
          <h1 className="text-2xl font-bold" style={{ color: "var(--navy-900)" }}>
            {user.company_name}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <p className="text-sm" style={{ color: "var(--ink-500)" }}>
              {user.email}
            </p>
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background:
                  user.status === "active"
                    ? "color-mix(in srgb, var(--navy-900) 8%, transparent)"
                    : "color-mix(in srgb, var(--gold-500) 10%, transparent)",
                color: user.status === "active" ? "var(--navy-900)" : "var(--gold-700)",
                border: `1px solid ${user.status === "active" ? "color-mix(in srgb, var(--navy-900) 20%, transparent)" : "color-mix(in srgb, var(--gold-500) 30%, transparent)"}`,
              }}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${user.status === "active" ? "bg-[var(--navy-900)]" : "bg-gold-500"}`}
              />
              {user.status === "active" ? "Quản trị CB" : "Đang chờ duyệt"}
            </span>
          </div>
        </div>

        {statsError && <div role="alert" className="mb-5 flex flex-col gap-3 rounded-xl border border-gold-600 bg-gold-100 p-4 text-sm text-navy-900 sm:flex-row sm:items-center sm:justify-between"><span>{statsError}</span><button type="button" onClick={() => { setStatsError(""); setLoadingStats(true); void Promise.all([fetchAuditorStats(), fetchCBStats()]).finally(() => setLoadingStats(false)); }} className="min-h-10 rounded-lg bg-navy-900 px-4 font-semibold text-cream-100">Thử tải lại</button></div>}

        {/* Pending notice */}
        {user.status === "pending" && (
          <div
            className="mb-6 p-5 rounded-xl animate-section"
            style={{
              background: "color-mix(in srgb, var(--gold-500) 8%, transparent)",
              border: "1px solid color-mix(in srgb, var(--gold-500) 20%, transparent)",
            }}
          >
            <div className="flex items-start gap-3">
              <Icon d={ICONS.clock} color="var(--gold-600)" size={5} />
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--gold-600)" }}>
                  Tài khoản đang chờ xét duyệt
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--ink-500)" }}>
                  Đội ngũ AMINRA đang xem xét hồ sơ của tổ chức bạn. Trong thời
                  gian chờ, bạn có thể khám phá tính năng AI.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Row 1 — 4 stat cards */}
        {cb && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-section">
            {(
              [
                {
                  label: "Doanh nghiệp",
                  value: cb.portfolio_size,
                  color: "var(--navy-900)",
                  bg: "var(--navy-100)",
                  icon: ICONS.building,
                },
                {
                  label: "Chứng nhận",
                  value: cb.certs.active,
                  color: "var(--navy-600)",
                  bg: "var(--navy-100)",
                  icon: ICONS.shield,
                },
                {
                  label: "Sắp hết hạn",
                  value: cb.certs.expiring_soon,
                  color: cb.certs.expiring_soon > 0 ? "var(--gold-700)" : "var(--gold-700)",
                  bg: cb.certs.expiring_soon > 0 ? "var(--gold-100)" : "var(--gold-100)",
                  icon: ICONS.clock,
                },
                {
                  label: "KĐ hoàn thành",
                  value: cb.audits.completed,
                  color: "var(--navy-700)",
                  bg: "var(--navy-100)",
                  icon: ICONS.clipboard,
                },
              ] as const
            ).map((c, i) => (
              <SpotlightCard
                key={c.label}
                className={`rounded-xl p-4 animate-list-item stagger-${i + 1}`}
                style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className="w-8 h-8 rounded-lg grid place-items-center"
                    style={{ background: c.bg }}
                  >
                    <Icon d={c.icon} color={c.color} />
                  </span>
                </div>
                <div className="text-2xl font-bold" style={{ color: c.color }}>
                  <CountUp value={Number(c.value)} />
                </div>
                <div
                  className="text-xs font-medium mt-0.5"
                  style={{ color: "var(--ink-500)" }}
                >
                  {c.label}
                </div>
              </SpotlightCard>
            ))}
          </div>
        )}

        {/* Row 2 — 3 metric cards */}
        {cb && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 animate-section">
            {/* Compliance score dial */}
            <div
              className="rounded-xl p-5 text-center"
              style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
            >
              <p
                className="text-xs font-medium mb-3"
                style={{ color: "var(--ink-300)" }}
              >
                Điểm tuân thủ TB
              </p>
              <ScoreDial value={cb.audits.avg_compliance} />
            </div>

            {/* Avg response time */}
            <div
              className="rounded-xl p-5 flex flex-col items-center justify-center"
              style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
            >
              <div
                className="w-10 h-10 rounded-full grid place-items-center mb-2"
                style={{ background: "var(--navy-100)" }}
              >
                <Icon d={ICONS.clock} color="var(--navy-600)" size={5} />
              </div>
              <p className="text-xs font-medium" style={{ color: "var(--ink-300)" }}>
                Thời gian phản hồi TB
              </p>
              <p
                className="text-2xl font-bold mt-1 animate-count"
                style={{ color: "var(--navy-900)" }}
              >
                {cb.submissions.avg_hours !== null
                  ? `${cb.submissions.avg_hours}h`
                  : "---"}
              </p>
            </div>

            {/* Pending queue */}
            <div
              className="rounded-xl p-5 flex flex-col items-center justify-center"
              style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
            >
              <div
                className="w-10 h-10 rounded-full grid place-items-center mb-2"
                style={{ background: "var(--gold-100)" }}
              >
                <Icon d={ICONS.inbox} color="var(--gold-700)" size={5} />
              </div>
              <p className="text-xs font-medium" style={{ color: "var(--ink-300)" }}>
                Hồ sơ chờ xử lý
              </p>
              <p
                className="text-2xl font-bold mt-1 animate-count"
                style={{
                  color:
                    cb.submissions.pending + cb.submissions.reviewing > 0
                      ? "var(--gold-700)"
                      : "var(--navy-900)",
                }}
              >
                {cb.submissions.pending + cb.submissions.reviewing}
              </p>
            </div>
          </div>
        )}

        {cb && <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <DashboardCard title="Chứng chỉ theo trạng thái" description="Phân bố trạng thái trong registry; mục chưa thuộc hai nhóm chính được tách riêng.">
            <DonutChart title="Chứng chỉ theo trạng thái" data={cbCertificateData} centerLabel="Chứng chỉ" />
          </DashboardCard>
          <DashboardCard title="Tiến độ kiểm định" description="Hoàn thành so với tổng audit visits hiện có.">
            <DonutChart title="Tiến độ kiểm định" data={cbAuditData} centerLabel="Audit visits" />
          </DashboardCard>
          <DashboardCard title="Hồ sơ theo trạng thái" description="Các nhóm còn lại được gộp để tổng biểu đồ khớp phạm vi hồ sơ API.">
            <DonutChart title="Hồ sơ Certification Body theo trạng thái" data={cbSubmissionData} centerLabel="Hồ sơ" />
          </DashboardCard>
        </div>}

        {/* Row 3 — Expiring certs + Auditor workload */}
        {cb && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6 animate-section">
            {/* Expiring certs */}
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid var(--cream-200)" }}
            >
              <div
                className="px-4 py-3 flex items-center justify-between"
                style={{
                  background: "var(--cream-50)",
                  borderBottom: "1px solid var(--cream-200)",
                }}
              >
                <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
                  Chứng nhận sắp hết hạn
                </h3>
                <Link
                  href="/certificates"
                  className="text-xs font-medium"
                  style={{ color: "var(--navy-900)" }}
                >
                  Xem tất cả &rarr;
                </Link>
              </div>
              {cb.expiring_certs.length === 0 ? (
                <div className="p-6 text-center">
                  <Icon d={ICONS.shield} color="var(--ink-300)" size={8} />
                  <p className="text-sm mt-2" style={{ color: "var(--ink-300)" }}>
                    Không có chứng nhận sắp hết hạn
                  </p>
                </div>
              ) : (
                <div className="divide-y" style={{ borderColor: "var(--cream-200)" }}>
                  {cb.expiring_certs.map((c, i) => {
                    const dc = daysColor(c.days_remaining);
                    return (
                      <div
                        key={c.cert_number}
                        className={`px-4 py-3 flex items-center justify-between animate-list-item stagger-${Math.min(i + 1, 12)}`}
                      >
                        <div className="min-w-0">
                          <p
                            className="text-sm font-medium truncate"
                            style={{ color: "var(--navy-900)" }}
                          >
                            {c.company_name}
                          </p>
                          <p
                            className="text-xs mt-0.5"
                            style={{ color: "var(--ink-300)" }}
                          >
                            {c.cert_number}
                          </p>
                        </div>
                        <span
                          className="px-2 py-0.5 rounded-full text-xs font-bold flex-shrink-0 ml-2"
                          style={{ background: dc.bg, color: dc.text }}
                        >
                          {c.days_remaining} ngày
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Auditor workload */}
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid var(--cream-200)" }}
            >
              <div
                className="px-4 py-3 flex items-center justify-between"
                style={{
                  background: "var(--cream-50)",
                  borderBottom: "1px solid var(--cream-200)",
                }}
              >
                <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
                  Tải công việc Auditor
                </h3>
                <Link
                  href="/auditors"
                  className="text-xs font-medium"
                  style={{ color: "var(--navy-900)" }}
                >
                  Quản lý &rarr;
                </Link>
              </div>
              {cb.auditor_workload.length === 0 ? (
                <div className="p-6 text-center">
                  <Icon d={ICONS.users} color="var(--ink-300)" size={8} />
                  <p className="text-sm mt-2" style={{ color: "var(--ink-300)" }}>
                    Chưa có auditor nào
                  </p>
                </div>
              ) : (
                <div className="p-4">
                  <AccessibleBarChart title="Tải công việc Auditor: kiểm định và hồ sơ đang xử lý" data={cb.auditor_workload.flatMap((auditor) => [
                    { label: `${auditor.name} · Kiểm định`, value: auditor.active_visits, color: "var(--navy-700)" },
                    { label: `${auditor.name} · Hồ sơ`, value: auditor.active_submissions, color: "var(--navy-600)" },
                  ])} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Row 4 — Quick actions */}
        <div className="animate-section">
          <h3 className="text-sm font-bold mb-3" style={{ color: "var(--navy-900)" }}>
            Thao tác nhanh
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {[
              {
                href: "/submissions",
                label: "Hồ sơ nhận",
                desc: "Xem & đánh giá hồ sơ",
                color: "var(--navy-900)",
                icon: ICONS.inbox,
              },
              {
                href: "/portfolio",
                label: "Portfolio",
                desc: "Quản lý doanh nghiệp",
                color: "var(--navy-600)",
                icon: ICONS.folder,
              },
              {
                href: "/certificates",
                label: "Chứng nhận",
                desc: "Quản lý chứng nhận",
                color: "var(--gold-700)",
                icon: ICONS.cert,
              },
              {
                href: "/auditors",
                label: "Quản lý Auditor",
                desc: "Thêm & quản lý auditor",
                color: "var(--navy-700)",
                icon: ICONS.users,
              },
              {
                href: "/chat",
                label: "Hỏi đáp AI",
                desc: "Tra cứu tiêu chuẩn Halal",
                color: "var(--ink-500)",
                icon: ICONS.chat,
              },
            ].map((a, i) => (
              <Link
                key={a.href}
                href={a.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
                style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
              >
                <div
                  className="w-9 h-9 rounded-lg grid place-items-center flex-shrink-0"
                  style={{
                    background: `${a.color}12`,
                    border: `1px solid ${a.color}25`,
                  }}
                >
                  <Icon d={a.icon} color={a.color} size={5} />
                </div>
                <div className="min-w-0">
                  <div
                    className="text-sm font-semibold truncate"
                    style={{ color: "var(--navy-900)" }}
                  >
                    {a.label}
                  </div>
                  <div
                    className="text-xs truncate"
                    style={{ color: "var(--ink-500)" }}
                  >
                    {a.desc}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Loading overlay when still fetching */}
        {loadingStats && !cb && (
          <div className="fixed inset-0 z-50 grid place-items-center bg-cream-50/60">
            <PulseLoader />
          </div>
        )}
      </div>
    );
  }

  /* ══════════════════════════════════════════════════════════════
     AUDITOR VIEW (!is_owner)
     ══════════════════════════════════════════════════════════════ */
  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* Header */}
      <div className="mb-6 animate-section">
        <p className="text-sm mb-1" style={{ color: "var(--ink-500)" }}>
          {greeting()},
        </p>
        <h1 className="text-2xl font-bold" style={{ color: "var(--navy-900)" }}>
          {user.company_name}
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <p className="text-sm" style={{ color: "var(--ink-500)" }}>
            {user.email}
          </p>
          <span
            className="px-2.5 py-1 rounded-full text-xs font-medium"
            style={{
              background: "var(--navy-100)",
              color: "var(--navy-600)",
              border: "1px solid var(--navy-100)",
            }}
          >
            Auditor
          </span>
        </div>
      </div>

      {statsError && <div role="alert" className="mb-5 flex flex-col gap-3 rounded-xl border border-gold-600 bg-gold-100 p-4 text-sm text-navy-900 sm:flex-row sm:items-center sm:justify-between"><span>{statsError}</span><button type="button" onClick={() => { setStatsError(""); setLoadingStats(true); void fetchAuditorStats().finally(() => setLoadingStats(false)); }} className="min-h-10 rounded-lg bg-navy-900 px-4 font-semibold text-cream-100">Thử tải lại</button></div>}

      {/* Auditor stat cards */}
      {au && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-section">
          {(
            [
              {
                label: "Chờ duyệt",
                value: au.pending,
                color: "var(--ink-500)",
                bg: "var(--cream-100)",
              },
              {
                label: "Đang xét",
                value: au.reviewing,
                color: "var(--navy-600)",
                bg: "var(--navy-100)",
              },
              {
                label: "Đã duyệt",
                value: au.approved,
                color: "var(--navy-800)",
                bg: "var(--navy-100)",
              },
              {
                label: "Trả lại",
                value: au.returned,
                color: "var(--gold-700)",
                bg: "var(--gold-100)",
              },
            ] as const
          ).map((st, i) => (
            <div
              key={st.label}
              className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
            >
              <div
                className="text-2xl font-bold animate-count"
                style={{ color: st.color }}
              >
                {st.value}
              </div>
              <div
                className="text-xs font-medium mt-0.5"
                style={{ color: "var(--ink-500)" }}
              >
                {st.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Overdue alert banner */}
      {au && au.overdue > 0 && (
        <Link
          href="/dashboard/provider/overdue"
          className="block rounded-xl p-4 mb-6 btn-lift animate-section"
          style={{
            background: "color-mix(in srgb, var(--gold-700) 6%, transparent)",
            border: "1px solid color-mix(in srgb, var(--gold-700) 25%, transparent)",
          }}
          data-testid="provider-overdue-banner"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p
                className="text-sm font-semibold"
                style={{ color: "var(--navy-900)" }}
              >
                ⚠ {au.overdue} hồ sơ đã quá deadline
              </p>
              <p
                className="text-xs mt-0.5"
                style={{ color: "var(--navy-900)" }}
              >
                Mở queue SLA để xem chi tiết và xử lý
              </p>
            </div>
            <span
              className="px-3 py-1.5 rounded-lg text-xs font-medium"
              style={{ background: "var(--navy-900)", color: "white" }}
            >
              Xem queue →
            </span>
          </div>
        </Link>
      )}

      {au && <div className="mb-6 grid gap-4 xl:grid-cols-[1fr_20rem]">
        <DashboardCard title="Hàng đợi được giao" description="Phân bố hồ sơ theo trạng thái; trạng thái ngoài các nhóm chính được gộp.">
          <DonutChart title="Hồ sơ auditor theo trạng thái" data={auditorSubmissionData} centerLabel="Hồ sơ" />
        </DashboardCard>
        <DashboardCard title="Ưu tiên hôm nay" description="Hồ sơ quá hạn cần xử lý trước.">
          <p className={`text-4xl font-bold tabular-nums ${au.overdue > 0 ? "text-gold-700" : "text-navy-700"}`}>{au.overdue}</p><p className="mt-2 text-sm text-ink-500">{au.overdue > 0 ? "Hồ sơ đã quá deadline" : "Không có hồ sơ quá hạn"}</p>
        </DashboardCard>
      </div>}

      {/* Metrics row */}
      {au && (
        <div className="grid grid-cols-2 gap-4 mb-6 animate-section">
          <div
            className="rounded-xl p-4"
            style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--ink-300)" }}>
              Tổng hồ sơ nhận
            </p>
            <p
              className="text-xl font-bold mt-1 animate-count"
              style={{ color: "var(--navy-900)" }}
            >
              {au.total}
            </p>
          </div>
          <div
            className="rounded-xl p-4"
            style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
          >
            <p className="text-xs font-medium" style={{ color: "var(--ink-300)" }}>
              Thời gian phản hồi TB
            </p>
            <p
              className="text-xl font-bold mt-1 animate-count"
              style={{ color: "var(--navy-900)" }}
            >
              {au.avg_response_hours !== null
                ? `${au.avg_response_hours}h`
                : "---"}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 flex-1 lg:min-h-0 grid-cols-1 lg:grid-cols-[1fr_20rem] animate-section">
        {/* Recent submissions */}
        <div className="flex flex-col lg:min-h-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
              Hồ sơ gần đây
            </h3>
            <Link
              href="/submissions"
              className="text-xs font-medium"
              style={{ color: "var(--navy-900)" }}
            >
              Xem tất cả &rarr;
            </Link>
          </div>
          <div
            className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: "1px solid var(--cream-200)" }}
          >
            {loadingStats ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex gap-3 items-center">
                    <div className="shimmer skeleton-text flex-1" />
                    <div className="shimmer skeleton-text w-16" />
                  </div>
                ))}
              </div>
            ) : !au?.recent.length ? (
              <div className="p-8 text-center">
                <svg
                  className="w-12 h-12 mx-auto mb-3 animate-empty-icon"
                  style={{ color: "var(--ink-300)" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1"
                    d={ICONS.inbox}
                  />
                </svg>
                <p className="text-sm font-medium" style={{ color: "var(--navy-900)" }}>
                  Chưa có hồ sơ nào
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--ink-300)" }}>
                  Doanh nghiệp sẽ gửi hồ sơ cho bạn khi sẵn sàng
                </p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: "var(--cream-200)" }}>
                {au.recent.map((r, i) => {
                  const st = STATUS_MAP[r.status] || STATUS_MAP.pending;
                  return (
                    <Link
                      key={r.id}
                      href="/submissions"
                      className={`flex items-center justify-between px-4 py-3 hover:bg-cream-100 transition-colors animate-list-item stagger-${Math.min(i + 1, 12)}`}
                    >
                      <div className="min-w-0">
                        <p
                          className="text-sm font-medium truncate"
                          style={{ color: "var(--navy-900)" }}
                        >
                          {r.company_name}
                        </p>
                        <p
                          className="text-xs mt-0.5"
                          style={{ color: "var(--ink-300)" }}
                        >
                          {r.doc_count} tài liệu &middot;{" "}
                          {timeAgo(r.submitted_at)}
                        </p>
                      </div>
                      <span
                        className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ml-2"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="space-y-3">
          <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
            Thao tác nhanh
          </h3>
          {[
            {
              href: "/submissions",
              label: "Hồ sơ nhận",
              desc: "Xem & đánh giá hồ sơ",
              color: "var(--navy-900)",
              icon: ICONS.inbox,
            },
            {
              href: "/chat",
              label: "Hỏi đáp AI",
              desc: "Tra cứu tiêu chuẩn Halal",
              color: "var(--ink-500)",
              icon: ICONS.chat,
            },
            {
              href: "/upload",
              label: "Đánh giá tài liệu",
              desc: "Upload & kiểm tra compliance",
              color: "var(--navy-500)",
              icon: ICONS.upload,
            },
          ].map((a, i) => (
            <Link
              key={a.href}
              href={a.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
            >
              <div
                className="w-9 h-9 rounded-lg grid place-items-center flex-shrink-0"
                style={{
                  background: `${a.color}12`,
                  border: `1px solid ${a.color}25`,
                }}
              >
                <Icon d={a.icon} color={a.color} size={5} />
              </div>
              <div>
                <div
                  className="text-sm font-semibold"
                  style={{ color: "var(--navy-900)" }}
                >
                  {a.label}
                </div>
                <div className="text-xs" style={{ color: "var(--ink-500)" }}>
                  {a.desc}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
