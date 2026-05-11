"use client";

/**
 * Create new dossier — title + standard chooser (filtered by user industry).
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";

interface StandardOption {
  id: string;
  code: string;
  name_vi: string;
  organization: string | null;
  scheme_version: string | null;
  is_default?: boolean;
  doc_types: Array<{ doc_type: string; required: boolean; display_order: number }>;
}

export default function CreateDossierPage() {
  const router = useRouter();
  const { token, user, isAuthenticated, loading: authLoading } = useUserAuth();
  const [standards, setStandards] = useState<StandardOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedStandardId, setSelectedStandardId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !token) {
      router.replace("/business/login");
      return;
    }
    if (user?.role === "business" && user.is_owner && !user.industry_schema_id) {
      router.replace("/business/onboarding/industry-select");
      return;
    }
    if (!user?.industry_schema_code) {
      setError("Cần chọn ngành nghề trước khi tạo hồ sơ");
      setLoading(false);
      return;
    }

    (async () => {
      try {
        const res = await fetch(
          `/api/standard-types/by-industry/${user.industry_schema_code}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: StandardOption[] = await res.json();
        setStandards(data);
        // Auto-pre-select default if exists
        const def = data.find((s) => s.is_default);
        if (def) setSelectedStandardId(def.id);
        else if (data.length === 1) setSelectedStandardId(data[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không tải được tiêu chuẩn");
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, isAuthenticated, token, user, router]);

  const handleSubmit = async () => {
    if (!selectedStandardId || !title.trim() || !token) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/dossiers", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: title.trim(),
          standard_type_id: selectedStandardId,
          notes: notes.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const created = await res.json();
      router.replace(`/dossiers/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tạo hồ sơ thất bại");
      setSubmitting(false);
    }
  };

  if (loading || authLoading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" style={{ color: "#6B7280" }}>Đang tải...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "#FFFFFF" }}>
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-6">
          <Link href="/dossiers" className="text-xs" style={{ color: "#6B7280" }}>
            ← Quay lại danh sách
          </Link>
          <h1 className="text-xl font-bold mt-2" style={{ color: "#0A1F44" }}>
            Tạo hồ sơ mới
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            Đặt tên cho hồ sơ và chọn tiêu chuẩn áp dụng. Hệ thống sẽ liệt kê
            các loại tài liệu cần chuẩn bị theo tiêu chuẩn đã chọn.
          </p>
        </div>

        {error && (
          <div
            className="rounded-lg px-4 py-3 text-xs mb-4"
            style={{
              background: "rgba(239,68,68,0.1)",
              color: "#DC2626",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            {error}
          </div>
        )}

        <div className="space-y-5">
          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Tên hồ sơ
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="VD: Cert Halal Nhà máy Cà phê Hồ Chí Minh — 2026"
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
              data-testid="dossier-title-input"
            />
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Tiêu chuẩn áp dụng
            </label>
            <div className="space-y-2">
              {standards.map((s) => {
                const sel = selectedStandardId === s.id;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSelectedStandardId(s.id)}
                    className="w-full text-left rounded-xl p-4 transition-all"
                    style={{
                      background: sel ? "#0A1F44" : "#FFFFFF",
                      color: sel ? "#FFFFFF" : "#0A1F44",
                      border: sel
                        ? "2px solid #0A1F44"
                        : "1px solid #E2E8F0",
                      cursor: "pointer",
                    }}
                    data-testid={`standard-option-${s.code}`}
                  >
                    <div className="text-sm font-semibold mb-1">
                      {s.name_vi} {s.is_default && "★"}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: sel ? "#E2E8F0" : "#6B7280" }}
                    >
                      {s.organization} · {s.scheme_version} ·{" "}
                      {s.doc_types.length} loại tài liệu yêu cầu
                    </div>
                  </button>
                );
              })}
            </div>
            {standards.length === 0 && (
              <p className="text-xs" style={{ color: "#6B7280" }}>
                Không có tiêu chuẩn khả dụng cho ngành nghề hiện tại. Liên hệ
                admin.
              </p>
            )}
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1.5"
              style={{ color: "#6B7280" }}
            >
              Ghi chú (tùy chọn)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="VD: Pilot test với CB Hồ Chí Minh"
              rows={3}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-none"
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                color: "#0A1F44",
              }}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Link
              href="/dossiers"
              className="px-5 py-2.5 rounded-xl font-semibold text-sm"
              style={{ color: "#6B7280" }}
            >
              Hủy
            </Link>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!selectedStandardId || !title.trim() || submitting}
              className="btn-lift py-2.5 px-6 rounded-xl font-semibold text-sm"
              style={{
                background:
                  !selectedStandardId || !title.trim() || submitting
                    ? "#E2E8F0"
                    : "#0A1F44",
                color:
                  !selectedStandardId || !title.trim() || submitting
                    ? "#6B7280"
                    : "white",
                cursor:
                  !selectedStandardId || !title.trim() || submitting
                    ? "not-allowed"
                    : "pointer",
              }}
              data-testid="dossier-create-submit"
            >
              {submitting ? "Đang tạo..." : "Tạo hồ sơ"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
