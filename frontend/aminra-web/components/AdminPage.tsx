"use client";

import {
  useState,
  useEffect,
  useCallback,
  useRef,
  Component,
  type ReactNode,
} from "react";
import { useAdminAuth } from "@/components/AdminAuthContext";
import { useUserAuth } from "@/components/UserAuthContext";
import AdminLoginModal from "@/components/AdminLoginModal";
import AdminUserManager from "@/components/AdminUserManager";
import { parseApiError } from "@/lib/apiError";
import Modal from "@/components/Modal";

const API = "/api";

// ─── Error Boundary ──────────────────────────────────────────────────────────

class AdminErrorBoundary extends Component<
  { children: ReactNode; onReset?: () => void },
  { error: Error | null }
> {
  constructor(props: { children: ReactNode; onReset?: () => void }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div
          className="rounded-xl p-6 m-4"
          style={{
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.3)",
          }}
        >
          <h3 className="text-sm font-bold mb-2" style={{ color: "#EF4444" }}>
            Lỗi hiển thị
          </h3>
          <pre
            className="text-xs mb-3 overflow-auto max-h-32"
            style={{ color: "#DC2626" }}
          >
            {this.state.error.message}
          </pre>
          <button
            onClick={() => {
              this.setState({ error: null });
              this.props.onReset?.();
            }}
            className="text-xs px-3 py-1.5 rounded-lg"
            style={{
              background: "rgba(239,68,68,0.15)",
              color: "#EF4444",
              border: "1px solid rgba(239,68,68,0.3)",
            }}
          >
            Thử lại
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Doc type groups ──────────────────────────────────────────────────────────

const DOC_TYPE_GROUPS = [
  {
    group: "Tài liệu chính sách",
    icon: (
      <svg
        className="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
    ),
    types: [
      { id: "halal_policy", label: "Halal Policy" },
      { id: "has_manual", label: "HAS Manual" },
      { id: "halal_manual", label: "Halal Manual" },
      { id: "internal_halal_committee", label: "Internal Halal Committee" },
      { id: "company_profile", label: "Company Profile" },
    ],
  },
  {
    group: "Tài liệu kỹ thuật",
    icon: (
      <svg
        className="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
      </svg>
    ),
    types: [
      { id: "ingredient_raw_material", label: "Ingredient & Raw Material" },
      { id: "process_flow_chart", label: "Process Flow Chart" },
    ],
  },
  {
    group: "SOP Documentation",
    icon: (
      <svg
        className="w-4 h-4"
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
    ),
    types: [
      { id: "sop_raw_material_receiving", label: "Raw Material Receiving" },
      { id: "sop_storage_segregation", label: "Storage & Segregation" },
      { id: "sop_production_operation", label: "Production Operation" },
      { id: "sop_cleaning_sanitation", label: "Cleaning & Sanitation" },
      {
        id: "sop_handling_nonconformances",
        label: "Handling Non-Conformances",
      },
      { id: "sop_complaint_recall", label: "Complaint & Recall" },
    ],
  },
];

// ─── Types ────────────────────────────────────────────────────────────────────

interface Criterion {
  id: string;
  name: string;
  description: string;
  weight: number;
}

interface DocxMetaItem {
  key: string;
  value: string;
}
interface DocxCustomSection {
  title: string;
  content: string;
}
interface DocxConfig {
  cover_meta: DocxMetaItem[];
  confidential_label: string;
  show_toc: boolean;
  show_revision_table: boolean;
  show_approval_block: boolean;
  custom_sections: DocxCustomSection[];
}

const DEFAULT_DOCX_CONFIG: DocxConfig = {
  cover_meta: [],
  confidential_label: "TÀI LIỆU NỘI BỘ",
  show_toc: false,
  show_revision_table: true,
  show_approval_block: true,
  custom_sections: [],
};

interface Template {
  doc_type: string;
  label: string;
  mandatory_criteria: Criterion[];
  evaluation_guidance: string;
  docx_config?: DocxConfig;
  updated_at: string;
}

interface TemplateFile {
  name: string;
  size: number;
  uploaded_at: string;
}

interface Revision {
  action: "upload" | "delete";
  filename: string;
  size?: number;
  timestamp: string;
}

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

// ─── Criterion row ────────────────────────────────────────────────────────────

function CriterionRow({
  c,
  idx,
  onChange,
  onDelete,
}: {
  c: Criterion;
  idx: number;
  onChange: (updated: Criterion) => void;
  onDelete: () => void;
}) {
  return (
    <div
      className="admin-row-appear rounded-2xl p-5 space-y-3 group transition-all duration-200"
      style={{
        background: "linear-gradient(135deg, #FFFFFF 0%, #FFFFFF 100%)",
        border: "1px solid rgba(226,232,240,0.8)",
        animationDelay: `${idx * 40}ms`,
        animationFillMode: "both",
      }}
    >
      <div
        className="grid gap-4 items-start"
        style={{ gridTemplateColumns: "1.75rem 1fr auto" }}
      >
        {/* Index badge */}
        <div
          className="w-7 h-7 rounded-lg grid place-items-center text-xs font-bold mt-0.5"
          style={{
            background: "rgba(14,165,233,0.15)",
            color: "#0EA5E9",
            border: "1px solid rgba(14,165,233,0.25)",
          }}
        >
          {idx + 1}
        </div>

        <div className="space-y-2.5">
          <input
            value={c.name}
            onChange={(e) => onChange({ ...c, name: e.target.value })}
            placeholder="Tên tiêu chí (vd: Chứng nhận Halal nhà cung cấp)"
            className="admin-input w-full px-4 py-2.5 rounded-xl text-sm transition-all duration-200"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0A1F44",
            }}
          />
          <textarea
            value={c.description}
            onChange={(e) => onChange({ ...c, description: e.target.value })}
            placeholder="Mô tả tiêu chí và cách đánh giá…"
            rows={2}
            className="admin-textarea w-full px-4 py-2.5 rounded-xl text-sm transition-all duration-200 resize-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0A1F44",
            }}
          />
        </div>

        {/* Weight + delete */}
        <div className="grid items-center gap-2 justify-items-center">
          <label className="text-xs font-medium" style={{ color: "#6B7280" }}>
            Điểm
          </label>
          <input
            type="number"
            min={1}
            max={100}
            value={c.weight}
            onChange={(e) => onChange({ ...c, weight: Number(e.target.value) })}
            className="admin-input w-16 px-2 py-2 rounded-xl text-sm text-center font-bold transition-all duration-200"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0EA5E9",
            }}
          />
          <button
            onClick={onDelete}
            className="p-2 rounded-xl transition-all duration-200 ease-out hover:scale-110"
            style={{
              color: "#ef4444",
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
            title="Xoá tiêu chí"
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
                strokeWidth="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Template editor ──────────────────────────────────────────────────────────

function TemplateEditor({
  docTypeId,
  label,
  token,
}: {
  docTypeId: string;
  label: string;
  token: string;
}) {
  const [template, setTemplate] = useState<Template | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [files, setFiles] = useState<TemplateFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Template DOCX (VI/EN)
  const [tplFiles, setTplFiles] = useState<
    Record<string, { filename: string; size: number }>
  >({});
  const [tplUploading, setTplUploading] = useState<string | null>(null);
  const [tplLang, setTplLang] = useState<"vi" | "en">("vi");
  const tplViRef = useRef<HTMLInputElement>(null);
  const tplEnRef = useRef<HTMLInputElement>(null);

  const [refLang, setRefLang] = useState<"vi" | "en">("vi");
  const [refFilesByLang, setRefFilesByLang] = useState<
    Record<string, TemplateFile[]>
  >({ vi: [], en: [] });

  const loadFiles = useCallback(() => {
    fetch(`${API}/admin/templates/${docTypeId}/files`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.files_by_lang) {
          setRefFilesByLang({
            vi: d.files_by_lang.vi || [],
            en: d.files_by_lang.en || [],
          });
          // Keep `files` in sync for backwards compat
          setFiles([
            ...(d.files_by_lang.vi || []),
            ...(d.files_by_lang.en || []),
            ...(d.files_by_lang.legacy || []),
          ]);
        } else {
          setFiles(d.files ?? []);
        }
      })
      .catch(() => {});
  }, [docTypeId, token]);

  const loadTplFiles = useCallback(() => {
    fetch(`${API}/admin/templates/${docTypeId}/template-files`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setTplFiles(d.templates ?? {}))
      .catch(() => {});
  }, [docTypeId, token]);

  const uploadTpl = async (lang: string, file: File) => {
    setTplUploading(lang);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("lang", lang);
      const res = await fetch(
        `${API}/admin/templates/${docTypeId}/template-file`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: fd,
        },
      );
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Upload thất bại");
        return;
      }
      loadTplFiles();
    } finally {
      setTplUploading(null);
    }
  };

  const deleteTpl = async (lang: string) => {
    if (!confirm(`Xoá template ${lang.toUpperCase()}?`)) return;
    await fetch(
      `${API}/admin/templates/${docTypeId}/template-file?lang=${lang}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    loadTplFiles();
  };

  const loadRevisions = useCallback(() => {
    fetch(`${API}/admin/templates/${docTypeId}/revisions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => setRevisions(d.revisions ?? []))
      .catch(() => {});
  }, [docTypeId, token]);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/admin/templates/${docTypeId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((d) => {
        setTemplate(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [docTypeId, token]);

  useEffect(() => {
    load();
    loadFiles();
    loadRevisions();
    loadTplFiles();
  }, [load, loadFiles, loadRevisions, loadTplFiles]);

  const uploadFile = async (file: File, fileLang?: string) => {
    const targetLang = fileLang || refLang;
    setUploading(true);
    setUploadError(null);
    const form = new FormData();
    form.append("file", file);
    form.append("lang", targetLang);
    try {
      const res = await fetch(`${API}/admin/templates/${docTypeId}/files`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, `HTTP ${res.status}`));
      }
      loadFiles();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload thất bại");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDeleteFile = async (filename: string) => {
    setDeletingFile(filename);
    try {
      await fetch(
        `${API}/admin/templates/${docTypeId}/files/${encodeURIComponent(filename)}?lang=${refLang}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      loadFiles();
    } finally {
      setDeletingFile(null);
    }
  };

  const addCriterion = () => {
    if (!template) return;
    setTemplate({
      ...template,
      mandatory_criteria: [
        ...(template.mandatory_criteria ?? []),
        { id: `c_${Date.now()}`, name: "", description: "", weight: 10 },
      ],
    });
  };

  const updateCriterion = (idx: number, updated: Criterion) => {
    if (!template) return;
    const list = [...(template.mandatory_criteria ?? [])];
    list[idx] = updated;
    setTemplate({ ...template, mandatory_criteria: list });
  };

  const deleteCriterion = (idx: number) => {
    if (!template) return;
    setTemplate({
      ...template,
      mandatory_criteria: (template.mandatory_criteria ?? []).filter(
        (_, i) => i !== idx,
      ),
    });
  };

  const save = async () => {
    if (!template) return;
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API}/admin/templates/${docTypeId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(template),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  if (loading)
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="admin-shimmer rounded-2xl h-16"
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    );

  if (!template) return null;

  const criteria = template.mandatory_criteria ?? [];
  const totalWeight = criteria.reduce((s, c) => s + (c.weight || 0), 0);
  const weightOk = totalWeight === 100;
  const weightPct = Math.min(totalWeight, 100);

  return (
    <div className="space-y-6">
      {/* ── Template DOCX (VI / EN) ── */}
      {(() => {
        const tplInfo = tplFiles[tplLang];
        const tplInputRef = tplLang === "vi" ? tplViRef : tplEnRef;
        return (
          <div
            className="rounded-2xl overflow-hidden"
            style={{
              border: "1px solid rgba(226,232,240,0.8)",
              background: "#FFFFFF",
            }}
          >
            {/* Header: icon + title + lang tabs + upload btn */}
            <div
              className="px-5 py-4 flex items-center gap-3 flex-wrap"
              style={{ borderBottom: "1px solid rgba(226,232,240,0.6)" }}
            >
              <div
                className="w-8 h-8 rounded-lg grid place-items-center flex-shrink-0"
                style={{
                  background: "rgba(10,31,68,0.12)",
                  border: "1px solid rgba(10,31,68,0.25)",
                }}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="#0A1F44"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "#0A1F44" }}
                >
                  Template DOCX cho tạo hồ sơ
                </h3>
                <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                  File DOCX chứa {`{{placeholders}}`} sẽ được điền thông tin
                  doanh nghiệp
                </p>
              </div>
              <div className="flex gap-2">
                {(["vi", "en"] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => setTplLang(l)}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                    style={{
                      background:
                        tplLang === l
                          ? l === "vi"
                            ? "rgba(239,68,68,0.12)"
                            : "rgba(37,99,235,0.12)"
                          : "transparent",
                      color:
                        tplLang === l
                          ? l === "vi"
                            ? "#EF4444"
                            : "#0EA5E9"
                          : "#6B7280",
                      border: `1px solid ${tplLang === l ? (l === "vi" ? "rgba(239,68,68,0.3)" : "rgba(37,99,235,0.3)") : "#E2E8F0"}`,
                    }}
                  >
                    {l === "vi" ? "🇻🇳 VI" : "🇬🇧 EN"}
                    {tplFiles[l] && (
                      <span
                        className="ml-1 px-1 py-0.5 rounded text-xs"
                        style={{ background: "rgba(0,0,0,0.06)" }}
                      >
                        1
                      </span>
                    )}
                  </button>
                ))}
              </div>
              <button
                onClick={() => tplInputRef.current?.click()}
                disabled={tplUploading !== null}
                className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ease-out hover:scale-105 active:scale-[0.97] flex-shrink-0"
                style={{
                  gridTemplateColumns: "auto 1fr",
                  background: tplUploading
                    ? "rgba(226,232,240,0.5)"
                    : "rgba(10,31,68,0.15)",
                  color: tplUploading ? "#6B7280" : "#0A1F44",
                  border: "1px solid rgba(10,31,68,0.3)",
                }}
              >
                {tplUploading ? (
                  <svg
                    className="w-4 h-4 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v8z"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                )}
                {tplUploading ? "Đang upload…" : "Upload template"}
              </button>
              <input
                ref={tplViRef}
                type="file"
                accept=".docx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadTpl(tplLang, f);
                  if (tplViRef.current) tplViRef.current.value = "";
                }}
              />
              <input
                ref={tplEnRef}
                type="file"
                accept=".docx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadTpl(tplLang, f);
                  if (tplEnRef.current) tplEnRef.current.value = "";
                }}
              />
            </div>
            {/* File display */}
            <div className="mx-5 my-4">
              {!tplInfo ? (
                <div
                  className="rounded-xl py-8 grid place-items-center gap-2 cursor-pointer"
                  style={{ border: "2px dashed rgba(226,232,240,0.6)" }}
                  onClick={() => tplInputRef.current?.click()}
                >
                  <svg
                    className="w-8 h-8"
                    fill="none"
                    stroke="#6B7280"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.5"
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p
                    className="text-sm font-medium"
                    style={{ color: "#6B7280" }}
                  >
                    Kéo thả hoặc nhấn để upload
                  </p>
                  <p className="text-xs" style={{ color: "#94A3B8" }}>
                    DOCX
                  </p>
                </div>
              ) : (
                <div className="p-3 space-y-2">
                  <div
                    className="grid items-center gap-3 px-4 py-3 rounded-xl group/file"
                    style={{
                      gridTemplateColumns: "auto 1fr auto",
                      background: "#FFFFFF",
                      border: "1px solid rgba(226,232,240,0.6)",
                    }}
                  >
                    <div
                      className="w-8 h-8 rounded-lg grid place-items-center"
                      style={{
                        background: "rgba(10,31,68,0.1)",
                        border: "1px solid rgba(10,31,68,0.2)",
                      }}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="#0A1F44"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="1.8"
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p
                        className="text-sm font-medium truncate"
                        style={{ color: "#0A1F44" }}
                      >
                        {tplInfo.filename}
                      </p>
                      <p
                        className="text-xs mt-0.5"
                        style={{ color: "#6B7280" }}
                      >
                        {formatBytes(tplInfo.size)}
                        {tplInfo.updated_at &&
                          ` · ${new Date(tplInfo.updated_at + "Z").toLocaleString("vi-VN")}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <a
                        href={`${API}/admin/templates/${docTypeId}/template-file/view?lang=${tplLang}&token=${encodeURIComponent(token)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Mở file ở tab mới — verify nội dung trước khi business dùng"
                        className="grid items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ease-out hover:scale-105"
                        style={{
                          gridTemplateColumns: "auto auto",
                          color: "#0A1F44",
                          background: "rgba(10,31,68,0.08)",
                          border: "1px solid rgba(10,31,68,0.2)",
                        }}
                      >
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
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                        Xem
                      </a>
                      <button
                        onClick={() => deleteTpl(tplLang)}
                        className="p-2 rounded-lg transition-all opacity-0 group-hover/file:opacity-100 hover:scale-110"
                        style={{
                          color: "#ef4444",
                          background: "rgba(239,68,68,0.1)",
                          border: "1px solid rgba(239,68,68,0.2)",
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
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* ── Reference files ── */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          border: "1px solid rgba(226,232,240,0.8)",
          background: "#FFFFFF",
        }}
      >
        {/* Header: icon + title + lang tabs + upload btn */}
        <div
          className="px-5 py-4 flex items-center gap-3 flex-wrap"
          style={{ borderBottom: "1px solid rgba(226,232,240,0.6)" }}
        >
          <div
            className="w-8 h-8 rounded-lg grid place-items-center flex-shrink-0"
            style={{
              background: "rgba(14,165,233,0.15)",
              border: "1px solid rgba(14,165,233,0.25)",
            }}
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="#0EA5E9"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
              Tài liệu mẫu tham chiếu
            </h3>
            <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
              AI dùng file theo ngôn ngữ tương ứng để đánh giá
            </p>
          </div>
          <div className="flex gap-2">
            {(["vi", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setRefLang(l)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                style={{
                  background:
                    refLang === l
                      ? l === "vi"
                        ? "rgba(239,68,68,0.12)"
                        : "rgba(37,99,235,0.12)"
                      : "transparent",
                  color:
                    refLang === l
                      ? l === "vi"
                        ? "#EF4444"
                        : "#0EA5E9"
                      : "#6B7280",
                  border: `1px solid ${refLang === l ? (l === "vi" ? "rgba(239,68,68,0.3)" : "rgba(37,99,235,0.3)") : "#E2E8F0"}`,
                }}
              >
                {l === "vi" ? "🇻🇳 VI" : "🇬🇧 EN"}
                {(refFilesByLang[l]?.length || 0) > 0 && (
                  <span
                    className="ml-1 px-1 py-0.5 rounded text-xs"
                    style={{ background: "rgba(0,0,0,0.06)" }}
                  >
                    {refFilesByLang[l].length}
                  </span>
                )}
              </button>
            ))}
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ease-out hover:scale-105 active:scale-[0.97] flex-shrink-0"
            style={{
              gridTemplateColumns: "auto 1fr",
              background: uploading
                ? "rgba(226,232,240,0.5)"
                : "rgba(14,165,233,0.15)",
              color: uploading ? "#6B7280" : "#0EA5E9",
              border: "1px solid rgba(14,165,233,0.3)",
            }}
          >
            {uploading ? (
              <svg
                className="w-4 h-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8v8z"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            )}
            {uploading ? "Đang upload…" : "Upload file mẫu"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.pptx,.ppt,.docx,.txt,.md"
            className="hidden"
            onChange={handleFileUpload}
          />
        </div>

        {/* Drop zone */}
        <div
          className="mx-5 my-4 rounded-xl transition-all duration-200 cursor-pointer"
          style={{
            border: dragOver
              ? "2px dashed rgba(14,165,233,0.6)"
              : "2px dashed rgba(226,232,240,0.6)",
            background: dragOver ? "rgba(14,165,233,0.06)" : "transparent",
            transform: dragOver ? "scale(1.01)" : "scale(1)",
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          {(refFilesByLang[refLang]?.length || 0) === 0 ? (
            <div className="grid place-items-center py-8 gap-2">
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="#6B7280"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className="text-sm font-medium" style={{ color: "#6B7280" }}>
                Kéo thả hoặc nhấn để upload
              </p>
              <p className="text-xs" style={{ color: "#94A3B8" }}>
                PDF, DOCX, PPTX, TXT, MD
              </p>
            </div>
          ) : (
            <div className="p-3 space-y-2">
              {(refFilesByLang[refLang] || []).map((f) => (
                <div
                  key={f.name}
                  className="grid items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group/file"
                  style={{
                    gridTemplateColumns: "auto 1fr auto",
                    background: "#FFFFFF",
                    border: "1px solid rgba(226,232,240,0.6)",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div
                    className="w-8 h-8 rounded-lg grid place-items-center"
                    style={{
                      background: "rgba(10,31,68,0.1)",
                      border: "1px solid rgba(10,31,68,0.2)",
                    }}
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="#0A1F44"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.8"
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p
                      className="text-sm font-medium truncate"
                      style={{ color: "#0A1F44" }}
                    >
                      {f.name}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                      {formatBytes(f.size)}
                    </p>
                  </div>
                  <div
                    className="flex items-center gap-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <a
                      href={`${API}/admin/templates/${docTypeId}/files/${encodeURIComponent(f.name)}/view?lang=${refLang}&token=${encodeURIComponent(token)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      title="Mở file ở tab mới"
                      className="grid items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ease-out hover:scale-105"
                      style={{
                        gridTemplateColumns: "auto auto",
                        color: "#0A1F44",
                        background: "rgba(10,31,68,0.08)",
                        border: "1px solid rgba(10,31,68,0.2)",
                      }}
                    >
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
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                      Xem
                    </a>
                    <button
                      onClick={() => handleDeleteFile(f.name)}
                      disabled={deletingFile === f.name}
                      className="p-2 rounded-lg transition-all duration-200 opacity-0 group-hover/file:opacity-100 hover:scale-110"
                      style={{
                        color: "#ef4444",
                        background: "rgba(239,68,68,0.1)",
                        border: "1px solid rgba(239,68,68,0.2)",
                      }}
                    >
                      {deletingFile === f.name ? (
                        <svg
                          className="w-4 h-4 animate-spin"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          />
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8v8z"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              ))}
              {/* Add more hint */}
              <div className="grid grid-flow-col place-items-center gap-2 py-2 justify-center">
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="#94A3B8"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                <p className="text-xs" style={{ color: "#94A3B8" }}>
                  Kéo thả thêm file vào đây
                </p>
              </div>
            </div>
          )}
        </div>

        {uploadError && (
          <div
            className="mx-5 mb-4 grid items-center gap-2 px-4 py-3 rounded-xl admin-fade-in"
            style={{
              gridTemplateColumns: "auto 1fr",
              color: "#EF4444",
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.2)",
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
                strokeWidth="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-sm">{uploadError}</p>
          </div>
        )}
      </div>

      {/* ── Criteria list ── */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          border: "1px solid rgba(226,232,240,0.8)",
          background: "#FFFFFF",
        }}
      >
        <div
          className="px-5 py-4"
          style={{ borderBottom: "1px solid rgba(226,232,240,0.6)" }}
        >
          <div
            className="grid items-center"
            style={{ gridTemplateColumns: "1fr auto" }}
          >
            <div className="grid grid-flow-col items-center gap-3 justify-start">
              <div
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{
                  background: "rgba(10,31,68,0.12)",
                  border: "1px solid rgba(10,31,68,0.25)",
                }}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="#0A1F44"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  />
                </svg>
              </div>
              <div>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "#0A1F44" }}
                >
                  Tiêu chí bắt buộc
                </h3>
                <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                  {criteria.length} tiêu chí — AI dùng để chấm điểm từng mục
                </p>
              </div>
            </div>
            <button
              onClick={addCriterion}
              className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ease-out hover:scale-105 active:scale-[0.97]"
              style={{
                gridTemplateColumns: "auto 1fr",
                background: "rgba(10,31,68,0.12)",
                color: "#0A1F44",
                border: "1px solid rgba(10,31,68,0.25)",
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
                  strokeWidth="2"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Thêm tiêu chí
            </button>
          </div>

          {/* Weight progress bar */}
          {criteria.length > 0 && (
            <div className="mt-4 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: "#6B7280" }}>
                  Tổng điểm
                </span>
                <span
                  className="text-xs font-bold"
                  style={{ color: weightOk ? "#0A1F44" : "#f59e0b" }}
                >
                  {totalWeight} / 100 {weightOk ? "✓" : "(nên = 100)"}
                </span>
              </div>
              <div
                className="h-1.5 rounded-full overflow-hidden"
                style={{ background: "rgba(226,232,240,0.8)" }}
              >
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${weightPct}%`,
                    background: weightOk
                      ? "linear-gradient(90deg, #0A1F44, #0A1F44)"
                      : totalWeight > 100
                        ? "linear-gradient(90deg, #dc2626, #EF4444)"
                        : "linear-gradient(90deg, #d97706, #F59E0B)",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        <div className="p-5">
          {criteria.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{
                  background: "rgba(226,232,240,0.5)",
                  border: "1px dashed rgba(226,232,240,0.8)",
                }}
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="#94A3B8"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.8"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium" style={{ color: "#6B7280" }}>
                Chưa có tiêu chí nào
              </p>
              <p className="text-xs" style={{ color: "#94A3B8" }}>
                Nhấn "+ Thêm tiêu chí" để bắt đầu
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {criteria.map((c, i) => (
                <CriterionRow
                  key={c.id}
                  c={c}
                  idx={i}
                  onChange={(updated) => updateCriterion(i, updated)}
                  onDelete={() => deleteCriterion(i)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Evaluation guidance ── */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          border: "1px solid rgba(226,232,240,0.8)",
          background: "#FFFFFF",
        }}
      >
        <div
          className="px-5 py-4"
          style={{ borderBottom: "1px solid rgba(226,232,240,0.6)" }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{
                background: "rgba(168,85,247,0.12)",
                border: "1px solid rgba(168,85,247,0.25)",
              }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="#c084fc"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.8"
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
            </div>
            <div>
              <h3
                className="text-sm font-semibold"
                style={{ color: "#0A1F44" }}
              >
                Hướng dẫn đánh giá cho AI
              </h3>
              <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                AI đọc hướng dẫn này để hiểu ngữ cảnh và cách chấm điểm
              </p>
            </div>
          </div>
        </div>
        <div className="p-5">
          <textarea
            value={template.evaluation_guidance}
            onChange={(e) =>
              setTemplate({ ...template, evaluation_guidance: e.target.value })
            }
            placeholder="Nhập hướng dẫn đánh giá tổng quát cho loại tài liệu này. AI sẽ đọc hướng dẫn này khi chấm điểm…"
            rows={5}
            className="admin-textarea w-full px-4 py-3 rounded-xl text-sm transition-all duration-200 resize-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0A1F44",
            }}
          />
        </div>
      </div>

      {/* ── DOCX Template Config ── */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{
          border: "1px solid rgba(99,102,241,0.3)",
          background: "#FFFFFF",
        }}
      >
        <div
          className="px-5 py-4"
          style={{
            borderBottom: "1px solid rgba(99,102,241,0.2)",
            background: "rgba(99,102,241,0.06)",
          }}
        >
          <div className="grid grid-flow-col items-center gap-2.5 justify-start">
            <span style={{ color: "#6366F1", fontSize: 16 }}>⎙</span>
            <div>
              <h3
                className="text-sm font-semibold"
                style={{ color: "#0A1F44" }}
              >
                Định dạng tài liệu DOCX
              </h3>
              <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                Cấu hình trang bìa, phần mục, metadata cho file xuất ra
              </p>
            </div>
          </div>
        </div>
        <div className="p-5 space-y-5">
          {(() => {
            const dc: DocxConfig = {
              ...DEFAULT_DOCX_CONFIG,
              ...(template.docx_config || {}),
              cover_meta: Array.isArray(template.docx_config?.cover_meta)
                ? template.docx_config.cover_meta
                : [],
              custom_sections: Array.isArray(
                template.docx_config?.custom_sections,
              )
                ? template.docx_config.custom_sections
                : [],
            };
            const update = (patch: Partial<DocxConfig>) =>
              setTemplate({ ...template, docx_config: { ...dc, ...patch } });

            return (
              <>
                {/* Confidential label */}
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Nhãn phân loại tài liệu (header)
                  </label>
                  <input
                    value={dc.confidential_label}
                    onChange={(e) =>
                      update({ confidential_label: e.target.value })
                    }
                    placeholder="TÀI LIỆU NỘI BỘ"
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                      color: "#0A1F44",
                    }}
                  />
                </div>

                {/* Toggles */}
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { key: "show_toc" as const, label: "Mục lục (TOC)" },
                    {
                      key: "show_revision_table" as const,
                      label: "Bảng lịch sử thay đổi",
                    },
                    {
                      key: "show_approval_block" as const,
                      label: "Bảng phê duyệt (trang bìa)",
                    },
                  ].map((opt) => (
                    <label
                      key={opt.key}
                      className="grid grid-flow-col items-center gap-2 justify-start cursor-pointer px-3 py-2.5 rounded-lg transition-all"
                      style={{
                        background: dc[opt.key]
                          ? "rgba(99,102,241,0.1)"
                          : "#FFFFFF",
                        border: dc[opt.key]
                          ? "1px solid rgba(99,102,241,0.3)"
                          : "1px solid rgba(226,232,240,0.5)",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={dc[opt.key]}
                        onChange={(e) =>
                          update({ [opt.key]: e.target.checked })
                        }
                        className="rounded"
                      />
                      <span
                        className="text-xs"
                        style={{ color: dc[opt.key] ? "#6366F1" : "#6B7280" }}
                      >
                        {opt.label}
                      </span>
                    </label>
                  ))}
                </div>

                {/* Cover metadata */}
                <div>
                  <div className="grid grid-flow-col items-center gap-2 mb-2 justify-start">
                    <span
                      className="text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      Metadata trang bìa
                    </span>
                    <button
                      onClick={() =>
                        update({
                          cover_meta: [
                            ...dc.cover_meta,
                            { key: "", value: "" },
                          ],
                        })
                      }
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: "rgba(99,102,241,0.15)",
                        color: "#6366F1",
                      }}
                    >
                      + Thêm
                    </button>
                  </div>
                  <div className="space-y-2">
                    {dc.cover_meta.map((m, i) => (
                      <div
                        key={i}
                        className="grid gap-2 items-center"
                        style={{ gridTemplateColumns: "1fr 1fr auto" }}
                      >
                        <input
                          value={m.key}
                          onChange={(e) => {
                            const arr = [...dc.cover_meta];
                            arr[i] = { ...arr[i], key: e.target.value };
                            update({ cover_meta: arr });
                          }}
                          placeholder="Tên trường"
                          className="px-3 py-2 rounded-lg text-xs outline-none"
                          style={{
                            background: "#FFFFFF",
                            border: "1px solid #E2E8F0",
                            color: "#0A1F44",
                          }}
                        />
                        <input
                          value={m.value}
                          onChange={(e) => {
                            const arr = [...dc.cover_meta];
                            arr[i] = { ...arr[i], value: e.target.value };
                            update({ cover_meta: arr });
                          }}
                          placeholder="Giá trị"
                          className="px-3 py-2 rounded-lg text-xs outline-none"
                          style={{
                            background: "#FFFFFF",
                            border: "1px solid #E2E8F0",
                            color: "#0A1F44",
                          }}
                        />
                        <button
                          onClick={() =>
                            update({
                              cover_meta: dc.cover_meta.filter(
                                (_, j) => j !== i,
                              ),
                            })
                          }
                          className="text-xs text-slate-600 hover:text-red-400 px-1"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    {dc.cover_meta.length === 0 && (
                      <p className="text-xs" style={{ color: "#94A3B8" }}>
                        Chưa có — sẽ dùng metadata mặc định của template
                      </p>
                    )}
                  </div>
                </div>

                {/* Custom sections */}
                <div>
                  <div className="grid grid-flow-col items-center gap-2 mb-2 justify-start">
                    <span
                      className="text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      Phần tùy chỉnh (trước nội dung chính)
                    </span>
                    <button
                      onClick={() =>
                        update({
                          custom_sections: [
                            ...dc.custom_sections,
                            { title: "", content: "" },
                          ],
                        })
                      }
                      className="text-xs px-2 py-0.5 rounded"
                      style={{
                        background: "rgba(99,102,241,0.15)",
                        color: "#6366F1",
                      }}
                    >
                      + Thêm phần
                    </button>
                  </div>
                  <div className="space-y-3">
                    {dc.custom_sections.map((sec, i) => (
                      <div
                        key={i}
                        className="rounded-xl p-3 space-y-2"
                        style={{
                          background: "#FFFFFF",
                          border: "1px solid rgba(226,232,240,0.5)",
                        }}
                      >
                        <div
                          className="grid gap-2 items-center"
                          style={{ gridTemplateColumns: "1fr auto" }}
                        >
                          <input
                            value={sec.title}
                            onChange={(e) => {
                              const arr = [...dc.custom_sections];
                              arr[i] = { ...arr[i], title: e.target.value };
                              update({ custom_sections: arr });
                            }}
                            placeholder="Tiêu đề phần"
                            className="px-3 py-2 rounded-lg text-xs outline-none font-medium"
                            style={{
                              background: "#FFFFFF",
                              border: "1px solid #E2E8F0",
                              color: "#0A1F44",
                            }}
                          />
                          <button
                            onClick={() =>
                              update({
                                custom_sections: dc.custom_sections.filter(
                                  (_, j) => j !== i,
                                ),
                              })
                            }
                            className="text-xs text-slate-600 hover:text-red-400 px-1"
                          >
                            ✕
                          </button>
                        </div>
                        <textarea
                          value={sec.content}
                          onChange={(e) => {
                            const arr = [...dc.custom_sections];
                            arr[i] = { ...arr[i], content: e.target.value };
                            update({ custom_sections: arr });
                          }}
                          placeholder="Nội dung (mỗi dòng = 1 đoạn, dùng - ở đầu dòng cho bullet)"
                          rows={3}
                          className="w-full px-3 py-2 rounded-lg text-xs outline-none resize-none"
                          style={{
                            background: "#FFFFFF",
                            border: "1px solid #E2E8F0",
                            color: "#0A1F44",
                          }}
                        />
                      </div>
                    ))}
                    {dc.custom_sections.length === 0 && (
                      <p className="text-xs" style={{ color: "#94A3B8" }}>
                        Chưa có — nội dung sẽ chỉ gồm phần AI tạo ra
                      </p>
                    )}
                  </div>
                </div>
              </>
            );
          })()}
        </div>
      </div>

      {/* ── Save bar ── */}
      <div className="grid grid-flow-col items-center gap-4 px-1 mt-6 mb-2 justify-start">
        <button
          onClick={save}
          disabled={saving}
          className={`grid items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${saved ? "admin-pulse-glow" : ""}`}
          style={{
            gridTemplateColumns: "auto 1fr",
            background: saving
              ? "rgba(10,31,68,0.4)"
              : saved
                ? "#0A1F44"
                : "linear-gradient(135deg, #0A1F44, #0A1F44)",
            color: saving ? "rgba(255,255,255,0.5)" : "white",
            boxShadow: saved
              ? "0 0 20px rgba(10,31,68,0.3)"
              : "0 4px 12px rgba(10,31,68,0.25)",
            transform: saving ? "scale(0.98)" : "scale(1)",
          }}
        >
          {saving ? (
            <svg
              className="w-4 h-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8z"
              />
            </svg>
          ) : saved ? (
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
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : (
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"
              />
            </svg>
          )}
          {saving ? "Đang lưu…" : saved ? "Đã lưu thành công!" : "Lưu template"}
        </button>

        {template.updated_at && (
          <span className="text-xs ml-auto" style={{ color: "#94A3B8" }}>
            Cập nhật lúc {new Date(template.updated_at).toLocaleString("vi-VN")}
          </span>
        )}
      </div>

      <div className="pb-6" />
    </div>
  );
}

// ─── Main admin page ──────────────────────────────────────────────────────────

// ─── Placeholder Manager ─────────────────────────────────────────────────────

function PlaceholderManager({ token }: { token: string }) {
  const [placeholders, setPlaceholders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [form, setForm] = useState({
    key: "",
    label: "",
    description: "",
    default_value: "",
    source: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const authHdr = { Authorization: `Bearer ${token}` };

  const fetchPlaceholders = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/admin/placeholders`, {
        headers: authHdr,
      });
      if (res.ok) {
        const d = await res.json();
        setPlaceholders(d.placeholders || []);
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchPlaceholders();
  }, [fetchPlaceholders]);

  const openAdd = () => {
    setEditKey(null);
    setForm({
      key: "",
      label: "",
      description: "",
      default_value: "",
      source: "",
    });
    setError("");
    setShowForm(true);
  };

  const openEdit = (p: any) => {
    setEditKey(p.key);
    setForm({
      key: p.key,
      label: p.label,
      description: p.description || "",
      default_value: p.default_value || "",
      source: p.source || "",
    });
    setError("");
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.key || !form.label) return;
    setSaving(true);
    setError("");
    try {
      const isEdit = !!editKey;
      const url = isEdit
        ? `${API}/admin/placeholders/${editKey}`
        : `${API}/admin/placeholders`;
      const res = await fetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: { ...authHdr, "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || "Lỗi");
        return;
      }
      setShowForm(false);
      setEditKey(null);
      setForm({
        key: "",
        label: "",
        description: "",
        default_value: "",
        source: "",
      });
      fetchPlaceholders();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (key: string) => {
    if (!confirm(`Xoá placeholder {{${key}}}?`)) return;
    await fetch(`${API}/admin/placeholders/${key}`, {
      method: "DELETE",
      headers: authHdr,
    });
    fetchPlaceholders();
  };

  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold" style={{ color: "#0A1F44" }}>
            Quản lý Placeholders
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
            Định nghĩa các biến dùng trong template DOCX. Dùng cú pháp{" "}
            {`{{key}}`} trong file mẫu.
          </p>
        </div>
        <button
          onClick={openAdd}
          className="px-4 py-2 rounded-lg text-xs font-semibold text-white"
          style={{ background: "#0A1F44" }}
        >
          + Thêm placeholder
        </button>
      </div>

      {/* List */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: "1px solid #E2E8F0" }}
      >
        {loading ? (
          <div
            className="py-8 text-center text-sm"
            style={{ color: "#6B7280" }}
          >
            Đang tải...
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead style={{ background: "#F5F1E8" }}>
              <tr>
                {["Placeholder", "Tên hiển thị", "Nguồn dữ liệu", ""].map(
                  (h) => (
                    <th
                      key={h}
                      className="text-left px-4 py-3 text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {placeholders.map((p, i) => (
                <tr
                  key={p.key}
                  style={{
                    background: i % 2 === 0 ? "#FFFFFF" : "#FFFFFF",
                    borderTop: "1px solid #E2E8F0",
                  }}
                >
                  <td className="px-4 py-3">
                    <code
                      className="px-2 py-0.5 rounded text-xs font-mono"
                      style={{
                        background: p.is_system ? "#F0F9FF" : "#F5F3FF",
                        color: p.is_system ? "#0369A1" : "#7C3AED",
                      }}
                    >
                      {`{{${p.key}}}`}
                    </code>
                  </td>
                  <td
                    className="px-4 py-3 font-medium"
                    style={{ color: "#0A1F44" }}
                  >
                    {p.label}
                  </td>
                  <td
                    className="px-4 py-3 text-xs"
                    style={{ color: "#6B7280" }}
                  >
                    {p.source ? (
                      <span
                        className="px-2 py-0.5 rounded"
                        style={{ background: "#F0F9FF", color: "#0369A1" }}
                      >
                        {p.source.startsWith("auto:")
                          ? `Tự động: ${p.source.replace("auto:", "")}`
                          : `DB: ${p.source}`}
                      </span>
                    ) : p.default_value ? (
                      <span>Tĩnh: {p.default_value}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {p.is_system ? (
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={{ background: "#F0F9FF", color: "#0369A1" }}
                      >
                        Hệ thống
                      </span>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openEdit(p)}
                          className="text-xs transition-colors hover:text-blue-600"
                          style={{ color: "#6B7280" }}
                        >
                          Sửa
                        </button>
                        <button
                          onClick={() => handleDelete(p.key)}
                          className="text-xs transition-colors hover:text-red-500"
                          style={{ color: "#9CA3AF" }}
                        >
                          Xoá
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add modal */}
      {showForm && (
        <Modal onClose={() => setShowForm(false)}>
          <div
            className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              className="text-base font-bold mb-4"
              style={{ color: "#0A1F44" }}
            >
              {editKey ? "Sửa Placeholder" : "Thêm Placeholder"}
            </h3>
            <div className="space-y-3">
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Key (không dấu, gạch dưới) *
                </label>
                <div className="flex items-center gap-1">
                  <span
                    className="text-sm"
                    style={{ color: "#9CA3AF" }}
                  >{`{{`}</span>
                  <input
                    value={form.key}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        key: e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9_]/g, ""),
                      }))
                    }
                    placeholder="vd: ma_so_thue"
                    readOnly={!!editKey}
                    className="flex-1 px-3 py-2 rounded-lg text-sm outline-none font-mono"
                    style={{
                      ...inputStyle,
                      opacity: editKey ? 0.6 : 1,
                      cursor: editKey ? "not-allowed" : "text",
                    }}
                  />
                  <span
                    className="text-sm"
                    style={{ color: "#9CA3AF" }}
                  >{`}}`}</span>
                </div>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Tên hiển thị *
                </label>
                <input
                  value={form.label}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, label: e.target.value }))
                  }
                  placeholder="VD: Mã số thuế"
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={inputStyle}
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Mô tả
                </label>
                <input
                  value={form.description}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, description: e.target.value }))
                  }
                  placeholder="VD: Lấy từ thông tin doanh nghiệp"
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={inputStyle}
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Nguồn dữ liệu
                </label>
                <select
                  value={form.source}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, source: e.target.value }))
                  }
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                  style={inputStyle}
                >
                  <option value="">Giá trị mặc định (tĩnh)</option>
                  <optgroup label="Thông tin doanh nghiệp">
                    <option value="company_name">Tên công ty</option>
                    <option value="representative_name">
                      Giám đốc / Người đại diện
                    </option>
                    <option value="address">Địa chỉ</option>
                    <option value="phone">Số điện thoại</option>
                    <option value="email">Email</option>
                    <option value="manager_name">Người quản lý hệ thống</option>
                  </optgroup>
                  <optgroup label="Tự động">
                    <option value="auto:date">Ngày tạo (DD/MM/YYYY)</option>
                    <option value="auto:year">Năm hiện tại</option>
                    <option value="auto:month">Tháng hiện tại</option>
                    <option value="auto:day">Ngày hiện tại</option>
                  </optgroup>
                </select>
              </div>
              {!form.source && (
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Giá trị mặc định
                  </label>
                  <input
                    value={form.default_value}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, default_value: e.target.value }))
                    }
                    placeholder="VD: Nguyễn Văn A"
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  />
                </div>
              )}
              {error && (
                <p className="text-xs" style={{ color: "#DC2626" }}>
                  {error}
                </p>
              )}
              <button
                onClick={handleSave}
                disabled={saving || !form.key || !form.label}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{
                  background: !form.key || !form.label ? "#E2E8F0" : "#0A1F44",
                  color: !form.key || !form.label ? "#9CA3AF" : "#fff",
                }}
              >
                {saving
                  ? "Đang lưu..."
                  : editKey
                    ? "Cập nhật"
                    : `Tạo {{${form.key || "..."}}}`}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default function AdminPageClient() {
  const { isAdmin, token } = useAdminAuth();
  const { isAuthenticated: isUserLoggedIn } = useUserAuth();
  const [showLogin, setShowLogin] = useState(false);
  const [activeSection, setActiveSection] = useState<
    "templates" | "users" | "placeholders"
  >("templates");
  const [activeGroup, setActiveGroup] = useState(0);
  const [activeType, setActiveType] = useState(DOC_TYPE_GROUPS[0].types[0].id);

  // Block access when a business/provider user is logged in
  if (isUserLoggedIn) {
    return (
      <div className="grid place-items-center min-h-[70vh] text-center px-4">
        <div className="admin-scale-in">
          <div className="relative mx-auto mb-6 w-24 h-24">
            <div
              className="absolute inset-0 rounded-full blur-xl opacity-30"
              style={{
                background: "radial-gradient(circle, #ef4444, transparent)",
              }}
            />
            <div
              className="relative w-24 h-24 rounded-full grid place-items-center"
              style={{
                background:
                  "linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.05))",
                border: "1px solid rgba(239,68,68,0.3)",
              }}
            >
              <svg
                className="w-10 h-10"
                fill="none"
                stroke="#ef4444"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                />
              </svg>
            </div>
          </div>
          <h2 className="text-2xl font-bold mb-3" style={{ color: "#0A1F44" }}>
            Không có quyền truy cập
          </h2>
          <p
            className="text-base mb-4 max-w-sm mx-auto leading-relaxed"
            style={{ color: "#6B7280" }}
          >
            Bạn đang đăng nhập bằng tài khoản doanh nghiệp/tổ chức. Vui lòng
            đăng xuất trước khi truy cập khu vực Admin.
          </p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="grid place-items-center min-h-[70vh] text-center px-4">
        <div className="admin-scale-in">
          {/* Lock icon with glow */}
          <div className="relative mx-auto mb-6 w-24 h-24">
            <div
              className="absolute inset-0 rounded-full blur-xl opacity-30"
              style={{
                background: "radial-gradient(circle, #f59e0b, transparent)",
              }}
            />
            <div
              className="relative w-24 h-24 rounded-full grid place-items-center"
              style={{
                background:
                  "linear-gradient(135deg, rgba(245,158,11,0.15), rgba(245,158,11,0.05))",
                border: "1px solid rgba(245,158,11,0.3)",
              }}
            >
              <svg
                className="w-10 h-10"
                fill="none"
                stroke="#f59e0b"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.5"
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
            </div>
          </div>

          <h2 className="text-2xl font-bold mb-3" style={{ color: "#0A1F44" }}>
            Khu vực dành cho Admin
          </h2>
          <p
            className="text-base mb-8 max-w-sm mx-auto leading-relaxed"
            style={{ color: "#6B7280" }}
          >
            Bạn cần đăng nhập bằng tài khoản admin để truy cập và quản lý
            template đánh giá.
          </p>
          <button
            onClick={() => setShowLogin(true)}
            className="inline-grid items-center gap-2 px-8 py-3.5 rounded-2xl font-semibold text-base transition-all duration-200 ease-out hover:scale-105 active:scale-[0.97]"
            style={{
              gridTemplateColumns: "auto 1fr",
              background: "linear-gradient(135deg, #0A1F44, #0A1F44)",
              color: "white",
              boxShadow: "0 4px 20px rgba(10,31,68,0.35)",
            }}
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
              />
            </svg>
            Đăng nhập Admin
          </button>
          {showLogin && <AdminLoginModal onClose={() => setShowLogin(false)} />}
        </div>
      </div>
    );
  }

  const currentGroup = DOC_TYPE_GROUPS[activeGroup];
  const currentType =
    currentGroup.types.find((t) => t.id === activeType) ??
    currentGroup.types[0];

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full admin-fade-in">
      {/* ── Header ── */}
      <div className="mb-8">
        <div className="grid grid-flow-col items-center gap-3 mb-2 justify-start">
          <div
            className="w-10 h-10 rounded-xl grid place-items-center"
            style={{
              background:
                "linear-gradient(135deg, rgba(10,31,68,0.2), rgba(10,31,68,0.08))",
              border: "1px solid rgba(10,31,68,0.3)",
            }}
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="#0A1F44"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
              Admin Panel
            </h1>
            <p className="text-sm" style={{ color: "#6B7280" }}>
              Quản lý template và tiêu chí đánh giá Halal
            </p>
          </div>
        </div>

        {/* Section tabs */}
        <div className="grid grid-flow-col gap-2 mt-5 justify-start">
          {[
            { key: "templates", label: "Template đánh giá" },
            { key: "placeholders", label: "Placeholders" },
            { key: "users", label: "Quản lý Users" },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() =>
                setActiveSection(
                  tab.key as "templates" | "users" | "placeholders",
                )
              }
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              style={{
                background:
                  activeSection === tab.key
                    ? "rgba(10,31,68,0.15)"
                    : "rgba(0,0,0,0.02)",
                color: activeSection === tab.key ? "#0A1F44" : "#6B7280",
                border:
                  activeSection === tab.key
                    ? "1px solid rgba(10,31,68,0.3)"
                    : "1px solid #E2E8F0",
              }}
            >
              {tab.label}
            </button>
          ))}
          <a
            href="/admin/analytics"
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            style={{
              background: "rgba(0,0,0,0.02)",
              color: "#6B7280",
              border: "1px solid #E2E8F0",
              textDecoration: "none",
            }}
          >
            Analytics
          </a>
          <a
            href="/admin/audit-logs"
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            style={{
              background: "rgba(0,0,0,0.02)",
              color: "#6B7280",
              border: "1px solid #E2E8F0",
              textDecoration: "none",
            }}
          >
            Audit logs
          </a>
          <a
            href="/admin/overdue-submissions"
            className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
            style={{
              background: "rgba(220,38,38,0.05)",
              color: "#dc2626",
              border: "1px solid rgba(220,38,38,0.2)",
              textDecoration: "none",
            }}
          >
            ⚠ Overdue queue
          </a>
        </div>
      </div>

      {/* ── Placeholders section ── */}
      {activeSection === "placeholders" && (
        <PlaceholderManager token={token!} />
      )}

      {/* ── Users section ── */}
      {activeSection === "users" && (
        <div
          className="rounded-2xl p-6"
          style={{
            background: "#FFFFFF",
            border: "1px solid rgba(226,232,240,0.6)",
          }}
        >
          <AdminUserManager token={token!} />
        </div>
      )}

      {/* ── Templates section ── */}
      {activeSection === "templates" && (
        <div
          className="grid gap-6 flex-1 lg:min-h-0"
          style={{ gridTemplateColumns: "16rem 1fr" }}
        >
          {/* ── Sidebar ── */}
          <div
            className="space-y-2 admin-scroll overflow-y-auto"
            style={{ maxHeight: "calc(100vh - 180px)" }}
          >
            {DOC_TYPE_GROUPS.map((grp, gi) => (
              <div
                key={gi}
                className="rounded-2xl overflow-hidden"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid rgba(226,232,240,0.6)",
                }}
              >
                {/* Group header */}
                <div
                  className="grid grid-flow-col items-center gap-2.5 px-4 py-3 justify-start"
                  style={{ borderBottom: "1px solid rgba(226,232,240,0.4)" }}
                >
                  <span style={{ color: "#6B7280" }}>{grp.icon}</span>
                  <p
                    className="text-xs font-semibold uppercase tracking-wider"
                    style={{ color: "#6B7280" }}
                  >
                    {grp.group}
                  </p>
                </div>
                {/* Type items */}
                <div className="p-2 space-y-1">
                  {grp.types.map((dt) => {
                    const isActive = activeType === dt.id;
                    return (
                      <button
                        key={dt.id}
                        onClick={() => {
                          setActiveGroup(gi);
                          setActiveType(dt.id);
                        }}
                        className="relative w-full text-left px-3.5 rounded-xl text-sm transition-all duration-200 ease-out hover:scale-[1.02] h-9 grid items-center"
                        style={{
                          background: isActive ? "#0A1F44" : "#FFFFFF",
                          color: isActive ? "#FFFFFF" : "#6B7280",
                          border: isActive
                            ? "1px solid #0A1F44"
                            : "1px solid transparent",
                          fontWeight: isActive ? "600" : "400",
                        }}
                      >
                        {isActive && (
                          <span
                            className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full admin-fade-in"
                            style={{ background: "#FFFFFF" }}
                          />
                        )}
                        <span className={isActive ? "pl-1.5" : ""}>
                          {dt.label}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* ── Content panel ── */}
          <div className="min-w-0">
            {/* Tab header */}
            <div
              className="rounded-2xl px-6 py-5 mb-5"
              style={{
                background: "linear-gradient(135deg, #FFFFFF, #F5F1E8)",
                border: "1px solid rgba(226,232,240,0.8)",
              }}
            >
              <div className="grid grid-flow-col items-center gap-3 justify-start">
                <div
                  className="w-9 h-9 rounded-xl grid place-items-center"
                  style={{
                    background: "rgba(10,31,68,0.12)",
                    border: "1px solid rgba(10,31,68,0.25)",
                  }}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="#0A1F44"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.8"
                      d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                    />
                  </svg>
                </div>
                <div>
                  <h2
                    className="text-lg font-bold"
                    style={{ color: "#0A1F44" }}
                  >
                    {currentType.label}
                  </h2>
                  <p className="text-sm" style={{ color: "#6B7280" }}>
                    Template · Tiêu chí · Hướng dẫn AI
                  </p>
                </div>
              </div>
            </div>

            {/* Editor — key triggers re-mount + animation */}
            <div key={activeType} className="admin-tab-enter">
              <AdminErrorBoundary onReset={() => {}}>
                <TemplateEditor
                  docTypeId={activeType}
                  label={currentType.label}
                  token={token!}
                />
              </AdminErrorBoundary>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
