"use client";

/**
 * Admin — Industry ↔ Standard M:N mapping editor.
 *
 * Mỗi industry_schema (ngành nghề) có thể áp dụng nhiều standards. Trong số đó
 * 1 standard được đánh dấu is_default (★) — sẽ tự pre-select khi user tạo
 * dossier mới.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { readAdminToken } from "@/lib/adminAuth";

interface Industry {
  id: string;
  code: string;
  name_vi: string;
  enabled: boolean;
  display_order: number;
}

interface Standard {
  id: string;
  code: string;
  name_vi: string;
  organization: string | null;
  enabled: boolean;
}

interface MappingRow {
  industry_id: string;
  standard_type_id: string;
  is_default: boolean;
  display_order: number;
}

interface IndustryWithStandards extends Industry {
  standards: Array<{
    standard_type_id: string;
    code: string;
    name_vi: string;
    is_default: boolean;
    display_order: number;
  }>;
}

interface EditableLink {
  standard_type_id: string;
  is_default: boolean;
  display_order: number;
}

export default function AdminIndustriesPage() {
  const [token, setToken] = useState<string | null>(null);
  const [industries, setIndustries] = useState<IndustryWithStandards[]>([]);
  const [allStandards, setAllStandards] = useState<Standard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingIndustry, setEditingIndustry] = useState<IndustryWithStandards | null>(null);
  const [editorLinks, setEditorLinks] = useState<EditableLink[]>([]);
  const [saving, setSaving] = useState(false);

  const headers = { Authorization: `Bearer ${token ?? ""}` };

  const fetchAll = async (t: string) => {
    setLoading(true);
    setError(null);
    try {
      const authHeaders = { Authorization: `Bearer ${t}` };
      const [indRes, stdRes] = await Promise.all([
        fetch("/api/auth/admin/industry-schemas", { headers: authHeaders }),
        fetch("/api/auth/admin/standard-types", { headers: authHeaders }),
      ]);
      if (!indRes.ok) throw new Error(`Industries HTTP ${indRes.status}`);
      if (!stdRes.ok) throw new Error(`Standards HTTP ${stdRes.status}`);

      const indsRaw: Array<Industry & {
        available_standards?: Array<{
          id: string;
          code: string;
          name_vi: string;
          is_default: boolean;
          display_order: number;
        }>;
      }> = await indRes.json();

      const inds: IndustryWithStandards[] = indsRaw.map((i) => ({
        id: i.id,
        code: i.code,
        name_vi: i.name_vi,
        enabled: i.enabled,
        display_order: i.display_order,
        standards: (i.available_standards || []).map((s) => ({
          standard_type_id: s.id,
          code: s.code,
          name_vi: s.name_vi,
          is_default: s.is_default,
          display_order: s.display_order,
        })),
      }));

      setIndustries(inds);
      setAllStandards(await stdRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được dữ liệu");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = readAdminToken();
    setToken(t);
    if (!t) {
      setError("Cần đăng nhập tài khoản admin qua Keycloak SSO (mở /admin).");
      setLoading(false);
      return;
    }
    fetchAll(t);
  }, []);

  const openEditor = (industry: IndustryWithStandards) => {
    setEditingIndustry(industry);
    setEditorLinks(
      industry.standards.map((s) => ({
        standard_type_id: s.standard_type_id,
        is_default: s.is_default,
        display_order: s.display_order,
      })),
    );
  };

  const toggleStandard = (standardId: string, checked: boolean) => {
    if (checked) {
      setEditorLinks([
        ...editorLinks,
        {
          standard_type_id: standardId,
          is_default: editorLinks.length === 0,
          display_order: editorLinks.length + 1,
        },
      ]);
    } else {
      const removed = editorLinks.find((l) => l.standard_type_id === standardId);
      const next = editorLinks.filter((l) => l.standard_type_id !== standardId);
      // If we removed the default, promote the first remaining
      if (removed?.is_default && next.length > 0) {
        next[0] = { ...next[0], is_default: true };
      }
      setEditorLinks(next);
    }
  };

  const setDefault = (standardId: string) => {
    setEditorLinks(
      editorLinks.map((l) => ({
        ...l,
        is_default: l.standard_type_id === standardId,
      })),
    );
  };

  const moveLink = (standardId: string, dir: -1 | 1) => {
    const idx = editorLinks.findIndex((l) => l.standard_type_id === standardId);
    if (idx < 0) return;
    const targetIdx = idx + dir;
    if (targetIdx < 0 || targetIdx >= editorLinks.length) return;
    const next = [...editorLinks];
    [next[idx], next[targetIdx]] = [next[targetIdx], next[idx]];
    next.forEach((l, i) => (l.display_order = i + 1));
    setEditorLinks(next);
  };

  const saveMapping = async () => {
    if (!editingIndustry) return;
    setSaving(true);
    try {
      const hasDefault = editorLinks.some((l) => l.is_default);
      if (editorLinks.length > 0 && !hasDefault) {
        throw new Error("Cần chọn 1 standard làm default (★)");
      }
      const res = await fetch(
        `/api/auth/admin/standard-types/industries/${editingIndustry.id}/standards`,
        {
          method: "PUT",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ standards: editorLinks }),
        },
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || `HTTP ${res.status}`);
      }
      setEditingIndustry(null);
      setEditorLinks([]);
      if (token) fetchAll(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <p className="text-sm" style={{ color: "#6B7280" }}>Đang tải...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "#FFFFFF" }}>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-6">
          <Link href="/admin" className="text-xs" style={{ color: "#6B7280" }}>
            ← Admin
          </Link>
          <h1 className="text-xl font-bold mt-2" style={{ color: "#0A1F44" }}>
            Ngành nghề ↔ Tiêu chuẩn
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            Map mỗi ngành nghề với 1 hoặc nhiều tiêu chuẩn áp dụng. ★ là tiêu
            chuẩn mặc định khi user tạo hồ sơ mới.
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

        <div className="space-y-3">
          {industries.map((ind) => (
            <div
              key={ind.id}
              className="rounded-2xl p-5"
              style={{
                background: ind.enabled ? "#FFFFFF" : "#F9FAFB",
                border: "1px solid #E2E8F0",
                opacity: ind.enabled ? 1 : 0.6,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3
                      className="text-base font-semibold"
                      style={{ color: "#0A1F44" }}
                    >
                      {ind.name_vi}
                    </h3>
                    <code
                      className="text-[10px] px-2 py-0.5 rounded"
                      style={{ background: "#F3F4F6", color: "#6B7280" }}
                    >
                      {ind.code}
                    </code>
                    {!ind.enabled && (
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded"
                        style={{ background: "#FEF2F2", color: "#DC2626" }}
                      >
                        DISABLED
                      </span>
                    )}
                  </div>
                  {ind.standards.length === 0 ? (
                    <p
                      className="text-xs mt-2"
                      style={{ color: "#DC2626" }}
                    >
                      ⚠ Chưa map tiêu chuẩn — user thuộc ngành này không thể
                      tạo hồ sơ
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {ind.standards.map((s) => (
                        <span
                          key={s.standard_type_id}
                          className="text-[11px] px-2 py-1 rounded-full"
                          style={{
                            background: s.is_default
                              ? "rgba(10,31,68,0.1)"
                              : "#F3F4F6",
                            color: s.is_default ? "#0A1F44" : "#6B7280",
                            border: s.is_default
                              ? "1px solid rgba(10,31,68,0.2)"
                              : "1px solid transparent",
                            fontWeight: s.is_default ? 600 : 400,
                          }}
                        >
                          {s.is_default && "★ "}
                          {s.code}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => openEditor(ind)}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift whitespace-nowrap"
                  style={{ background: "#0A1F44", color: "white" }}
                >
                  Sửa mapping
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Editor modal */}
        {editingIndustry && (
          <div
            className="fixed inset-0 z-50 grid place-items-center px-6"
            style={{ background: "rgba(0,0,0,0.4)" }}
            onClick={() => setEditingIndustry(null)}
          >
            <div
              className="bg-white rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-lg font-bold" style={{ color: "#0A1F44" }}>
                Mapping cho:
              </h2>
              <p className="text-sm mb-4" style={{ color: "#6B7280" }}>
                {editingIndustry.name_vi}
              </p>

              <div className="space-y-2">
                {allStandards
                  .filter((s) => s.enabled)
                  .map((s) => {
                    const link = editorLinks.find(
                      (l) => l.standard_type_id === s.id,
                    );
                    const selected = !!link;
                    return (
                      <div
                        key={s.id}
                        className="rounded-lg p-3"
                        style={{
                          background: selected
                            ? "rgba(10,31,68,0.04)"
                            : "#F9FAFB",
                          border: selected
                            ? "1px solid rgba(10,31,68,0.2)"
                            : "1px solid transparent",
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(e) =>
                              toggleStandard(s.id, e.target.checked)
                            }
                          />
                          <div className="flex-1 min-w-0">
                            <div
                              className="text-sm font-medium truncate"
                              style={{ color: "#0A1F44" }}
                            >
                              {s.name_vi}
                            </div>
                            <code
                              className="text-[10px]"
                              style={{ color: "#6B7280" }}
                            >
                              {s.code} · {s.organization}
                            </code>
                          </div>
                          {selected && (
                            <>
                              <button
                                onClick={() => moveLink(s.id, -1)}
                                title="Move up"
                                className="w-7 h-7 rounded-lg text-xs font-medium btn-lift flex items-center justify-center"
                                style={{ background: "#F1F5F9", color: "#0A1F44" }}
                              >
                                ↑
                              </button>
                              <button
                                onClick={() => moveLink(s.id, 1)}
                                title="Move down"
                                className="w-7 h-7 rounded-lg text-xs font-medium btn-lift flex items-center justify-center"
                                style={{ background: "#F1F5F9", color: "#0A1F44" }}
                              >
                                ↓
                              </button>
                              <label
                                className="flex items-center gap-1 text-xs"
                                style={{ color: "#0A1F44" }}
                              >
                                <input
                                  type="radio"
                                  name={`default-${editingIndustry.id}`}
                                  checked={link?.is_default ?? false}
                                  onChange={() => setDefault(s.id)}
                                />
                                ★ default
                              </label>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setEditingIndustry(null)}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{ background: "#F1F5F9", color: "#0A1F44" }}
                >
                  Hủy
                </button>
                <button
                  onClick={saveMapping}
                  disabled={saving}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{
                    background: saving ? "#94A3B8" : "#0A1F44",
                    color: "white",
                    cursor: saving ? "not-allowed" : "pointer",
                  }}
                >
                  {saving ? "Đang lưu..." : "Lưu mapping"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
