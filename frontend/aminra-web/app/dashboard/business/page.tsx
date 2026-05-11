"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";
import CountUp from "@/components/CountUp";
import SpotlightCard from "@/components/SpotlightCard";

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
interface DashboardStats {
  readiness: number;
  compliant_count: number;
  total_types: number;
  submitted_count: number;
  total_documents: number;
  avg_score: number | null;
  member_count: number;
  doc_type_progress: DocTypeProgress[];
  recent_activity: RecentItem[];
}

const STATUS_STYLE = {
  cb_approved: {
    label: "Duyệt bởi CB",
    bg: "rgba(10,31,68,0.15)",
    color: "#0A1F44",
  },
  compliant: { label: "Đạt", bg: "rgba(10,31,68,0.1)", color: "#0A1F44" },
  needs_review: {
    label: "Cần sửa",
    bg: "rgba(245,158,11,0.15)",
    color: "#d97706",
  },
  non_compliant: {
    label: "Chưa đạt",
    bg: "rgba(239,68,68,0.15)",
    color: "#f87171",
  },
};

function scoreColor(s: number | null) {
  if (s === null) return "#94A3B8";
  if (s >= 75) return "#16A34A";
  if (s >= 50) return "#D97706";
  return "#DC2626";
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
  const [certs, setCerts] = useState<any[]>([]);
  const [loadingStats, setLoadingStats] = useState(true);

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
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [statsRes, certsRes] = await Promise.all([
        fetch("/api/api/dashboard/stats", { headers }),
        fetch("/api/api/submissions/cert-timeline", { headers }),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (certsRes.ok) {
        const d = await certsRes.json();
        setCerts(d.certificates || []);
      }
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
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
        </div>
      </div>
    );
  }

  const s = stats;

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
        <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
          {user.email}
        </p>
      </div>

      {/* Certification Readiness */}
      {s && (
        <div
          className="rounded-2xl p-6 mb-6 animate-section doc-card-hover"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          <div
            className="grid items-center gap-6"
            style={{ gridTemplateColumns: "auto 1fr" }}
          >
            {/* Circular progress */}
            <div className="relative w-24 h-24">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  stroke="#E2E8F0"
                  strokeWidth="8"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="42"
                  fill="none"
                  className="animate-score-fill"
                  stroke={
                    s.readiness >= 75
                      ? "#0A1F44"
                      : s.readiness >= 40
                        ? "#f59e0b"
                        : "#ef4444"
                  }
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${s.readiness * 2.64} 264`}
                />
              </svg>
              <div className="absolute inset-0 grid place-items-center">
                <div className="text-center">
                  <span
                    className="text-2xl font-bold"
                    style={{ color: "#0A1F44" }}
                  >
                    {s.readiness}%
                  </span>
                </div>
              </div>
            </div>
            <div>
              <h2
                className="text-lg font-bold mb-1"
                style={{ color: "#0A1F44" }}
              >
                Sẵn sàng chứng nhận
              </h2>
              <p className="text-sm" style={{ color: "#6B7280" }}>
                <strong style={{ color: "#0A1F44" }}>
                  {s.compliant_count}
                </strong>
                /{s.total_types} loại tài liệu đạt chuẩn
                {s.submitted_count > 0 && s.submitted_count < s.total_types && (
                  <span>
                    {" "}
                    · {s.total_types - s.submitted_count} chưa upload
                  </span>
                )}
              </p>
              {/* Mini progress bar */}
              <div
                className="mt-3 h-2 rounded-full overflow-hidden"
                style={{ background: "#E2E8F0" }}
              >
                <div
                  className="h-full rounded-full animate-progress"
                  style={{
                    width: `${s.readiness}%`,
                    background:
                      s.readiness >= 75
                        ? "#0A1F44"
                        : s.readiness >= 40
                          ? "#f59e0b"
                          : "#ef4444",
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-section">
        {(
          [
            {
              label: "Tài liệu",
              numeric: s?.total_documents,
              sub: "đã upload",
              color: "#0EA5E9",
            },
            {
              label: "Điểm TB",
              numeric: s?.avg_score ?? null,
              suffix: "%",
              sub: "compliance",
              color: scoreColor(s?.avg_score ?? null),
            },
            {
              label: "Đạt chuẩn",
              numeric: s?.compliant_count,
              suffix: ` / ${s?.total_types ?? 13}`,
              sub: "loại tài liệu đạt",
              color: "#0A1F44",
            },
            {
              label: "Thành viên",
              numeric: user.member_count ?? 0,
              suffix: "/7",
              sub: "đang hoạt động",
              color: "#818cf8",
            },
          ] as const
        ).map((st, i) => (
          <SpotlightCard
            key={st.label}
            className={`rounded-xl p-4 animate-list-item stagger-${i + 1}`}
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <div
              className="text-xl font-bold mb-0.5"
              style={{ color: st.color }}
            >
              {st.numeric == null ? (
                "—"
              ) : (
                <CountUp
                  value={Number(st.numeric)}
                  suffix={("suffix" in st ? st.suffix : "") as string}
                />
              )}
            </div>
            <div className="text-xs font-medium" style={{ color: "#0A1F44" }}>
              {st.label}
            </div>
            <div className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
              {st.sub}
            </div>
          </SpotlightCard>
        ))}
      </div>

      {/* Certificate Status */}
      {certs.length > 0 && (
        <div
          className="rounded-xl mb-6 animate-section"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          <div
            className="px-5 py-3"
            style={{ borderBottom: "1px solid #E2E8F0" }}
          >
            <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
              Chứng nhận Halal
            </h3>
          </div>
          <div className="divide-y" style={{ borderColor: "#F0F0F0" }}>
            {certs.map((cert) => {
              return (
                <div
                  key={cert.cert_number}
                  className="px-5 py-3 flex items-center justify-between gap-3"
                >
                  <div>
                    <p className="text-sm font-semibold">{cert.cert_number}</p>
                    <p className="text-xs" style={{ color: "#6B7280" }}>
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
                            ? "#FEF2F2"
                            : cert.days_remaining > 90
                              ? "#DCE3F0"
                              : cert.days_remaining > 30
                                ? "#FEF3C7"
                                : "#FEF2F2",
                        color:
                          cert.status !== "active"
                            ? "#DC2626"
                            : cert.days_remaining > 90
                              ? "#0A1F44"
                              : cert.days_remaining > 30
                                ? "#D97706"
                                : "#DC2626",
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
            <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
              Tiến trình tài liệu
            </h3>
            <Link
              href="/upload"
              className="text-xs font-medium"
              style={{ color: "#0A1F44" }}
            >
              Upload tài liệu →
            </Link>
          </div>
          <div
            className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: "1px solid #E2E8F0" }}
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
                            style={{ color: missing ? "#DC2626" : "#6B7280" }}
                          >
                            {missing ? "\u26A0\uFE0F " : ""}
                            {dt.label}
                          </span>
                          <div
                            className="flex-1 h-2 rounded-full overflow-hidden"
                            style={{ background: "#E2E8F0" }}
                          >
                            <div
                              className="h-full rounded-full animate-progress"
                              style={{
                                width: `${pct}%`,
                                background:
                                  pct >= 75
                                    ? "#0A1F44"
                                    : pct >= 50
                                      ? "#D97706"
                                      : pct > 0
                                        ? "#EF4444"
                                        : "#E2E8F0",
                              }}
                            />
                          </div>
                          <span
                            className="text-xs w-10 text-right font-bold"
                            style={{
                              color:
                                pct >= 75
                                  ? "#0A1F44"
                                  : pct >= 50
                                    ? "#D97706"
                                    : "#EF4444",
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
                      background: "#F5F1E8",
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
                            style={{ color: "#6B7280" }}
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
                            background: i % 2 === 0 ? "#FFFFFF" : "#FFFFFF",
                            borderTop: "1px solid #E2E8F0",
                            opacity: submitted ? 1 : 0.5,
                          }}
                        >
                          <td className="px-4 py-3">
                            <span
                              className="text-xs font-medium"
                              style={{ color: "#0A1F44" }}
                            >
                              {dt.label}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            {dt.filename ? (
                              <span
                                className="text-xs truncate block max-w-[140px]"
                                style={{ color: "#6B7280" }}
                                title={dt.filename}
                              >
                                {dt.filename}
                              </span>
                            ) : (
                              <span
                                className="text-xs"
                                style={{ color: "#94A3B8" }}
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
                                style={{ color: "#94A3B8" }}
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
          <div className="rounded-xl" style={{ border: "1px solid #E2E8F0" }}>
            <div
              className="px-4 py-3"
              style={{
                borderBottom: "1px solid #E2E8F0",
                background: "#F5F1E8",
              }}
            >
              <h3 className="text-xs font-bold" style={{ color: "#0A1F44" }}>
                Hoạt động gần đây
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: "#E2E8F0" }}>
              {(s?.recent_activity ?? []).length === 0 ? (
                <div
                  className="p-6 text-center text-xs"
                  style={{ color: "#94A3B8" }}
                >
                  Chưa có hoạt động
                </div>
              ) : (
                (s?.recent_activity ?? []).map((r, i) => (
                  <div
                    key={i}
                    className={`px-4 py-3 animate-list-item stagger-${Math.min(i + 1, 12)}`}
                    style={{ borderColor: "#E2E8F0" }}
                  >
                    <p
                      className="text-xs font-medium truncate"
                      style={{ color: "#0A1F44" }}
                      title={r.filename}
                    >
                      {r.filename}
                    </p>
                    <div
                      className="grid grid-flow-col items-center gap-2 mt-1 justify-start text-xs"
                      style={{ color: "#6B7280" }}
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
            <h3 className="text-xs font-bold px-1" style={{ color: "#0A1F44" }}>
              Thao tác nhanh
            </h3>
            {[
              {
                href: "/upload",
                label: "Đánh giá tài liệu",
                desc: "Upload & kiểm tra Halal",
                color: "#0A1F44",
                icon: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12",
              },
              {
                href: "/",
                label: "Hỏi đáp AI",
                desc: "Tư vấn quy trình chứng nhận",
                color: "#0EA5E9",
                icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
              },
              {
                href: "/documents",
                label: "Tài liệu",
                desc: "Xem & quản lý tài liệu",
                color: "#818cf8",
                icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
              },
              ...(user.is_owner
                ? [
                    {
                      href: "/members",
                      label: "Thành viên",
                      desc: `${user.member_count ?? 0}/7 thành viên`,
                      color: "#c084fc",
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
                  background: "#F5F1E8",
                  border: "1px solid #E2E8F0",
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
    </div>
  );
}
