"use client";

/**
 * Admin — Standard types CRUD + doc_types assignment per standard.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { readAdminToken } from "@/lib/adminAuth";

interface DocTypeAssoc {
  doc_type: string;
  required: boolean;
  display_order: number;
}

interface Standard {
  id: string;
  code: string;
  name_vi: string;
  name_en: string | null;
  organization: string | null;
  scheme_version: string | null;
  description: string | null;
  full_text_url: string | null;
  enabled: boolean;
  display_order: number;
  doc_types: DocTypeAssoc[];
}

const KNOWN_DOC_TYPES = [
  "company_profile",
  "halal_policy",
  "has_manual",
  "internal_halal_committee",
  "ingredient_raw_material",
  "process_flow_chart",
  "sop_personal_hygiene",
  "sop_cleaning_sanitation",
  "sop_pest_control",
  "sop_supplier_evaluation",
  "sop_traceability",
  "sop_complaint_handling",
  "generic",
];

const emptyForm = {
  code: "",
  name_vi: "",
  name_en: "",
  organization: "JAKIM",
  scheme_version: "",
  description: "",
  full_text_url: "",
  enabled: true,
  display_order: 0,
};

export default function AdminStandardsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [standards, setStandards] = useState<Standard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Standard | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [docTypesEditor, setDocTypesEditor] = useState<DocTypeAssoc[] | null>(null);
  const [activeStandardId, setActiveStandardId] = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token ?? ""}` };

  const fetchAll = async (t: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/admin/standard-types", {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStandards(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const t = readAdminToken();
    setToken(t);
    if (!t) {
      setError("Cần đăng nhập admin (mở /admin/login hoặc /provider/login)");
      setLoading(false);
      return;
    }
    fetchAll(t);
  }, []);

  const openCreate = () => {
    setForm(emptyForm);
    setEditing(null);
    setCreating(true);
  };

  const openEdit = (s: Standard) => {
    setForm({
      code: s.code,
      name_vi: s.name_vi,
      name_en: s.name_en || "",
      organization: s.organization || "",
      scheme_version: s.scheme_version || "",
      description: s.description || "",
      full_text_url: s.full_text_url || "",
      enabled: s.enabled,
      display_order: s.display_order,
    });
    setEditing(s);
    setCreating(true);
  };

  const handleSubmit = async () => {
    try {
      const body: Record<string, unknown> = {
        name_vi: form.name_vi,
        name_en: form.name_en || null,
        organization: form.organization || null,
        scheme_version: form.scheme_version || null,
        description: form.description || null,
        full_text_url: form.full_text_url || null,
        enabled: form.enabled,
        display_order: form.display_order,
      };
      let res;
      if (editing) {
        res = await fetch(`/api/auth/admin/standard-types/${editing.id}`, {
          method: "PATCH",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        body.code = form.code;
        res = await fetch("/api/auth/admin/standard-types", {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || `HTTP ${res.status}`);
      }
      setCreating(false);
      if (token) fetchAll(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lưu thất bại");
    }
  };

  const handleDisable = async (id: string) => {
    if (!confirm("Disable standard này? Tenants đã chọn sẽ giữ; chỉ block khỏi danh sách mới.")) return;
    await fetch(`/api/auth/admin/standard-types/${id}`, {
      method: "DELETE",
      headers,
    });
    if (token) fetchAll(token);
  };

  const openDocTypesEditor = (s: Standard) => {
    setActiveStandardId(s.id);
    setDocTypesEditor([...s.doc_types]);
  };

  const saveDocTypes = async () => {
    if (!activeStandardId || !docTypesEditor) return;
    const res = await fetch(
      `/api/auth/admin/standard-types/${activeStandardId}/doc-types`,
      {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ doc_types: docTypesEditor }),
      },
    );
    if (res.ok) {
      setDocTypesEditor(null);
      setActiveStandardId(null);
      if (token) fetchAll(token);
    } else {
      setError("Lưu doc-types thất bại");
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
        <div className="flex items-center justify-between mb-6">
          <div>
            <Link href="/admin" className="text-xs" style={{ color: "#6B7280" }}>
              ← Admin
            </Link>
            <h1 className="text-xl font-bold mt-2" style={{ color: "#0A1F44" }}>
              Tiêu chuẩn áp dụng (Standards)
            </h1>
            <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
              Quản lý tiêu chuẩn JAKIM/MUI/BPJPH/TCVN và danh sách doc_types
              mỗi tiêu chuẩn quy định.
            </p>
          </div>
          <button
            onClick={openCreate}
            className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
            style={{ background: "#0A1F44", color: "white" }}
          >
            + Tạo standard mới
          </button>
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
          {standards.map((s) => (
            <div
              key={s.id}
              className="rounded-2xl p-5"
              style={{
                background: s.enabled ? "#FFFFFF" : "#F9FAFB",
                border: "1px solid #E2E8F0",
                opacity: s.enabled ? 1 : 0.6,
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-semibold" style={{ color: "#0A1F44" }}>
                      {s.name_vi}
                    </h3>
                    <code
                      className="text-[10px] px-2 py-0.5 rounded"
                      style={{ background: "#F3F4F6", color: "#6B7280" }}
                    >
                      {s.code}
                    </code>
                    {!s.enabled && (
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded"
                        style={{ background: "#FEF2F2", color: "#DC2626" }}
                      >
                        DISABLED
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-1" style={{ color: "#6B7280" }}>
                    {s.organization} · {s.scheme_version} · {s.doc_types.length}{" "}
                    doc_types
                  </p>
                  {s.description && (
                    <p className="text-xs mt-2" style={{ color: "#6B7280" }}>
                      {s.description}
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-2 items-stretch whitespace-nowrap">
                  <button
                    onClick={() => openEdit(s)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium btn-lift"
                    style={{ background: "#F1F5F9", color: "#0A1F44" }}
                  >
                    Sửa
                  </button>
                  <button
                    onClick={() => openDocTypesEditor(s)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium btn-lift"
                    style={{ background: "#F1F5F9", color: "#0A1F44" }}
                  >
                    Doc-types ({s.doc_types.length})
                  </button>
                  {s.enabled && (
                    <button
                      onClick={() => handleDisable(s.id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium btn-lift"
                      style={{
                        background: "rgba(239,68,68,0.1)",
                        color: "#DC2626",
                        border: "1px solid rgba(239,68,68,0.3)",
                      }}
                    >
                      Disable
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Create/Edit Modal */}
        {creating && (
          <div
            className="fixed inset-0 z-50 grid place-items-center px-6"
            style={{ background: "rgba(0,0,0,0.4)" }}
            onClick={() => setCreating(false)}
          >
            <div
              className="bg-white rounded-2xl p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-lg font-bold mb-4" style={{ color: "#0A1F44" }}>
                {editing ? "Sửa standard" : "Tạo standard mới"}
              </h2>
              <div className="space-y-3">
                {!editing && (
                  <div>
                    <label className="text-xs font-medium" style={{ color: "#6B7280" }}>
                      Code (slug, immutable)
                    </label>
                    <input
                      value={form.code}
                      onChange={(e) =>
                        setForm({ ...form, code: e.target.value.toLowerCase() })
                      }
                      placeholder="vd: ms_1500_2025"
                      className="w-full px-3 py-2 rounded-lg text-sm mt-1"
                      style={{ border: "1px solid #E2E8F0" }}
                    />
                  </div>
                )}
                {[
                  ["name_vi", "Tên VI"],
                  ["name_en", "Tên EN"],
                  ["organization", "Tổ chức (JAKIM/MUI/...)"],
                  ["scheme_version", "Version (vd 2019, 2023)"],
                  ["full_text_url", "URL văn bản gốc"],
                  ["display_order", "Thứ tự hiển thị"],
                ].map(([k, label]) => (
                  <div key={k}>
                    <label className="text-xs font-medium" style={{ color: "#6B7280" }}>
                      {label}
                    </label>
                    <input
                      type={k === "display_order" ? "number" : "text"}
                      value={(form as Record<string, string | number | boolean>)[k] as string}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          [k]: k === "display_order" ? Number(e.target.value) : e.target.value,
                        })
                      }
                      className="w-full px-3 py-2 rounded-lg text-sm mt-1"
                      style={{ border: "1px solid #E2E8F0" }}
                    />
                  </div>
                ))}
                <div>
                  <label className="text-xs font-medium" style={{ color: "#6B7280" }}>
                    Mô tả
                  </label>
                  <textarea
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg text-sm mt-1 resize-none"
                    style={{ border: "1px solid #E2E8F0" }}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                  />
                  Enabled
                </label>
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setCreating(false)}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{ background: "#F1F5F9", color: "#0A1F44" }}
                >
                  Hủy
                </button>
                <button
                  onClick={handleSubmit}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{ background: "#0A1F44", color: "white" }}
                >
                  {editing ? "Lưu" : "Tạo"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Doc-types editor */}
        {docTypesEditor && (
          <div
            className="fixed inset-0 z-50 grid place-items-center px-6"
            style={{ background: "rgba(0,0,0,0.4)" }}
            onClick={() => setDocTypesEditor(null)}
          >
            <div
              className="bg-white rounded-2xl p-6 max-w-md w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-lg font-bold mb-4" style={{ color: "#0A1F44" }}>
                Doc-types của standard
              </h2>
              <p className="text-xs mb-4" style={{ color: "#6B7280" }}>
                Tick để include vào tiêu chuẩn này. Sort drag-free, theo display_order.
              </p>
              <div className="space-y-2">
                {KNOWN_DOC_TYPES.map((dt, idx) => {
                  const existing = docTypesEditor.find((x) => x.doc_type === dt);
                  return (
                    <div
                      key={dt}
                      className="flex items-center gap-3 rounded-lg p-2"
                      style={{ background: existing ? "rgba(10,31,68,0.04)" : "#F9FAFB" }}
                    >
                      <input
                        type="checkbox"
                        checked={!!existing}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setDocTypesEditor([
                              ...docTypesEditor,
                              { doc_type: dt, required: true, display_order: idx + 1 },
                            ]);
                          } else {
                            setDocTypesEditor(
                              docTypesEditor.filter((x) => x.doc_type !== dt),
                            );
                          }
                        }}
                      />
                      <code className="flex-1 text-xs">{dt}</code>
                      {existing && (
                        <label className="flex items-center gap-1 text-xs">
                          <input
                            type="checkbox"
                            checked={existing.required}
                            onChange={(e) =>
                              setDocTypesEditor(
                                docTypesEditor.map((x) =>
                                  x.doc_type === dt ? { ...x, required: e.target.checked } : x,
                                ),
                              )
                            }
                          />
                          required
                        </label>
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <button
                  onClick={() => setDocTypesEditor(null)}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{ background: "#F1F5F9", color: "#0A1F44" }}
                >
                  Hủy
                </button>
                <button
                  onClick={saveDocTypes}
                  className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                  style={{ background: "#0A1F44", color: "white" }}
                >
                  Lưu
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
