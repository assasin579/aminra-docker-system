"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { readAdminToken } from "@/lib/adminAuth";

type Analytics = {
  cert_buckets: {
    healthy: number;
    expiring_90d: number;
    expiring_60d: number;
    expiring_30d: number;
    expired: number;
    suspended: number;
    revoked: number;
    total: number;
  };
  funnel: Record<string, number>;
  monthly_trend: { month: string; issued: number }[];
  top_actions: { action: string; count: number }[];
  heatmap: { dow: number; hour: number; count: number }[];
  generated_at: string;
};

export default function AdminAnalyticsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setToken(readAdminToken());
  }, []);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch("/api/auth/admin/analytics", {
          headers: { Authorization: `Bearer ${token}` },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
        setData(body);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Lỗi không xác định");
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8" data-page>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
            Analytics dashboard
          </h1>
          {data && (
            <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
              Cập nhật: {new Date(data.generated_at).toLocaleString("vi-VN")}
            </p>
          )}
        </div>
        <Link
          href="/admin"
          className="text-sm font-medium"
          style={{ color: "#0A1F44" }}
        >
          ← Quay lại Admin
        </Link>
      </div>

      {!token && !loading && (
        <div
          className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm"
          style={{ color: "#7c2d12" }}
        >
          Cần đăng nhập admin.{" "}
          <Link href="/provider/login" className="underline font-medium">
            Đăng nhập
          </Link>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm mb-4"
          style={{ color: "#991b1b" }}
        >
          {error}
        </div>
      )}

      {loading && (
        <p className="text-sm" style={{ color: "#94A3B8" }}>
          Đang tải...
        </p>
      )}

      {data && (
        <>
          <CertBucketsSection buckets={data.cert_buckets} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <FunnelSection funnel={data.funnel} />
            <TopActionsSection actions={data.top_actions} />
          </div>
          <MonthlyTrendSection trend={data.monthly_trend} />
          <HeatmapSection cells={data.heatmap} />
        </>
      )}
    </div>
  );
}

// ── Cert buckets ───────────────────────────────────────────────────────────

function CertBucketsSection({
  buckets,
}: {
  buckets: Analytics["cert_buckets"];
}) {
  const cards = [
    {
      label: "Khoẻ mạnh",
      value: buckets.healthy,
      color: "#102A5C",
      urgent: false,
    },
    {
      label: "Hết hạn ≤90d",
      value: buckets.expiring_90d,
      color: "#0ea5e9",
      urgent: false,
    },
    {
      label: "Hết hạn ≤60d",
      value: buckets.expiring_60d,
      color: "#f59e0b",
      urgent: false,
    },
    {
      label: "Hết hạn ≤30d",
      value: buckets.expiring_30d,
      color: "#dc2626",
      urgent: true,
    },
    {
      label: "Đã hết hạn",
      value: buckets.expired,
      color: "#7c2d12",
      urgent: true,
    },
    {
      label: "Đình chỉ",
      value: buckets.suspended,
      color: "#6b7280",
      urgent: false,
    },
    {
      label: "Thu hồi",
      value: buckets.revoked,
      color: "#374151",
      urgent: false,
    },
  ];
  return (
    <section className="mb-6">
      <h2 className="text-lg font-bold mb-3" style={{ color: "#0A1F44" }}>
        Trạng thái chứng chỉ ({buckets.total})
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {cards.map((c) => (
          <div
            key={c.label}
            className="p-4 rounded-xl bg-white"
            style={{
              border: `1px solid ${c.urgent && c.value > 0 ? c.color : "#E2E8F0"}`,
              boxShadow:
                c.urgent && c.value > 0 ? `0 0 0 3px ${c.color}15` : "none",
            }}
          >
            <div
              className="text-xs font-medium mb-1"
              style={{ color: "#6B7280" }}
            >
              {c.label}
            </div>
            <div className="text-2xl font-bold" style={{ color: c.color }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Submission funnel ──────────────────────────────────────────────────────

const FUNNEL_LABELS: Record<string, string> = {
  pending: "Đang chờ",
  assigned: "Đã giao",
  reviewing: "Đang đánh giá",
  returned: "Bị trả lại",
  approved: "Đã duyệt",
  rejected: "Bị từ chối",
};

function FunnelSection({ funnel }: { funnel: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(funnel));
  return (
    <section
      className="bg-white rounded-2xl p-5"
      style={{ border: "1px solid #E2E8F0" }}
    >
      <h2 className="text-lg font-bold mb-3" style={{ color: "#0A1F44" }}>
        Funnel hồ sơ
      </h2>
      <div className="space-y-2">
        {Object.entries(FUNNEL_LABELS).map(([key, label]) => {
          const v = funnel[key] ?? 0;
          const pct = (v / max) * 100;
          return (
            <div key={key}>
              <div
                className="flex items-baseline justify-between text-xs mb-1"
                style={{ color: "#6B7280" }}
              >
                <span>{label}</span>
                <span className="font-mono">{v}</span>
              </div>
              <div
                className="h-2 rounded-full overflow-hidden"
                style={{ background: "#F1F5F9" }}
              >
                <div
                  className="h-full"
                  style={{ width: `${pct}%`, background: "#0A1F44" }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── Top actions ────────────────────────────────────────────────────────────

function TopActionsSection({
  actions,
}: {
  actions: { action: string; count: number }[];
}) {
  return (
    <section
      className="bg-white rounded-2xl p-5"
      style={{ border: "1px solid #E2E8F0" }}
    >
      <h2 className="text-lg font-bold mb-3" style={{ color: "#0A1F44" }}>
        Top hoạt động (7 ngày qua)
      </h2>
      {actions.length === 0 ? (
        <p className="text-sm" style={{ color: "#94A3B8" }}>
          Chưa có dữ liệu
        </p>
      ) : (
        <ul className="space-y-2">
          {actions.map((a) => (
            <li
              key={a.action}
              className="flex items-center justify-between text-sm"
            >
              <code
                className="px-2 py-0.5 rounded text-xs"
                style={{ background: "#FFFFFF", color: "#0A1F44" }}
              >
                {a.action}
              </code>
              <span className="font-mono" style={{ color: "#0A1F44" }}>
                {a.count}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Monthly trend ──────────────────────────────────────────────────────────

function MonthlyTrendSection({
  trend,
}: {
  trend: { month: string; issued: number }[];
}) {
  const max = Math.max(1, ...trend.map((t) => t.issued));
  return (
    <section
      className="bg-white rounded-2xl p-5 mb-6"
      style={{ border: "1px solid #E2E8F0" }}
    >
      <h2 className="text-lg font-bold mb-3" style={{ color: "#0A1F44" }}>
        Chứng chỉ cấp theo tháng (12 tháng gần nhất)
      </h2>
      {trend.length === 0 ? (
        <p className="text-sm" style={{ color: "#94A3B8" }}>
          Chưa có chứng chỉ nào được cấp
        </p>
      ) : (
        <div className="flex items-end gap-2 h-32">
          {trend.map((t) => (
            <div
              key={t.month}
              className="flex-1 flex flex-col items-center gap-1"
            >
              <div className="text-xs font-mono" style={{ color: "#0A1F44" }}>
                {t.issued}
              </div>
              <div
                className="w-full rounded-t"
                style={{
                  height: `${(t.issued / max) * 100}%`,
                  background: "#0A1F44",
                  minHeight: t.issued > 0 ? 4 : 0,
                }}
              />
              <div className="text-[10px]" style={{ color: "#94A3B8" }}>
                {t.month.slice(5)}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Heatmap ────────────────────────────────────────────────────────────────

const DOW_LABELS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

function HeatmapSection({
  cells,
}: {
  cells: { dow: number; hour: number; count: number }[];
}) {
  const max = Math.max(1, ...cells.map((c) => c.count));
  const grid: Record<string, number> = {};
  cells.forEach((c) => {
    grid[`${c.dow}-${c.hour}`] = c.count;
  });

  return (
    <section
      className="bg-white rounded-2xl p-5"
      style={{ border: "1px solid #E2E8F0" }}
    >
      <h2 className="text-lg font-bold mb-3" style={{ color: "#0A1F44" }}>
        Heatmap hoạt động (30 ngày gần nhất)
      </h2>
      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="w-8" />
              {Array.from({ length: 24 }, (_, h) => (
                <th
                  key={h}
                  className="w-6 font-normal pb-1"
                  style={{ color: "#94A3B8" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DOW_LABELS.map((dowLabel, dow) => (
              <tr key={dow}>
                <td className="pr-2 text-right" style={{ color: "#6B7280" }}>
                  {dowLabel}
                </td>
                {Array.from({ length: 24 }, (_, h) => {
                  const v = grid[`${dow}-${h}`] ?? 0;
                  const intensity = v / max;
                  return (
                    <td
                      key={h}
                      title={`${dowLabel} ${h}h: ${v} events`}
                      className="w-6 h-6"
                      style={{
                        background:
                          v === 0
                            ? "#FFFFFF"
                            : `rgba(10,31,68, ${0.15 + intensity * 0.85})`,
                        border: "1px solid #fff",
                      }}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
