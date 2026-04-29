"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";
import CountUp from "@/components/CountUp";
import SpotlightCard from "@/components/SpotlightCard";

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
    pending: { label: "Chờ duyệt", bg: "#F3F4F6", color: "#6B7280" },
    reviewing: { label: "Đang xét", bg: "#DBEAFE", color: "#2563EB" },
    approved: { label: "Đã duyệt", bg: "#DCE3F0", color: "#102A5C" },
    returned: { label: "Trả lại", bg: "#FEF3C7", color: "#D97706" },
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
  if (v >= 80) return "#0A1F44";
  if (v >= 60) return "#D97706";
  return "#DC2626";
}

function daysColor(d: number): { text: string; bg: string } {
  if (d <= 30) return { text: "#DC2626", bg: "#FEF2F2" };
  if (d <= 90) return { text: "#D97706", bg: "#FFFBEB" };
  return { text: "#0A1F44", bg: "#DCE3F0" };
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
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
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
          stroke="#E2E8F0"
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
      <span className="w-20 truncate" style={{ color: "#6B7280" }}>
        {label}
      </span>
      <div
        className="flex-1 h-2 rounded-full overflow-hidden"
        style={{ background: "#E2E8F0" }}
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
      if (res.ok) setCbStats(await res.json());
    } catch {
      /* silent */
    }
  }, [token]);

  /* Fetch auditor stats (both roles — backward compat) */
  const fetchAuditorStats = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/api/submissions/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setAuditorStats(await res.json());
    } catch {
      /* silent */
    }
  }, [token]);

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    setLoadingStats(true);
    const promises: Promise<void>[] = [fetchAuditorStats()];
    if (user.is_owner) promises.push(fetchCBStats());
    Promise.all(promises).finally(() => setLoadingStats(false));
  }, [isAuthenticated, user, fetchCBStats, fetchAuditorStats]);

  /* ── Loading state ─────────────────────────────────────────── */
  if (loading || !user) return <PulseLoader />;

  const isOwner = user.is_owner;
  const cb = cbStats;
  const au = auditorStats;

  /* ══════════════════════════════════════════════════════════════
     OWNER VIEW
     ══════════════════════════════════════════════════════════════ */
  if (isOwner) {
    return (
      <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
        {/* Header */}
        <div className="mb-6 animate-section">
          <p className="text-sm mb-1" style={{ color: "#6B7280" }}>
            {greeting()},
          </p>
          <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
            {user.company_name}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <p className="text-sm" style={{ color: "#6B7280" }}>
              {user.email}
            </p>
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                background:
                  user.status === "active"
                    ? "rgba(10,31,68,0.08)"
                    : "rgba(245,158,11,0.1)",
                color: user.status === "active" ? "#0A1F44" : "#D97706",
                border: `1px solid ${user.status === "active" ? "rgba(10,31,68,0.2)" : "rgba(245,158,11,0.3)"}`,
              }}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${user.status === "active" ? "bg-[#0A1F44]" : "bg-yellow-400"}`}
              />
              {user.status === "active" ? "Quản trị CB" : "Đang chờ duyệt"}
            </span>
          </div>
        </div>

        {/* Pending notice */}
        {user.status === "pending" && (
          <div
            className="mb-6 p-5 rounded-xl animate-section"
            style={{
              background: "rgba(245,158,11,0.08)",
              border: "1px solid rgba(245,158,11,0.2)",
            }}
          >
            <div className="flex items-start gap-3">
              <Icon d={ICONS.clock} color="#F59E0B" size={5} />
              <div>
                <p className="text-sm font-medium" style={{ color: "#F59E0B" }}>
                  Tài khoản đang chờ xét duyệt
                </p>
                <p className="text-xs mt-1" style={{ color: "#6B7280" }}>
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
                  color: "#0A1F44",
                  bg: "#DCE3F0",
                  icon: ICONS.building,
                },
                {
                  label: "Chứng nhận",
                  value: cb.certs.active,
                  color: "#2563EB",
                  bg: "#DBEAFE",
                  icon: ICONS.shield,
                },
                {
                  label: "Sắp hết hạn",
                  value: cb.certs.expiring_soon,
                  color: cb.certs.expiring_soon > 0 ? "#DC2626" : "#D97706",
                  bg: cb.certs.expiring_soon > 0 ? "#FEF2F2" : "#FFFBEB",
                  icon: ICONS.clock,
                },
                {
                  label: "KĐ hoàn thành",
                  value: cb.audits.completed,
                  color: "#7C3AED",
                  bg: "#F5F3FF",
                  icon: ICONS.clipboard,
                },
              ] as const
            ).map((c, i) => (
              <SpotlightCard
                key={c.label}
                className={`rounded-xl p-4 animate-list-item stagger-${i + 1}`}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
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
                  style={{ color: "#6B7280" }}
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
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <p
                className="text-xs font-medium mb-3"
                style={{ color: "#94A3B8" }}
              >
                Điểm tuân thủ TB
              </p>
              <ScoreDial value={cb.audits.avg_compliance} />
            </div>

            {/* Avg response time */}
            <div
              className="rounded-xl p-5 flex flex-col items-center justify-center"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div
                className="w-10 h-10 rounded-full grid place-items-center mb-2"
                style={{ background: "#DBEAFE" }}
              >
                <Icon d={ICONS.clock} color="#2563EB" size={5} />
              </div>
              <p className="text-xs font-medium" style={{ color: "#94A3B8" }}>
                Thời gian phản hồi TB
              </p>
              <p
                className="text-2xl font-bold mt-1 animate-count"
                style={{ color: "#0A1F44" }}
              >
                {cb.submissions.avg_hours !== null
                  ? `${cb.submissions.avg_hours}h`
                  : "---"}
              </p>
            </div>

            {/* Pending queue */}
            <div
              className="rounded-xl p-5 flex flex-col items-center justify-center"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div
                className="w-10 h-10 rounded-full grid place-items-center mb-2"
                style={{ background: "#FEF3C7" }}
              >
                <Icon d={ICONS.inbox} color="#D97706" size={5} />
              </div>
              <p className="text-xs font-medium" style={{ color: "#94A3B8" }}>
                Hồ sơ chờ xử lý
              </p>
              <p
                className="text-2xl font-bold mt-1 animate-count"
                style={{
                  color:
                    cb.submissions.pending + cb.submissions.reviewing > 0
                      ? "#D97706"
                      : "#0A1F44",
                }}
              >
                {cb.submissions.pending + cb.submissions.reviewing}
              </p>
            </div>
          </div>
        )}

        {/* Row 3 — Expiring certs + Auditor workload */}
        {cb && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6 animate-section">
            {/* Expiring certs */}
            <div
              className="rounded-xl overflow-hidden"
              style={{ border: "1px solid #E2E8F0" }}
            >
              <div
                className="px-4 py-3 flex items-center justify-between"
                style={{
                  background: "#FAFBFC",
                  borderBottom: "1px solid #E2E8F0",
                }}
              >
                <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
                  Chứng nhận sắp hết hạn
                </h3>
                <Link
                  href="/certificates"
                  className="text-xs font-medium"
                  style={{ color: "#0A1F44" }}
                >
                  Xem tất cả &rarr;
                </Link>
              </div>
              {cb.expiring_certs.length === 0 ? (
                <div className="p-6 text-center">
                  <Icon d={ICONS.shield} color="#CBD5E1" size={8} />
                  <p className="text-sm mt-2" style={{ color: "#94A3B8" }}>
                    Không có chứng nhận sắp hết hạn
                  </p>
                </div>
              ) : (
                <div className="divide-y" style={{ borderColor: "#F0F0F0" }}>
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
                            style={{ color: "#0A1F44" }}
                          >
                            {c.company_name}
                          </p>
                          <p
                            className="text-xs mt-0.5"
                            style={{ color: "#94A3B8" }}
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
              style={{ border: "1px solid #E2E8F0" }}
            >
              <div
                className="px-4 py-3 flex items-center justify-between"
                style={{
                  background: "#FAFBFC",
                  borderBottom: "1px solid #E2E8F0",
                }}
              >
                <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
                  Tải công việc Auditor
                </h3>
                <Link
                  href="/auditors"
                  className="text-xs font-medium"
                  style={{ color: "#0A1F44" }}
                >
                  Quản lý &rarr;
                </Link>
              </div>
              {cb.auditor_workload.length === 0 ? (
                <div className="p-6 text-center">
                  <Icon d={ICONS.users} color="#CBD5E1" size={8} />
                  <p className="text-sm mt-2" style={{ color: "#94A3B8" }}>
                    Chưa có auditor nào
                  </p>
                </div>
              ) : (
                <div className="p-4 space-y-4">
                  {cb.auditor_workload.map((a, i) => {
                    const maxVal = Math.max(
                      ...cb.auditor_workload.map((w) =>
                        Math.max(w.active_visits, w.active_submissions),
                      ),
                      1,
                    );
                    return (
                      <div
                        key={a.id}
                        className={`animate-list-item stagger-${Math.min(i + 1, 12)}`}
                      >
                        <p
                          className="text-sm font-medium mb-1.5"
                          style={{ color: "#0A1F44" }}
                        >
                          {a.name}
                        </p>
                        <HBar
                          value={a.active_visits}
                          max={maxVal}
                          color="#2563EB"
                          label="Kiểm định"
                        />
                        <div className="mt-1">
                          <HBar
                            value={a.active_submissions}
                            max={maxVal}
                            color="#7C3AED"
                            label="Hồ sơ"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Row 4 — Quick actions */}
        <div className="animate-section">
          <h3 className="text-sm font-bold mb-3" style={{ color: "#0A1F44" }}>
            Thao tác nhanh
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {[
              {
                href: "/submissions",
                label: "Hồ sơ nhận",
                desc: "Xem & đánh giá hồ sơ",
                color: "#0A1F44",
                icon: ICONS.inbox,
              },
              {
                href: "/portfolio",
                label: "Portfolio",
                desc: "Quản lý doanh nghiệp",
                color: "#2563EB",
                icon: ICONS.folder,
              },
              {
                href: "/certificates",
                label: "Chứng nhận",
                desc: "Quản lý chứng nhận",
                color: "#D97706",
                icon: ICONS.cert,
              },
              {
                href: "/auditors",
                label: "Quản lý Auditor",
                desc: "Thêm & quản lý auditor",
                color: "#7C3AED",
                icon: ICONS.users,
              },
              {
                href: "/chat",
                label: "Hỏi đáp AI",
                desc: "Tra cứu tiêu chuẩn Halal",
                color: "#64748B",
                icon: ICONS.chat,
              },
            ].map((a, i) => (
              <Link
                key={a.href}
                href={a.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
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
                    style={{ color: "#0A1F44" }}
                  >
                    {a.label}
                  </div>
                  <div
                    className="text-xs truncate"
                    style={{ color: "#6B7280" }}
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
          <div className="fixed inset-0 z-50 grid place-items-center bg-white/60">
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
        <p className="text-sm mb-1" style={{ color: "#6B7280" }}>
          {greeting()},
        </p>
        <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
          {user.company_name}
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <p className="text-sm" style={{ color: "#6B7280" }}>
            {user.email}
          </p>
          <span
            className="px-2.5 py-1 rounded-full text-xs font-medium"
            style={{
              background: "#DBEAFE",
              color: "#2563EB",
              border: "1px solid #BFDBFE",
            }}
          >
            Auditor
          </span>
        </div>
      </div>

      {/* Auditor stat cards */}
      {au && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-section">
          {(
            [
              {
                label: "Chờ duyệt",
                value: au.pending,
                color: "#6B7280",
                bg: "#F3F4F6",
              },
              {
                label: "Đang xét",
                value: au.reviewing,
                color: "#2563EB",
                bg: "#DBEAFE",
              },
              {
                label: "Đã duyệt",
                value: au.approved,
                color: "#102A5C",
                bg: "#DCE3F0",
              },
              {
                label: "Trả lại",
                value: au.returned,
                color: "#D97706",
                bg: "#FEF3C7",
              },
            ] as const
          ).map((st, i) => (
            <div
              key={st.label}
              className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div
                className="text-2xl font-bold animate-count"
                style={{ color: st.color }}
              >
                {st.value}
              </div>
              <div
                className="text-xs font-medium mt-0.5"
                style={{ color: "#6B7280" }}
              >
                {st.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Metrics row */}
      {au && (
        <div className="grid grid-cols-2 gap-4 mb-6 animate-section">
          <div
            className="rounded-xl p-4"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <p className="text-xs font-medium" style={{ color: "#94A3B8" }}>
              Tổng hồ sơ nhận
            </p>
            <p
              className="text-xl font-bold mt-1 animate-count"
              style={{ color: "#0A1F44" }}
            >
              {au.total}
            </p>
          </div>
          <div
            className="rounded-xl p-4"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <p className="text-xs font-medium" style={{ color: "#94A3B8" }}>
              Thời gian phản hồi TB
            </p>
            <p
              className="text-xl font-bold mt-1 animate-count"
              style={{ color: "#0A1F44" }}
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
            <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
              Hồ sơ gần đây
            </h3>
            <Link
              href="/submissions"
              className="text-xs font-medium"
              style={{ color: "#0A1F44" }}
            >
              Xem tất cả &rarr;
            </Link>
          </div>
          <div
            className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: "1px solid #E2E8F0" }}
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
                  style={{ color: "#CBD5E1" }}
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
                <p className="text-sm font-medium" style={{ color: "#0A1F44" }}>
                  Chưa có hồ sơ nào
                </p>
                <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
                  Doanh nghiệp sẽ gửi hồ sơ cho bạn khi sẵn sàng
                </p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: "#F0F0F0" }}>
                {au.recent.map((r, i) => {
                  const st = STATUS_MAP[r.status] || STATUS_MAP.pending;
                  return (
                    <Link
                      key={r.id}
                      href="/submissions"
                      className={`flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors animate-list-item stagger-${Math.min(i + 1, 12)}`}
                    >
                      <div className="min-w-0">
                        <p
                          className="text-sm font-medium truncate"
                          style={{ color: "#0A1F44" }}
                        >
                          {r.company_name}
                        </p>
                        <p
                          className="text-xs mt-0.5"
                          style={{ color: "#94A3B8" }}
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
          <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
            Thao tác nhanh
          </h3>
          {[
            {
              href: "/submissions",
              label: "Hồ sơ nhận",
              desc: "Xem & đánh giá hồ sơ",
              color: "#0A1F44",
              icon: ICONS.inbox,
            },
            {
              href: "/chat",
              label: "Hỏi đáp AI",
              desc: "Tra cứu tiêu chuẩn Halal",
              color: "#64748B",
              icon: ICONS.chat,
            },
            {
              href: "/upload",
              label: "Đánh giá tài liệu",
              desc: "Upload & kiểm tra compliance",
              color: "#0EA5E9",
              icon: ICONS.upload,
            },
          ].map((a, i) => (
            <Link
              key={a.href}
              href={a.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
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
                  style={{ color: "#0A1F44" }}
                >
                  {a.label}
                </div>
                <div className="text-xs" style={{ color: "#6B7280" }}>
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
