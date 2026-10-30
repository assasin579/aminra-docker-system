"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";
import CountUp from "@/components/CountUp";
import SpotlightCard from "@/components/SpotlightCard";
import { AMINRA_DASHBOARD_PALETTE, DonutChart, DashboardCard } from "@/components/dashboard/DashboardCharts";
import motion from "@/components/dashboard/DashboardMotion.module.css";
import BusinessReadinessProfiles from "@/components/dashboard/BusinessReadinessProfiles";

interface DocTypeProgress {
  doc_type: string;
  label: string;
  score: number | null;
  status: string | null;
  filename: string | null;
  uploaded_at: string | null;
}
interface RecentItem {
  filename: string;
  doc_type_label: string | null;
  score: number | null;
  status: string | null;
  uploaded_by: string | null;
  uploaded_at: string | null;
}
interface DashboardCertificate {
  cert_number: string;
  provider_name: string | null;
  status: string;
  days_remaining: number;
  expiry_date: string;
}
interface DashboardStats {
  total_documents: number;
  avg_score: number | null;
  member_count: number;
  doc_type_progress: DocTypeProgress[];
  recent_activity: RecentItem[];
}

const STATUS_STYLE = {
  cb_approved: { label: "Duyệt bởi CB", bg: AMINRA_DASHBOARD_PALETTE.navy100, color: AMINRA_DASHBOARD_PALETTE.navy800 },
  compliant: { label: "AI: phù hợp", bg: AMINRA_DASHBOARD_PALETTE.navy100, color: AMINRA_DASHBOARD_PALETTE.navy900 },
  needs_review: { label: "Cần sửa", bg: AMINRA_DASHBOARD_PALETTE.gold100, color: AMINRA_DASHBOARD_PALETTE.gold700 },
  non_compliant: { label: "Chưa đạt", bg: AMINRA_DASHBOARD_PALETTE.gold100, color: AMINRA_DASHBOARD_PALETTE.gold700 },
};

function scoreColor(s: number | null) {
  if (s === null) return AMINRA_DASHBOARD_PALETTE.ink300;
  if (s >= 75) return AMINRA_DASHBOARD_PALETTE.navy900;
  if (s >= 50) return AMINRA_DASHBOARD_PALETTE.gold600;
  return AMINRA_DASHBOARD_PALETTE.gold700;
}

function timeAgo(iso: string | null) {
  if (!iso) return "";
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return "Hôm nay";
  if (d === 1) return "Hôm qua";
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Chào buổi sáng";
  if (h < 18) return "Chào buổi chiều";
  return "Chào buổi tối";
}

export default function BusinessDashboard() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading, logout } = useUserAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [certs, setCerts] = useState<DashboardCertificate[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState("");

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== "business")) {
      router.replace("/business/login");
      return;
    }
    // TASK #19: tenant owner without industry_schema_id → onboarding
    if (
      !loading &&
      isAuthenticated &&
      user?.role === "business" &&
      user?.is_owner &&
      !user?.industry_schema_id
    ) {
      router.replace("/business/onboarding/industry-select");
    }
  }, [loading, isAuthenticated, user, router]);

  const fetchStats = useCallback(async () => {
    if (!token) return;
    setLoadingStats(true);
    setStatsError("");
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [statsRes, certsRes] = await Promise.all([
        fetch("/api/api/dashboard/stats", { headers }),
        fetch("/api/api/submissions/cert-timeline", { headers }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (!statsRes.ok) throw new Error(`Không tải được số liệu hồ sơ (${statsRes.status}).`);
      if (certsRes.ok) {
        const d = await certsRes.json();
        setCerts(d.certificates || []);
      } else {
        throw new Error(`Không tải được dòng thời gian chứng chỉ (${certsRes.status}).`);
      }
    } catch (error) {
      setStatsError(error instanceof Error ? error.message : "Không thể tải dashboard.");
    } finally {
      setLoadingStats(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) fetchStats();
  }, [isAuthenticated, fetchStats]);

  if (loading || !user) {
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-navy-900 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-navy-900 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-navy-900 animate-pulse-dot" />
        </div>
      </div>
    );
  }

  const s = stats;
  const documentStatusData = s?.doc_type_progress.reduce<Record<string, number>>((counts, document) => {
    const status = document.score === null
      ? (document.filename ? "Chưa được chấm" : "Chưa tải lên")
      : STATUS_STYLE[document.status as keyof typeof STATUS_STYLE]?.label || "Đang xử lý";
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {}) ?? {};
  const documentStatusChartData = Object.entries(documentStatusData).map(([label, value]) => ({
    label,
    value,
    color: ({
      "AI: phù hợp": AMINRA_DASHBOARD_PALETTE.navy900,
      "Duyệt bởi CB": AMINRA_DASHBOARD_PALETTE.navy700,
      "Cần sửa": AMINRA_DASHBOARD_PALETTE.gold500,
      "Chưa đạt": AMINRA_DASHBOARD_PALETTE.gold700,
      "Chưa tải lên": AMINRA_DASHBOARD_PALETTE.ink300,
      "Chưa được chấm": AMINRA_DASHBOARD_PALETTE.gold400,
      "Đang xử lý": AMINRA_DASHBOARD_PALETTE.navy500,
    } as Record<string, string>)[label],
  }));
  const scoreCounts = s?.doc_type_progress.reduce<Record<string, number>>((counts, document) => {
    const band = document.score === null
      ? (document.filename ? "Đã tải · chờ chấm" : "Chưa tải lên")
      : document.score >= 75 ? "75–100" : document.score >= 50 ? "50–74" : "0–49";
    counts[band] = (counts[band] || 0) + 1;
    return counts;
  }, { "75–100": 0, "50–74": 0, "0–49": 0, "Đã tải · chờ chấm": 0, "Chưa tải lên": 0 }) ?? {};
  const scoreBandData = [
    { label: "75–100", value: scoreCounts["75–100"], color: AMINRA_DASHBOARD_PALETTE.navy900 },
    { label: "50–74", value: scoreCounts["50–74"], color: AMINRA_DASHBOARD_PALETTE.gold500 },
    { label: "0–49", value: scoreCounts["0–49"], color: AMINRA_DASHBOARD_PALETTE.gold700 },
    { label: "Đã tải · chờ chấm", value: scoreCounts["Đã tải · chờ chấm"], color: AMINRA_DASHBOARD_PALETTE.navy500 },
    { label: "Chưa tải lên", value: scoreCounts["Chưa tải lên"], color: AMINRA_DASHBOARD_PALETTE.ink300 },
  ];
  const certificateStatusData = [
    { label: "Còn hiệu lực · >60 ngày", value: certs.filter((cert) => cert.status === "active" && cert.days_remaining > 60).length, color: AMINRA_DASHBOARD_PALETTE.navy900 },
    { label: "Sắp hết hạn · 0–60 ngày", value: certs.filter((cert) => cert.status === "active" && cert.days_remaining >= 0 && cert.days_remaining <= 60).length, color: AMINRA_DASHBOARD_PALETTE.gold500 },
    { label: "Quá ngày hết hạn", value: certs.filter((cert) => cert.status === "active" && cert.days_remaining < 0).length, color: AMINRA_DASHBOARD_PALETTE.gold700 },
    { label: "Không hoạt động / khác", value: certs.filter((cert) => cert.status !== "active").length, color: AMINRA_DASHBOARD_PALETTE.ink500 },
  ];

  return (
    <div className={`flex flex-col flex-1 lg:min-h-0 w-full bg-cream-100 text-navy-900 ${motion.page}`} data-page data-dashboard-motion-root="true" data-dashboard-experience="business-v2">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 animate-section">
        <div>
          <div className="mb-1.5 flex items-center gap-2">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-gold-700">{greeting()}</p>
            <span aria-hidden="true" className="h-1 w-1 rounded-full bg-cream-300" />
            <span className="text-[11px] font-medium text-ink-500">Tổng quan doanh nghiệp</span>
          </div>
          <h1 className="text-[26px] font-extrabold leading-tight tracking-tight text-navy-900 sm:text-[30px]">{user.company_name}</h1>
          <p className="mt-1 text-sm text-ink-500">{user.email}</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-gold-500 bg-gold-100 px-3 py-1.5 text-xs font-semibold text-navy-900">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-gold-500" /> Hồ sơ doanh nghiệp
        </span>
      </div>

      {statsError && <div data-dashboard-motion="alert" role="alert" className={`mb-5 flex flex-col gap-3 rounded-xl border border-gold-600 bg-gold-100 p-4 text-sm text-navy-900 sm:flex-row sm:items-center sm:justify-between ${motion.alert}`}><span>{statsError}</span><button type="button" onClick={() => void fetchStats()} className="min-h-10 rounded-lg bg-navy-900 px-4 font-semibold text-cream-100">Thử tải lại</button></div>}

      <BusinessReadinessProfiles
        token={token}
        key={JSON.stringify({ actor: user.id, organization: user.tenant_id, role: user.role, status: user.status, owner: user.is_owner, permissions: user.permissions ?? null, entitlement: user.industry_schema_id ?? null })}
        contextKey={JSON.stringify({ actor: user.id, organization: user.tenant_id, role: user.role, status: user.status, owner: user.is_owner, permissions: user.permissions ?? null, entitlement: user.industry_schema_id ?? null })}
      />


      {s && <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-dashboard-section="overview-charts">
        <DashboardCard title="Trạng thái tài liệu" description="Phân bố hiện tại theo loại tài liệu; không phải xu hướng theo thời gian.">
          <DonutChart title="Trạng thái tài liệu doanh nghiệp" data={documentStatusChartData} centerLabel="Loại tài liệu" />
        </DashboardCard>
        <DashboardCard title="Phân bố điểm tài liệu" description="Điểm trung bình trên tài liệu đã chấm; biểu đồ tách riêng trạng thái chưa tải/chờ chấm.">
          <div className="mb-2 flex items-center gap-2 rounded-xl bg-cream-100 px-3 py-2"><span className="h-2 w-2 rounded-full bg-gold-500"/><span className="text-xs text-ink-500">Điểm trung bình</span><strong className="ml-auto text-base font-extrabold tabular-nums text-navy-900">{s.avg_score == null ? "—" : `${Math.round(s.avg_score)}%`}</strong></div>
          <DonutChart title="Phân bố điểm theo loại tài liệu" data={scoreBandData} centerLabel="Loại tài liệu" />
        </DashboardCard>
        <DashboardCard title="Phân bố chứng chỉ" description="Theo trạng thái API và số ngày còn lại đến hạn; khoảng ngày không chồng lấn.">
          <DonutChart title="Tình trạng chứng chỉ" data={certificateStatusData} centerLabel="Chứng chỉ" />
        </DashboardCard>
      </div>}

      {/* KPI strip — color-coded, but values remain API-owned */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-3" data-dashboard-section="key-metrics">
        {(
          [
            { label: "Tài liệu", numeric: s?.total_documents, sub: "đã upload", color: "var(--navy-600)", tint: "var(--navy-100)", symbol: "▤" },
            { label: "Điểm TB", numeric: s?.avg_score ?? null, suffix: "%", sub: "trên tài liệu đã chấm", color: scoreColor(s?.avg_score ?? null), tint: "var(--gold-100)", symbol: "◉" },
            { label: "Thành viên", numeric: user.member_count ?? 0, suffix: "", sub: "đang hoạt động", color: "var(--navy-700)", tint: "var(--navy-100)", symbol: "◈" },
          ] as const
        ).map((st, i) => (
          <SpotlightCard key={st.label} data-dashboard-kpi={st.label}
            className={`relative min-h-[124px] overflow-hidden rounded-2xl p-4 shadow-sm transition duration-300 hover:-translate-y-1 hover:shadow-md sm:p-5 animate-list-item stagger-${i + 1}`}
            style={{ background: `linear-gradient(145deg, var(--cream-50) 15%, ${st.tint} 145%)`, border: "1px solid var(--cream-200)" }}>
            <span aria-hidden="true" className="pointer-events-none absolute -right-7 -top-8 h-24 w-24 rounded-full opacity-50 blur-xl" style={{ background: st.tint }} />
            <div className="relative flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[27px] font-extrabold leading-none tracking-tight tabular-nums sm:text-[30px]" style={{ color: st.color }}>
                  {st.numeric == null ? "—" : <CountUp value={Number(st.numeric)} suffix={("suffix" in st ? st.suffix : "") as string} />}
                </div>
                <div className="mt-3 text-sm font-bold text-navy-900">{st.label}</div>
                <div className="mt-0.5 text-xs text-ink-500">{st.sub}</div>
              </div>
              <span aria-hidden="true" className="grid h-10 w-10 shrink-0 place-items-center rounded-[14px] text-lg font-bold shadow-sm ring-1 ring-cream-100/80" style={{ color: st.color, background: st.tint }}>{st.symbol}</span>
            </div>
            <div aria-hidden="true" className="absolute bottom-0 left-4 right-4 h-[3px] rounded-full opacity-70" style={{ background: `linear-gradient(90deg, ${st.color}, transparent)` }} />
          </SpotlightCard>
        ))}
      </div>

      {/* Certificate Status */}
      {certs.length > 0 && (
        <div
          className="rounded-xl mb-6 animate-section"
          style={{ background: "var(--cream-50)", border: "1px solid var(--cream-200)" }}
        >
          <div
            className="px-5 py-3"
            style={{ borderBottom: "1px solid var(--cream-200)" }}
          >
            <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
              Chứng nhận Halal
            </h3>
          </div>
          <div className="divide-y" style={{ borderColor: "var(--cream-200)" }}>
            {certs.map((cert) => {
              return (
                <div
                  key={cert.cert_number}
                  className="px-5 py-3 flex items-center justify-between gap-3"
                >
                  <div>
                    <p className="text-sm font-semibold">{cert.cert_number}</p>
                    <p className="text-xs" style={{ color: "var(--ink-500)" }}>
                      {cert.provider_name} · hết hạn{" "}
                      {new Date(cert.expiry_date).toLocaleDateString("vi-VN")}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className="px-2.5 py-0.5 rounded-full text-xs font-semibold"
                      style={{
                        background:
                          cert.status !== "active"
                            ? "var(--gold-100)"
                            : cert.days_remaining > 90
                              ? "var(--navy-100)"
                              : cert.days_remaining > 30
                                ? "var(--gold-100)"
                                : "var(--gold-100)",
                        color:
                          cert.status !== "active"
                            ? "var(--gold-700)"
                            : cert.days_remaining > 90
                              ? "var(--navy-900)"
                              : cert.days_remaining > 30
                                ? "var(--gold-700)"
                                : "var(--gold-700)",
                      }}
                    >
                      {cert.status !== "active"
                        ? cert.status === "suspended"
                          ? "Tạm đình chỉ"
                          : "Đã thu hồi"
                        : `Còn ${cert.days_remaining} ngày`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid gap-6 flex-1 lg:min-h-0 grid-cols-1 lg:grid-cols-[1fr_22rem] animate-section">
        {/* Left: Document progress */}
        <div className="flex flex-col lg:min-h-0">
          <div
            className="grid items-center mb-3"
            style={{ gridTemplateColumns: "1fr auto" }}
          >
            <h3 className="text-sm font-bold" style={{ color: "var(--navy-900)" }}>
              Tiến trình tài liệu
            </h3>
            <Link
              href="/upload"
              className="text-xs font-medium"
              style={{ color: "var(--navy-900)" }}
            >
              Upload tài liệu →
            </Link>
          </div>
          <div
            className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: "1px solid var(--cream-200)" }}
          >
            {loadingStats ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex gap-3 items-center">
                    <div className="shimmer skeleton-text flex-1" />
                    <div className="shimmer skeleton-text w-16" />
                    <div className="shimmer skeleton-text w-12" />
                    <div className="shimmer skeleton-text w-16" />
                  </div>
                ))}
              </div>
            ) : (
              <>
                {/* Visual readiness per doc type */}
                {s?.doc_type_progress && (
                  <div className="mb-4 px-4 pt-4">
                    {s.doc_type_progress.map((dt, i) => {
                      const pct = dt.score || 0;
                      const missing = dt.score === null;
                      return (
                        <div
                          key={dt.doc_type}
                          className="flex items-center gap-3 py-1.5"
                        >
                          <span
                            className="text-xs w-36 truncate"
                            style={{ color: missing ? "var(--gold-700)" : "var(--ink-500)" }}
                          >
                            {missing ? "\u26A0\uFE0F " : ""}
                            {dt.label}
                          </span>
                          <div
                            className="flex-1 h-2 rounded-full overflow-hidden"
                            style={{ background: "var(--cream-200)" }}
                          >
                            <div
                              className="h-full rounded-full animate-progress"
                              style={{
                                width: `${pct}%`,
                                background:
                                  pct >= 75
                                    ? "var(--navy-900)"
                                    : pct >= 50
                                      ? "var(--gold-700)"
                                      : pct > 0
                                        ? "var(--gold-700)"
                                        : "var(--cream-200)",
                              }}
                            />
                          </div>
                          <span
                            className="text-xs w-10 text-right font-bold"
                            style={{
                              color:
                                pct >= 75
                                  ? "var(--navy-900)"
                                  : pct >= 50
                                    ? "var(--gold-700)"
                                    : "var(--gold-700)",
                            }}
                          >
                            {missing ? "\u2014" : `${pct}%`}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
                <table className="w-full text-sm">
                  <thead
                    style={{
                      background: "var(--cream-100)",
                      position: "sticky",
                      top: 0,
                    }}
                  >
                    <tr>
                      {["Loại tài liệu", "File", "Điểm", "Trạng thái"].map(
                        (h) => (
                          <th
                            key={h}
                            className="text-left px-4 py-2.5 text-xs font-medium"
                            style={{ color: "var(--ink-500)" }}
                          >
                            {h}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {(s?.doc_type_progress ?? []).map((dt, i) => {
                      const st =
                        STATUS_STYLE[dt.status as keyof typeof STATUS_STYLE];
                      const submitted = dt.score !== null;
                      return (
                        <tr
                          key={dt.doc_type}
                          className={`animate-row stagger-${Math.min(i + 1, 12)}`}
                          style={{
                            background: i % 2 === 0 ? "var(--cream-50)" : "var(--cream-50)",
                            borderTop: "1px solid var(--cream-200)",
                            opacity: submitted ? 1 : 0.5,
                          }}
                        >
                          <td className="px-4 py-3">
                            <span
                              className="text-xs font-medium"
                              style={{ color: "var(--navy-900)" }}
                            >
                              {dt.label}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {dt.filename ? (
                              <span
                                className="text-xs truncate block max-w-[140px]"
                                style={{ color: "var(--ink-500)" }}
                                title={dt.filename}
                              >
                                {dt.filename}
                              </span>
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "var(--ink-300)" }}
                              >
                                —
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className="text-xs font-bold"
                              style={{ color: scoreColor(dt.score) }}
                            >
                              {dt.score !== null ? `${dt.score}%` : "—"}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {st ? (
                              <span
                                className="px-2 py-0.5 rounded-full text-xs"
                                style={{ background: st.bg, color: st.color }}
                              >
                                {st.label}
                              </span>
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "var(--ink-300)" }}
                              >
                                Chưa upload
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>

        {/* Right: Recent activity + Quick actions */}
        <div className="flex flex-col gap-5">
          {/* Recent activity */}
          <div className="rounded-xl" style={{ border: "1px solid var(--cream-200)" }}>
            <div
              className="px-4 py-3"
              style={{
                borderBottom: "1px solid var(--cream-200)",
                background: "var(--cream-100)",
              }}
            >
              <h3 className="text-xs font-bold" style={{ color: "var(--navy-900)" }}>
                Hoạt động gần đây
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: "var(--cream-200)" }}>
              {(s?.recent_activity ?? []).length === 0 ? (
                <div
                  className="p-6 text-center text-xs"
                  style={{ color: "var(--ink-300)" }}
                >
                  Chưa có hoạt động
                </div>
              ) : (
                (s?.recent_activity ?? []).map((r, i) => (
                  <div
                    key={i}
                    className={`px-4 py-3 animate-list-item stagger-${Math.min(i + 1, 12)}`}
                    style={{ borderColor: "var(--cream-200)" }}
                  >
                    <p
                      className="text-xs font-medium truncate"
                      style={{ color: "var(--navy-900)" }}
                      title={r.filename}
                    >
                      {r.filename}
                    </p>
                    <div
                      className="grid grid-flow-col items-center gap-2 mt-1 justify-start text-xs"
                      style={{ color: "var(--ink-500)" }}
                    >
                      {r.score !== null && (
                        <span
                          className="font-bold"
                          style={{ color: scoreColor(r.score) }}
                        >
                          {r.score}%
                        </span>
                      )}
                      <span>{r.doc_type_label || "—"}</span>
                      <span>·</span>
                      <span>{timeAgo(r.uploaded_at)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold px-1" style={{ color: "var(--navy-900)" }}>
              Thao tác nhanh
            </h3>
            {[
              {
                href: "/upload",
                label: "Đánh giá tài liệu",
                desc: "Upload & kiểm tra Halal",
                color: "var(--navy-900)",
                icon: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12",
              },
              {
                href: "/",
                label: "Hỏi đáp AI",
                desc: "Tư vấn quy trình chứng nhận",
                color: "var(--navy-500)",
                icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
              },
              {
                href: "/documents",
                label: "Tài liệu",
                desc: "Xem & quản lý tài liệu",
                color: "var(--navy-600)",
                icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
              },
              ...(user.is_owner
                ? [
                    {
                      href: "/members",
                      label: "Thành viên",
                      desc: `${user.member_count ?? 0}/7 thành viên`,
                      color: "var(--navy-700)",
                      icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
                    },
                  ]
                : []),
            ].map((a, i) => (
              <Link
                key={a.href}
                href={a.href}
                className={`grid items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
                style={{
                  gridTemplateColumns: "2rem 1fr",
                  background: "var(--cream-100)",
                  border: "1px solid var(--cream-200)",
                }}
              >
                <div
                  className="w-8 h-8 rounded-lg grid place-items-center"
                  style={{
                    background: `${a.color}15`,
                    border: `1px solid ${a.color}30`,
                  }}
                >
                  <svg
                    className="w-4 h-4"
                    style={{ color: a.color }}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d={a.icon}
                    />
                  </svg>
                </div>
                <div>
                  <div
                    className="text-xs font-semibold"
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
    </div>
  );
}
