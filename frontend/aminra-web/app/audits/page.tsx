"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import { parseApiError } from "@/lib/apiError";
import RevealOnScroll from "@/components/RevealOnScroll";
import Modal from "@/components/Modal";

interface AuditVisit {
  id: string;
  business_name: string;
  visit_type: "initial" | "renewal" | "surprise";
  status: "scheduled" | "in_progress" | "completed" | "report_submitted";
  scheduled_date: string | null;
  auditor_id: string | null;
  auditor_name: string | null;
  compliance_score: number | null;
  location: string | null;
  notes: string | null;
  created_at: string;
}

interface Auditor {
  id: string;
  email: string;
  display_name: string;
}

interface AuditTemplate {
  id: string;
  name: string;
}

const VISIT_TYPE_MAP: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  initial: { label: "Lần đầu", color: "#2563EB", bg: "rgba(37,99,235,0.12)" },
  renewal: {
    label: "Tái đánh giá",
    color: "#F59E0B",
    bg: "rgba(245,158,11,0.12)",
  },
  surprise: { label: "Đột xuất", color: "#DC2626", bg: "rgba(220,38,38,0.12)" },
};

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> =
  {
    scheduled: {
      label: "Đã lên lịch",
      color: "#6B7280",
      bg: "rgba(107,114,128,0.12)",
    },
    in_progress: {
      label: "Đang kiểm",
      color: "#2563EB",
      bg: "rgba(37,99,235,0.12)",
    },
    completed: {
      label: "Hoàn thành",
      color: "#102A5C",
      bg: "rgba(5,150,105,0.12)",
    },
    report_submitted: {
      label: "Đã báo cáo",
      color: "#7C3AED",
      bg: "rgba(124,58,237,0.12)",
    },
  };

function scoreColor(s: number | null) {
  if (s === null) return "#6B7280";
  if (s >= 75) return "#0A1F44";
  if (s >= 50) return "#F59E0B";
  return "#f87171";
}

export default function AuditsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  const [visits, setVisits] = useState<AuditVisit[]>([]);
  const [fetching, setFetching] = useState(false);

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [form, setForm] = useState({
    business_name: "",
    visit_type: "initial",
    scheduled_date: "",
    location: "",
    notes: "",
    template_id: "",
  });
  const [templates, setTemplates] = useState<AuditTemplate[]>([]);

  // Assign auditor
  const [assignId, setAssignId] = useState<string | null>(null);
  const [auditors, setAuditors] = useState<Auditor[]>([]);
  const [selectedAuditor, setSelectedAuditor] = useState("");
  const [assigning, setAssigning] = useState(false);

  // Auth guard
  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== "provider"))
      router.replace(
        user?.role === "business" ? "/dashboard/business" : "/provider/login",
      );
  }, [loading, isAuthenticated, user, router]);

  // Fetch visits
  const fetchVisits = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch("/api/api/audits/", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setVisits(d.visits || d || []);
      }
    } finally {
      setFetching(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) fetchVisits();
  }, [isAuthenticated, fetchVisits]);

  // Fetch templates (for create modal)
  const fetchTemplates = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/api/audits/templates", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setTemplates(d.templates || d || []);
      }
    } catch {
      /* ignore */
    }
  }, [token]);

  // Fetch auditors (for assign)
  const fetchAuditors = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/auth/provider/auditors", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setAuditors(d.auditors || []);
      }
    } catch {
      /* ignore */
    }
  }, [token]);

  // Create visit
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    setCreating(true);
    try {
      const payload: Record<string, string> = {
        business_name: form.business_name,
        visit_type: form.visit_type,
      };
      if (form.scheduled_date) payload.scheduled_date = form.scheduled_date;
      if (form.location) payload.location = form.location;
      if (form.notes) payload.notes = form.notes;
      if (form.template_id) payload.template_id = form.template_id;

      const res = await fetch("/api/api/audits/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "Tạo thất bại"));
      }
      setShowCreate(false);
      setForm({
        business_name: "",
        visit_type: "initial",
        scheduled_date: "",
        location: "",
        notes: "",
        template_id: "",
      });
      fetchVisits();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Lỗi");
    } finally {
      setCreating(false);
    }
  };

  // Assign auditor
  const handleAssign = async () => {
    if (!assignId || !selectedAuditor) return;
    setAssigning(true);
    try {
      await fetch(`/api/api/audits/${assignId}/assign`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ auditor_id: selectedAuditor }),
      });
      setAssignId(null);
      setSelectedAuditor("");
      fetchVisits();
    } finally {
      setAssigning(false);
    }
  };

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
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
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
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
                Kiểm định thực địa
              </h1>
              <p className="text-sm" style={{ color: "#6B7280" }}>
                {visits.length} lượt kiểm định · {user.company_name}
              </p>
            </div>
          </div>
          {user.is_owner && (
            <button
              onClick={() => {
                setShowCreate(true);
                fetchTemplates();
              }}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
              style={{
                background: "#0A1F44",
                boxShadow: "0 4px 12px rgba(10,31,68,0.3)",
              }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Tạo lượt kiểm định
            </button>
          )}
        </div>
      </div>

      {/* Visit list */}
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
        ) : visits.length === 0 ? (
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
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
            <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
              Chưa có lượt kiểm định nào
            </p>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              Tạo lượt kiểm định thực địa để đánh giá doanh nghiệp tại chỗ
            </p>
          </div>
        ) : (
          visits.map((v, idx) => {
            const vt = VISIT_TYPE_MAP[v.visit_type] || VISIT_TYPE_MAP.initial;
            const st = STATUS_MAP[v.status] || STATUS_MAP.scheduled;
            return (
              <RevealOnScroll
                key={v.id}
                delay={Math.min(idx, 11) * 45}
                className="rounded-xl p-4 transition-colors lift-hover"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                  cursor: "pointer",
                }}
              >
                <div
                  className="flex flex-col sm:flex-row sm:items-center gap-3"
                  onClick={() => router.push(`/audits/${v.id}`)}
                >
                  {/* Left: info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p
                        className="text-sm font-semibold"
                        style={{ color: "#0A1F44" }}
                      >
                        {v.business_name}
                      </p>
                      <span
                        className="px-2 py-0.5 rounded-lg text-xs font-medium"
                        style={{ background: vt.bg, color: vt.color }}
                      >
                        {vt.label}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded-lg text-xs font-medium"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </div>
                    <div
                      className="flex items-center gap-4 text-xs"
                      style={{ color: "#6B7280" }}
                    >
                      {v.scheduled_date && (
                        <span className="flex items-center gap-1">
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                            />
                          </svg>
                          {new Date(v.scheduled_date).toLocaleDateString(
                            "vi-VN",
                          )}
                        </span>
                      )}
                      {v.auditor_name && (
                        <span className="flex items-center gap-1">
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                            />
                          </svg>
                          {v.auditor_name}
                        </span>
                      )}
                      {v.compliance_score !== null && (
                        <span
                          className="font-semibold"
                          style={{ color: scoreColor(v.compliance_score) }}
                        >
                          {v.compliance_score}%
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Right: assign button (owner only) */}
                  {user.is_owner && !v.auditor_id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setAssignId(v.id);
                        fetchAuditors();
                      }}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ease-out hover:scale-105"
                      style={{
                        background: "rgba(14,165,233,0.1)",
                        color: "#0EA5E9",
                        border: "1px solid rgba(14,165,233,0.2)",
                      }}
                    >
                      Gán Auditor
                    </button>
                  )}
                </div>
              </RevealOnScroll>
            );
          })
        )}
      </div>

      {/* Create visit modal */}
      {showCreate && (
        <Modal>
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
                Tạo lượt kiểm định
              </h3>
              <button
                onClick={() => setShowCreate(false)}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: "rgba(0,0,0,0.05)" }}
              >
                <span className="hover:text-gray-700">✕</span>
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Tên doanh nghiệp *
                </label>
                <input
                  type="text"
                  required
                  value={form.business_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, business_name: e.target.value }))
                  }
                  placeholder="Nhập tên doanh nghiệp"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    color: "#0A1F44",
                  }}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Loại kiểm định *
                  </label>
                  <select
                    value={form.visit_type}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, visit_type: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  >
                    <option value="initial">Lần đầu</option>
                    <option value="renewal">Tái đánh giá</option>
                    <option value="surprise">Đột xuất</option>
                  </select>
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Ngày kiểm định
                  </label>
                  <input
                    type="date"
                    value={form.scheduled_date}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, scheduled_date: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  />
                </div>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Địa điểm
                </label>
                <input
                  value={form.location}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, location: e.target.value }))
                  }
                  placeholder="Địa chỉ kiểm định"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    color: "#0A1F44",
                  }}
                />
              </div>
              {templates.length > 0 && (
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Mẫu kiểm định
                  </label>
                  <select
                    value={form.template_id}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, template_id: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  >
                    <option value="">-- Chọn mẫu --</option>
                    {templates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Ghi chú
                </label>
                <textarea
                  value={form.notes}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  placeholder="Ghi chú thêm..."
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none resize-none"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    color: "#0A1F44",
                  }}
                />
              </div>
              {createError && (
                <p className="text-xs text-red-400">{createError}</p>
              )}
              <button
                type="submit"
                disabled={creating}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{
                  background: creating ? "#E2E8F0" : "#0A1F44",
                  color: creating ? "#6B7280" : "white",
                }}
              >
                {creating ? "Đang tạo..." : "Tạo lượt kiểm định"}
              </button>
            </form>
          </div>
        </Modal>
      )}

      {/* Assign auditor modal */}
      {assignId && (
        <Modal onClose={() => setAssignId(null)}>
          <div
            className="w-full max-w-sm rounded-2xl p-6 animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                Gán Auditor
              </h3>
              <button
                onClick={() => {
                  setAssignId(null);
                  setSelectedAuditor("");
                }}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: "rgba(0,0,0,0.05)" }}
              >
                <span className="hover:text-gray-700">✕</span>
              </button>
            </div>
            {auditors.length === 0 ? (
              <p
                className="text-sm text-center py-4"
                style={{ color: "#6B7280" }}
              >
                Chưa có auditor nào. Vui lòng tạo auditor trước.
              </p>
            ) : (
              <>
                <select
                  value={selectedAuditor}
                  onChange={(e) => setSelectedAuditor(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none mb-4"
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    color: "#0A1F44",
                  }}
                >
                  <option value="">-- Chọn auditor --</option>
                  {auditors.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.display_name} ({a.email})
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAssign}
                  disabled={!selectedAuditor || assigning}
                  className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                  style={{
                    background:
                      !selectedAuditor || assigning ? "#E2E8F0" : "#0A1F44",
                    color: !selectedAuditor || assigning ? "#6B7280" : "white",
                  }}
                >
                  {assigning ? "Đang gán..." : "Xác nhận gán"}
                </button>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
