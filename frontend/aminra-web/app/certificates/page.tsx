"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import ExpiryUrgency from "@/components/certificates/ExpiryUrgency";
import { openAuthed } from "@/lib/authedOpen";
import RevealOnScroll from "@/components/RevealOnScroll";

interface CertStats {
  active: number;
  expiring: number;
  suspended: number;
  revoked: number;
}

interface Certificate {
  id: string;
  cert_number: string;
  company_name: string;
  issue_date: string;
  expiry_date: string;
  days_remaining: number;
  status: "active" | "suspended" | "revoked" | "expired";
  revocation_reason?: string | null;
  revoked_at?: string | null;
  revoked_by?: string | null;
}

const STATUS_BADGE: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  active: { label: "Hoạt động", color: "#0A1F44", bg: "rgba(10,31,68,0.12)" },
  suspended: {
    label: "Đình chỉ",
    color: "#D97706",
    bg: "rgba(217,119,6,0.12)",
  },
  revoked: { label: "Thu hồi", color: "#DC2626", bg: "rgba(220,38,38,0.12)" },
  expired: { label: "Hết hạn", color: "#6B7280", bg: "rgba(107,114,128,0.12)" },
};

const TABS = [
  { key: "all", label: "Tất cả" },
  { key: "active", label: "Hoạt động" },
  { key: "expiring", label: "Sắp hết hạn" },
  { key: "suspended", label: "Đình chỉ" },
  { key: "revoked", label: "Thu hồi" },
];

function daysColor(days: number): string {
  if (days > 90) return "#0A1F44";
  if (days >= 30) return "#D97706";
  return "#DC2626";
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function CertificatesPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  const [stats, setStats] = useState<CertStats>({
    active: 0,
    expiring: 0,
    suspended: 0,
    revoked: 0,
  });
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [fetching, setFetching] = useState(false);
  const [tab, setTab] = useState("all");

  // Confirm dialog state
  const [confirmAction, setConfirmAction] = useState<{
    id: string;
    action: "suspended" | "revoked";
  } | null>(null);
  const [reason, setReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Auth guard — provider owner only
  useEffect(() => {
    if (
      !loading &&
      (!isAuthenticated || user?.role !== "provider" || !user?.is_owner)
    )
      router.replace(
        user?.role === "business" ? "/dashboard/business" : "/provider/login",
      );
  }, [loading, isAuthenticated, user, router]);

  // Fetch certificates
  const fetchData = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch("/api/api/submissions/certificates/registry", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setStats(
          d.stats || { active: 0, expiring: 0, suspended: 0, revoked: 0 },
        );
        setCertificates(d.certificates || []);
      }
    } finally {
      setFetching(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) fetchData();
  }, [isAuthenticated, fetchData]);

  // Status action
  const handleStatusChange = async () => {
    if (!confirmAction || !reason.trim()) return;
    setActionLoading(true);
    try {
      await fetch(
        `/api/api/submissions/certificates/${confirmAction.id}/status`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status: confirmAction.action, reason }),
        },
      );
      setConfirmAction(null);
      setReason("");
      fetchData();
    } finally {
      setActionLoading(false);
    }
  };

  // Filter
  const filtered = certificates.filter((c) => {
    if (tab === "all") return true;
    if (tab === "expiring")
      return c.status === "active" && c.days_remaining <= 90;
    return c.status === tab;
  });

  if (loading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div
            className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
            style={{ animationDelay: "0.15s" }}
          />
          <div
            className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
            style={{ animationDelay: "0.3s" }}
          />
        </div>
      </div>
    );

  const statCards = [
    {
      label: "Hoạt động",
      value: stats.active,
      color: "#0A1F44",
      bg: "rgba(10,31,68,0.12)",
    },
    {
      label: "Sắp hết hạn (<90 ngày)",
      value: stats.expiring,
      color: "#D97706",
      bg: "rgba(217,119,6,0.12)",
    },
    {
      label: "Đình chỉ",
      value: stats.suspended,
      color: "#DC2626",
      bg: "rgba(220,38,38,0.12)",
    },
    {
      label: "Thu hồi",
      value: stats.revoked,
      color: "#6B7280",
      bg: "rgba(107,114,128,0.12)",
    },
  ];

  return (
    <div
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden"
      data-page
    >
      {/* Header */}
      <div
        className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-xl grid place-items-center"
            style={{
              background: "rgba(10,31,68,0.12)",
              border: "1px solid rgba(10,31,68,0.25)",
            }}
          >
            <svg
              className="w-5 h-5"
              style={{ color: "#0A1F44" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
              Sổ đăng ký chứng nhận
            </h1>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              {certificates.length} chứng nhận · {user.company_name}
            </p>
          </div>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6 animate-section">
        {statCards.map((s, i) => (
          <div
            key={i}
            className="rounded-xl p-4"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <p
              className="text-xs font-medium mb-1"
              style={{ color: "#6B7280" }}
            >
              {s.label}
            </p>
            <p className="text-2xl font-bold" style={{ color: s.color }}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div
        className="grid grid-cols-5 gap-1 p-1 rounded-xl mb-6 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className="px-3 py-2 rounded-lg text-xs font-semibold transition-all text-center"
            style={{
              background: tab === t.key ? "#0A1F44" : "transparent",
              color: tab === t.key ? "#FFFFFF" : "#6B7280",
              boxShadow:
                tab === t.key ? "0 2px 8px rgba(10,31,68,0.25)" : "none",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Certificate list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="rounded-2xl h-24 animate-pulse"
                style={{ background: "#F5F1E8", opacity: 1 - i * 0.15 }}
              />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div
            className="rounded-2xl p-12 text-center animate-section"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <svg
              className="w-16 h-16 mx-auto mb-4 animate-empty-icon"
              style={{ color: "#E2E8F0" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
              Không có chứng nhận nào
            </p>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              Chưa có chứng nhận nào phù hợp với bộ lọc hiện tại
            </p>
          </div>
        ) : (
          filtered.map((cert, idx) => {
            const badge = STATUS_BADGE[cert.status] || STATUS_BADGE.expired;
            return (
              <RevealOnScroll
                key={cert.id}
                delay={Math.min(idx, 11) * 45}
                className="rounded-xl p-4 transition-colors lift-hover"
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              >
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  {/* Left info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p
                        className="text-sm font-semibold"
                        style={{ color: "#0A1F44" }}
                      >
                        {cert.company_name}
                      </p>
                      <span
                        className="px-2 py-0.5 rounded-lg text-xs font-medium"
                        style={{ background: badge.bg, color: badge.color }}
                      >
                        {badge.label}
                      </span>
                    </div>
                    <div
                      className="flex items-center gap-4 text-xs flex-wrap"
                      style={{ color: "#6B7280" }}
                    >
                      <span className="font-mono" style={{ color: "#94A3B8" }}>
                        #{cert.cert_number}
                      </span>
                      <span>Cấp: {formatDate(cert.issue_date)}</span>
                      <span>Hết hạn: {formatDate(cert.expiry_date)}</span>
                      {cert.status === "active" && cert.days_remaining > 90 && (
                        <span
                          className="font-semibold"
                          style={{ color: daysColor(cert.days_remaining) }}
                        >
                          {cert.days_remaining} ngày còn lại
                        </span>
                      )}
                      <ExpiryUrgency
                        daysRemaining={cert.days_remaining}
                        status={cert.status}
                      />
                    </div>
                    {cert.status === "revoked" && cert.revocation_reason && (
                      <div
                        className="mt-2 px-3 py-2 rounded-lg text-xs"
                        style={{
                          background: "rgba(220,38,38,0.06)",
                          border: "1px solid rgba(220,38,38,0.2)",
                          color: "#7f1d1d",
                        }}
                        data-revocation
                      >
                        <strong>Lý do thu hồi:</strong> {cert.revocation_reason}
                        {cert.revoked_at && (
                          <span
                            className="block mt-0.5 text-[11px]"
                            style={{ color: "#991b1b" }}
                          >
                            Thu hồi ngày {formatDate(cert.revoked_at)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Right actions */}
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openAuthed(
                          `/api/api/submissions/certificates/${cert.id}/pdf`,
                          token || "",
                          {
                            download: true,
                            filename: `${cert.cert_number}.pdf`,
                          },
                        );
                      }}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                      style={{
                        background: "rgba(10,31,68,0.1)",
                        color: "#0A1F44",
                        border: "1px solid rgba(10,31,68,0.2)",
                      }}
                    >
                      Tải PDF
                    </button>
                    {cert.status === "active" && (
                      <>
                        <button
                          onClick={() =>
                            setConfirmAction({
                              id: cert.id,
                              action: "suspended",
                            })
                          }
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                          style={{
                            background: "rgba(217,119,6,0.1)",
                            color: "#D97706",
                            border: "1px solid rgba(217,119,6,0.2)",
                          }}
                        >
                          Đình chỉ
                        </button>
                        <button
                          onClick={() =>
                            setConfirmAction({ id: cert.id, action: "revoked" })
                          }
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                          style={{
                            background: "rgba(220,38,38,0.1)",
                            color: "#DC2626",
                            border: "1px solid rgba(220,38,38,0.2)",
                          }}
                        >
                          Thu hồi
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </RevealOnScroll>
            );
          })
        )}
      </div>

      {/* Confirm dialog */}
      {confirmAction && (
        <div
          className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{
            background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(8px)",
          }}
        >
          <div
            className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
            }}
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                {confirmAction.action === "suspended"
                  ? "Đình chỉ chứng nhận"
                  : "Thu hồi chứng nhận"}
              </h3>
              <button
                onClick={() => {
                  setConfirmAction(null);
                  setReason("");
                }}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: "rgba(0,0,0,0.05)" }}
              >
                <span className="hover:text-gray-700">&#10005;</span>
              </button>
            </div>

            <p className="text-sm mb-4" style={{ color: "#6B7280" }}>
              {confirmAction.action === "suspended"
                ? "Chứng nhận sẽ bị đình chỉ tạm thời. Vui lòng nhập lý do."
                : "Chứng nhận sẽ bị thu hồi vĩnh viễn. Vui lòng nhập lý do."}
            </p>

            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Nhập lý do..."
              rows={3}
              className="w-full px-4 py-2.5 rounded-xl text-sm outline-none resize-none mb-4"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setConfirmAction(null);
                  setReason("");
                }}
                className="flex-1 py-2.5 rounded-xl font-semibold text-sm transition-all"
                style={{
                  background: "#F5F1E8",
                  color: "#6B7280",
                  border: "1px solid #E2E8F0",
                }}
              >
                Hủy
              </button>
              <button
                onClick={handleStatusChange}
                disabled={!reason.trim() || actionLoading}
                className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{
                  background:
                    !reason.trim() || actionLoading
                      ? "#E2E8F0"
                      : confirmAction.action === "suspended"
                        ? "#D97706"
                        : "#DC2626",
                  color: !reason.trim() || actionLoading ? "#6B7280" : "white",
                }}
              >
                {actionLoading
                  ? "Đang xử lý..."
                  : confirmAction.action === "suspended"
                    ? "Xác nhận đình chỉ"
                    : "Xác nhận thu hồi"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
