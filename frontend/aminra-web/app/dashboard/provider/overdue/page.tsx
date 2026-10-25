"use client";

/**
 * Provider — Overdue SLA queue (org-scoped).
 *
 * cb_admin (owner) sees all submissions of their CB org past deadline.
 * Auditor (non-owner) sees only submissions assigned to them.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";

type OverdueItem = {
  submission_id: string;
  company_name: string | null;
  status: string;
  submitted_at: string | null;
  deadline: string;
  provider_email: string | null;
  provider_name: string | null;
  days_overdue: number;
};

const STATUS_LABEL: Record<string, string> = {
  pending: "Đang chờ",
  reviewing: "Đang đánh giá",
  revision_required: "Cần sửa",
  assigned: "Đã giao auditor",
};

const urgencyColor = (days: number) =>
  days >= 14 ? "var(--gold-700)" : days >= 7 ? "var(--gold-600)" : "var(--gold-500)";

export default function ProviderOverduePage() {
  const router = useRouter();
  const { token, user, isAuthenticated, loading: authLoading } = useUserAuth();
  const [items, setItems] = useState<OverdueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !token) {
      router.replace("/provider/login");
      return;
    }
    if (user?.role !== "provider") {
      setError("Trang này chỉ dành cho Tổ chức Chứng nhận (CB).");
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch("/api/api/submissions/overdue", {
          headers: { Authorization: `Bearer ${token}` },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
        setItems(body.items ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Lỗi tải queue");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, user, router]);

  const scopeLabel = user?.is_owner ? "toàn tổ chức" : "phần được giao của bạn";

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <Link
            href="/dashboard/provider"
            className="text-xs"
            style={{ color: "var(--ink-500)" }}
          >
            ← Dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2" style={{ color: "var(--navy-900)" }}>
            Hồ sơ quá hạn
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-500)" }}>
            {loading
              ? "Đang tải..."
              : items.length > 0
                ? `${items.length} hồ sơ quá deadline (${scopeLabel})`
                : `Không có hồ sơ nào quá hạn (${scopeLabel})`}
          </p>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="bg-gold-100 border border-gold-600 rounded-lg p-4 text-sm mb-4"
          style={{ color: "var(--gold-700)" }}
        >
          {error}
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div
          className="bg-[var(--navy-100)] border border-[var(--navy-100)] rounded-2xl p-8 text-center"
          style={{ color: "var(--navy-900)" }}
        >
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-cream-50 grid place-items-center">
            <span className="text-xl">✓</span>
          </div>
          <p className="font-semibold">Đang đúng SLA</p>
          <p className="text-xs mt-1" style={{ color: "var(--navy-800)" }}>
            Không có hồ sơ {scopeLabel} bị quá deadline.
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div
          className="bg-cream-50 rounded-2xl overflow-x-auto"
          style={{ border: "1px solid var(--cream-200)" }}
        >
          <table className="w-full text-sm">
            <thead style={{ background: "var(--cream-50)" }}>
              <tr>
                <th
                  className="text-left px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Doanh nghiệp
                </th>
                <th
                  className="text-left px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Trạng thái
                </th>
                <th
                  className="text-left px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Submitted
                </th>
                <th
                  className="text-left px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Deadline
                </th>
                <th
                  className="text-right px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Quá hạn
                </th>
                <th
                  className="text-right px-4 py-3 font-medium"
                  style={{ color: "var(--ink-500)" }}
                >
                  Hành động
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr
                  key={it.submission_id}
                  className="border-t"
                  style={{ borderColor: "var(--cream-200)" }}
                  data-testid={`overdue-row-${it.submission_id}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium" style={{ color: "var(--navy-900)" }}>
                      {it.company_name || (
                        <span className="italic" style={{ color: "var(--ink-300)" }}>
                          Chưa rõ
                        </span>
                      )}
                    </div>
                    <div
                      className="font-mono text-[10px] mt-0.5"
                      style={{ color: "var(--ink-300)" }}
                    >
                      {it.submission_id.slice(0, 8)}…
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="px-2 py-0.5 rounded-full text-[11px] font-semibold"
                      style={{
                        background: "color-mix(in srgb, var(--navy-500) 12%, transparent)",
                        color: "var(--navy-500)",
                      }}
                    >
                      {STATUS_LABEL[it.status] || it.status}
                    </span>
                  </td>
                  <td
                    className="px-4 py-3 text-xs"
                    style={{ color: "var(--ink-500)" }}
                  >
                    {it.submitted_at
                      ? new Date(it.submitted_at).toLocaleDateString("vi-VN", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })
                      : "—"}
                  </td>
                  <td
                    className="px-4 py-3 text-xs"
                    style={{ color: "var(--ink-500)" }}
                  >
                    {new Date(it.deadline).toLocaleDateString("vi-VN", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                    })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span
                      className="font-mono font-semibold text-sm"
                      style={{ color: urgencyColor(it.days_overdue) }}
                    >
                      {it.days_overdue.toFixed(1)} ngày
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/submissions?focus=${it.submission_id}`}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium btn-lift inline-block"
                      style={{ background: "var(--cream-200)", color: "var(--navy-900)" }}
                    >
                      Mở hồ sơ
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
