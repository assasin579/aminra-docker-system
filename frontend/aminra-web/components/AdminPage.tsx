'use client';

import { useState, useEffect, useCallback, useRef, Component, type ReactNode } from 'react';
import { useAdminAuth } from '@/components/AdminAuthContext';
import AdminLoginModal from '@/components/AdminLoginModal';
import AdminUserManager from '@/components/AdminUserManager';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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
        <div className="rounded-xl p-6 m-4" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)' }}>
          <h3 className="text-sm font-bold mb-2" style={{ color: '#f87171' }}>Lỗi hiển thị</h3>
          <pre className="text-xs mb-3 overflow-auto max-h-32" style={{ color: '#fca5a5' }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => { this.setState({ error: null }); this.props.onReset?.(); }}
            className="text-xs px-3 py-1.5 rounded-lg"
            style={{ background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)' }}>
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
    group: 'Tài liệu chính sách',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    types: [
      { id: 'halal_policy',             label: 'Halal Policy' },
      { id: 'has_manual',               label: 'HAS Manual' },
      { id: 'halal_manual',             label: 'Halal Manual' },
      { id: 'internal_halal_committee', label: 'Internal Halal Committee' },
      { id: 'company_profile',          label: 'Company Profile' },
    ],
  },
  {
    group: 'Tài liệu kỹ thuật',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    types: [
      { id: 'ingredient_raw_material', label: 'Ingredient & Raw Material' },
      { id: 'process_flow_chart',      label: 'Process Flow Chart' },
    ],
  },
  {
    group: 'SOP Documentation',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
    types: [
      { id: 'sop_raw_material_receiving',   label: 'Raw Material Receiving' },
      { id: 'sop_storage_segregation',      label: 'Storage & Segregation' },
      { id: 'sop_production_operation',     label: 'Production Operation' },
      { id: 'sop_cleaning_sanitation',      label: 'Cleaning & Sanitation' },
      { id: 'sop_handling_nonconformances', label: 'Handling Non-Conformances' },
      { id: 'sop_complaint_recall',         label: 'Complaint & Recall' },
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

interface DocxMetaItem { key: string; value: string }
interface DocxCustomSection { title: string; content: string }
interface DocxConfig {
  cover_meta:          DocxMetaItem[];
  confidential_label:  string;
  show_toc:            boolean;
  show_revision_table: boolean;
  show_approval_block: boolean;
  custom_sections:     DocxCustomSection[];
}

const DEFAULT_DOCX_CONFIG: DocxConfig = {
  cover_meta: [], confidential_label: 'TÀI LIỆU NỘI BỘ',
  show_toc: false, show_revision_table: true, show_approval_block: true,
  custom_sections: [],
};

interface Template {
  doc_type:            string;
  label:               string;
  mandatory_criteria:  Criterion[];
  evaluation_guidance: string;
  docx_config?:        DocxConfig;
  updated_at:          string;
}

interface TemplateFile {
  name: string;
  size: number;
  uploaded_at: string;
}

interface Revision {
  action: 'upload' | 'delete';
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

function CriterionRow({ c, idx, onChange, onDelete }: {
  c: Criterion; idx: number;
  onChange: (updated: Criterion) => void;
  onDelete: () => void;
}) {
  return (
    <div
      className="admin-row-appear rounded-2xl p-5 space-y-3 group transition-all duration-200"
      style={{
        background: 'linear-gradient(135deg, rgba(15,30,53,0.9) 0%, rgba(10,25,45,0.9) 100%)',
        border: '1px solid rgba(30,58,95,0.8)',
        animationDelay: `${idx * 40}ms`,
        animationFillMode: 'both',
      }}
    >
      <div className="grid gap-4 items-start" style={{ gridTemplateColumns: '1.75rem 1fr auto' }}>
        {/* Index badge */}
        <div className="w-7 h-7 rounded-lg grid place-items-center text-xs font-bold mt-0.5"
          style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa', border: '1px solid rgba(59,130,246,0.25)' }}>
          {idx + 1}
        </div>

        <div className="space-y-2.5">
          <input
            value={c.name}
            onChange={e => onChange({ ...c, name: e.target.value })}
            placeholder="Tên tiêu chí (vd: Chứng nhận Halal nhà cung cấp)"
            className="admin-input w-full px-4 py-2.5 rounded-xl text-sm text-white transition-all duration-200"
            style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
          />
          <textarea
            value={c.description}
            onChange={e => onChange({ ...c, description: e.target.value })}
            placeholder="Mô tả tiêu chí và cách đánh giá…"
            rows={2}
            className="admin-textarea w-full px-4 py-2.5 rounded-xl text-sm text-white transition-all duration-200 resize-none"
            style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
          />
        </div>

        {/* Weight + delete */}
        <div className="grid items-center gap-2 justify-items-center">
          <label className="text-xs font-medium" style={{ color: '#64748b' }}>Điểm</label>
          <input
            type="number" min={1} max={100}
            value={c.weight}
            onChange={e => onChange({ ...c, weight: Number(e.target.value) })}
            className="admin-input w-16 px-2 py-2 rounded-xl text-sm text-center font-bold text-white transition-all duration-200"
            style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)', color: '#60a5fa' }}
          />
          <button
            onClick={onDelete}
            className="p-2 rounded-xl transition-all duration-200 hover:scale-110"
            style={{ color: '#ef4444', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}
            title="Xoá tiêu chí"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Template editor ──────────────────────────────────────────────────────────

function TemplateEditor({ docTypeId, label, token }: { docTypeId: string; label: string; token: string }) {
  const [template, setTemplate]         = useState<Template | null>(null);
  const [saving, setSaving]             = useState(false);
  const [saved, setSaved]               = useState(false);
  const [loading, setLoading]           = useState(true);
  const [files, setFiles]               = useState<TemplateFile[]>([]);
  const [uploading, setUploading]       = useState(false);
  const [uploadError, setUploadError]   = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [dragOver, setDragOver]         = useState(false);
  const [revisions, setRevisions]       = useState<Revision[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadFiles = useCallback(() => {
    fetch(`${API}/admin/templates/${docTypeId}/files`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => setFiles(d.files ?? []))
      .catch(() => {});
  }, [docTypeId, token]);

  const loadRevisions = useCallback(() => {
    fetch(`${API}/admin/templates/${docTypeId}/revisions`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => setRevisions(d.revisions ?? []))
      .catch(() => {});
  }, [docTypeId, token]);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API}/admin/templates/${docTypeId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setTemplate(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [docTypeId, token]);

  useEffect(() => { load(); loadFiles(); loadRevisions(); }, [load, loadFiles, loadRevisions]);

  const uploadFile = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API}/admin/templates/${docTypeId}/files`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      loadFiles();
      loadRevisions();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload thất bại');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
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
      await fetch(`${API}/admin/templates/${docTypeId}/files/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      loadFiles();
      loadRevisions();
    } finally {
      setDeletingFile(null);
    }
  };

  const addCriterion = () => {
    if (!template) return;
    setTemplate({
      ...template,
      mandatory_criteria: [...(template.mandatory_criteria ?? []), { id: `c_${Date.now()}`, name: '', description: '', weight: 10 }],
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
    setTemplate({ ...template, mandatory_criteria: (template.mandatory_criteria ?? []).filter((_, i) => i !== idx) });
  };

  const save = async () => {
    if (!template) return;
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API}/admin/templates/${docTypeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(template),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="admin-shimmer rounded-2xl h-16" style={{ opacity: 1 - i * 0.15 }} />
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

      {/* ── Reference files ── */}
      <div className="rounded-2xl overflow-hidden"
        style={{ border: '1px solid rgba(30,58,95,0.8)', background: 'rgba(10,20,40,0.6)' }}>

        <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(30,58,95,0.6)' }}>
          <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="grid grid-flow-col items-center gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.25)' }}>
                <svg className="w-4 h-4" fill="none" stroke="#60a5fa" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Tài liệu mẫu tham chiếu</h3>
                <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
                  AI chỉ dùng các file này để đánh giá — không dùng kiến thức bên ngoài
                </p>
              </div>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 hover:scale-105 active:scale-95"
              style={{
                gridTemplateColumns: 'auto 1fr',
                background: uploading ? 'rgba(30,58,95,0.5)' : 'rgba(59,130,246,0.15)',
                color: uploading ? '#475569' : '#60a5fa',
                border: '1px solid rgba(59,130,246,0.3)',
              }}
            >
              {uploading ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              )}
              {uploading ? 'Đang upload…' : 'Upload file mẫu'}
            </button>
            <input ref={fileInputRef} type="file" accept=".pdf,.pptx,.ppt,.docx,.txt,.md"
              className="hidden" onChange={handleFileUpload} />
          </div>
        </div>

        {/* Drop zone */}
        <div
          className="mx-5 my-4 rounded-xl transition-all duration-200 cursor-pointer"
          style={{
            border: dragOver ? '2px dashed rgba(59,130,246,0.6)' : '2px dashed rgba(30,58,95,0.6)',
            background: dragOver ? 'rgba(59,130,246,0.06)' : 'transparent',
            transform: dragOver ? 'scale(1.01)' : 'scale(1)',
          }}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          {files.length === 0 ? (
            <div className="grid place-items-center py-8 gap-2">
              <svg className="w-8 h-8" fill="none" stroke="#475569" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="text-sm font-medium" style={{ color: '#64748b' }}>
                Kéo thả hoặc nhấn để upload
              </p>
              <p className="text-xs" style={{ color: '#334155' }}>PDF, DOCX, PPTX, TXT, MD</p>
            </div>
          ) : (
            <div className="p-3 space-y-2">
              {files.map(f => (
                <div key={f.name}
                  className="grid items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group/file"
                  style={{ gridTemplateColumns: 'auto 1fr auto', background: 'rgba(15,30,53,0.8)', border: '1px solid rgba(30,58,95,0.6)' }}
                  onClick={e => e.stopPropagation()}
                >
                  <div className="w-8 h-8 rounded-lg grid place-items-center"
                    style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>
                    <svg className="w-4 h-4" fill="none" stroke="#4ade80" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">{f.name}</p>
                    <p className="text-xs mt-0.5" style={{ color: '#475569' }}>{formatBytes(f.size)}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteFile(f.name)}
                    disabled={deletingFile === f.name}
                    className="p-2 rounded-lg transition-all duration-200 opacity-0 group-hover/file:opacity-100 hover:scale-110"
                    style={{ color: '#ef4444', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}
                  >
                    {deletingFile === f.name
                      ? <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg>
                      : <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    }
                  </button>
                </div>
              ))}
              {/* Add more hint */}
              <div className="grid grid-flow-col place-items-center gap-2 py-2 justify-center">
                <svg className="w-3.5 h-3.5" fill="none" stroke="#334155" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                <p className="text-xs" style={{ color: '#334155' }}>Kéo thả thêm file vào đây</p>
              </div>
            </div>
          )}
        </div>

        {uploadError && (
          <div className="mx-5 mb-4 grid items-center gap-2 px-4 py-3 rounded-xl admin-fade-in"
            style={{ gridTemplateColumns: 'auto 1fr', color: '#f87171', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm">{uploadError}</p>
          </div>
        )}
      </div>

      {/* ── Criteria list ── */}
      <div className="rounded-2xl overflow-hidden"
        style={{ border: '1px solid rgba(30,58,95,0.8)', background: 'rgba(10,20,40,0.6)' }}>

        <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(30,58,95,0.6)' }}>
          <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="grid grid-flow-col items-center gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.25)' }}>
                <svg className="w-4 h-4" fill="none" stroke="#4ade80" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Tiêu chí bắt buộc</h3>
                <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
                  {criteria.length} tiêu chí — AI dùng để chấm điểm từng mục
                </p>
              </div>
            </div>
            <button
              onClick={addCriterion}
              className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 hover:scale-105 active:scale-95"
              style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(34,197,94,0.12)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.25)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Thêm tiêu chí
            </button>
          </div>

          {/* Weight progress bar */}
          {criteria.length > 0 && (
            <div className="mt-4 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs" style={{ color: '#64748b' }}>Tổng điểm</span>
                <span className="text-xs font-bold" style={{ color: weightOk ? '#4ade80' : '#f59e0b' }}>
                  {totalWeight} / 100 {weightOk ? '✓' : '(nên = 100)'}
                </span>
              </div>
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(30,58,95,0.8)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${weightPct}%`,
                    background: weightOk
                      ? 'linear-gradient(90deg, #16a34a, #4ade80)'
                      : totalWeight > 100
                        ? 'linear-gradient(90deg, #dc2626, #f87171)'
                        : 'linear-gradient(90deg, #d97706, #fbbf24)',
                  }}
                />
              </div>
            </div>
          )}
        </div>

        <div className="p-5">
          {criteria.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(30,58,95,0.5)', border: '1px dashed rgba(30,58,95,0.8)' }}>
                <svg className="w-6 h-6" fill="none" stroke="#334155" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-sm font-medium" style={{ color: '#475569' }}>Chưa có tiêu chí nào</p>
              <p className="text-xs" style={{ color: '#334155' }}>Nhấn "+ Thêm tiêu chí" để bắt đầu</p>
            </div>
          ) : (
            <div className="space-y-3">
              {criteria.map((c, i) => (
                <CriterionRow key={c.id} c={c} idx={i}
                  onChange={updated => updateCriterion(i, updated)}
                  onDelete={() => deleteCriterion(i)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Evaluation guidance ── */}
      <div className="rounded-2xl overflow-hidden"
        style={{ border: '1px solid rgba(30,58,95,0.8)', background: 'rgba(10,20,40,0.6)' }}>
        <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(30,58,95,0.6)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: 'rgba(168,85,247,0.12)', border: '1px solid rgba(168,85,247,0.25)' }}>
              <svg className="w-4 h-4" fill="none" stroke="#c084fc" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Hướng dẫn đánh giá cho AI</h3>
              <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
                AI đọc hướng dẫn này để hiểu ngữ cảnh và cách chấm điểm
              </p>
            </div>
          </div>
        </div>
        <div className="p-5">
          <textarea
            value={template.evaluation_guidance}
            onChange={e => setTemplate({ ...template, evaluation_guidance: e.target.value })}
            placeholder="Nhập hướng dẫn đánh giá tổng quát cho loại tài liệu này. AI sẽ đọc hướng dẫn này khi chấm điểm…"
            rows={5}
            className="admin-textarea w-full px-4 py-3 rounded-xl text-sm text-white transition-all duration-200 resize-none"
            style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
          />
        </div>
      </div>

      {/* ── DOCX Template Config ── */}
      <div className="rounded-2xl overflow-hidden"
        style={{ border: '1px solid rgba(99,102,241,0.3)', background: 'rgba(10,20,40,0.6)' }}>
        <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(99,102,241,0.2)', background: 'rgba(99,102,241,0.06)' }}>
          <div className="grid grid-flow-col items-center gap-2.5 justify-start">
            <span style={{ color: '#818cf8', fontSize: 16 }}>⎙</span>
            <div>
              <h3 className="text-sm font-semibold text-white">Định dạng tài liệu DOCX</h3>
              <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
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
              cover_meta: Array.isArray(template.docx_config?.cover_meta) ? template.docx_config.cover_meta : [],
              custom_sections: Array.isArray(template.docx_config?.custom_sections) ? template.docx_config.custom_sections : [],
            };
            const update = (patch: Partial<DocxConfig>) =>
              setTemplate({ ...template, docx_config: { ...dc, ...patch } });

            return (<>
              {/* Confidential label */}
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#94a3b8' }}>
                  Nhãn phân loại tài liệu (header)
                </label>
                <input
                  value={dc.confidential_label}
                  onChange={e => update({ confidential_label: e.target.value })}
                  placeholder="TÀI LIỆU NỘI BỘ"
                  className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                  style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
                />
              </div>

              {/* Toggles */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { key: 'show_toc' as const, label: 'Mục lục (TOC)' },
                  { key: 'show_revision_table' as const, label: 'Bảng lịch sử thay đổi' },
                  { key: 'show_approval_block' as const, label: 'Bảng phê duyệt (trang bìa)' },
                ].map(opt => (
                  <label key={opt.key}
                    className="grid grid-flow-col items-center gap-2 justify-start cursor-pointer px-3 py-2.5 rounded-lg transition-all"
                    style={{
                      background: dc[opt.key] ? 'rgba(99,102,241,0.1)' : 'rgba(5,15,30,0.5)',
                      border: dc[opt.key] ? '1px solid rgba(99,102,241,0.3)' : '1px solid rgba(30,58,95,0.5)',
                    }}>
                    <input type="checkbox" checked={dc[opt.key]}
                      onChange={e => update({ [opt.key]: e.target.checked })}
                      className="rounded" />
                    <span className="text-xs" style={{ color: dc[opt.key] ? '#818cf8' : '#64748b' }}>
                      {opt.label}
                    </span>
                  </label>
                ))}
              </div>

              {/* Cover metadata */}
              <div>
                <div className="grid grid-flow-col items-center gap-2 mb-2 justify-start">
                  <span className="text-xs font-medium" style={{ color: '#94a3b8' }}>Metadata trang bìa</span>
                  <button
                    onClick={() => update({ cover_meta: [...dc.cover_meta, { key: '', value: '' }] })}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}>
                    + Thêm
                  </button>
                </div>
                <div className="space-y-2">
                  {dc.cover_meta.map((m, i) => (
                    <div key={i} className="grid gap-2 items-center" style={{ gridTemplateColumns: '1fr 1fr auto' }}>
                      <input
                        value={m.key}
                        onChange={e => {
                          const arr = [...dc.cover_meta];
                          arr[i] = { ...arr[i], key: e.target.value };
                          update({ cover_meta: arr });
                        }}
                        placeholder="Tên trường"
                        className="px-3 py-2 rounded-lg text-xs text-white outline-none"
                        style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
                      />
                      <input
                        value={m.value}
                        onChange={e => {
                          const arr = [...dc.cover_meta];
                          arr[i] = { ...arr[i], value: e.target.value };
                          update({ cover_meta: arr });
                        }}
                        placeholder="Giá trị"
                        className="px-3 py-2 rounded-lg text-xs text-white outline-none"
                        style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
                      />
                      <button
                        onClick={() => update({ cover_meta: dc.cover_meta.filter((_, j) => j !== i) })}
                        className="text-xs text-slate-600 hover:text-red-400 px-1">✕</button>
                    </div>
                  ))}
                  {dc.cover_meta.length === 0 && (
                    <p className="text-xs" style={{ color: '#334155' }}>
                      Chưa có — sẽ dùng metadata mặc định của template
                    </p>
                  )}
                </div>
              </div>

              {/* Custom sections */}
              <div>
                <div className="grid grid-flow-col items-center gap-2 mb-2 justify-start">
                  <span className="text-xs font-medium" style={{ color: '#94a3b8' }}>Phần tùy chỉnh (trước nội dung chính)</span>
                  <button
                    onClick={() => update({ custom_sections: [...dc.custom_sections, { title: '', content: '' }] })}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}>
                    + Thêm phần
                  </button>
                </div>
                <div className="space-y-3">
                  {dc.custom_sections.map((sec, i) => (
                    <div key={i} className="rounded-xl p-3 space-y-2"
                      style={{ background: 'rgba(5,15,30,0.5)', border: '1px solid rgba(30,58,95,0.5)' }}>
                      <div className="grid gap-2 items-center" style={{ gridTemplateColumns: '1fr auto' }}>
                        <input
                          value={sec.title}
                          onChange={e => {
                            const arr = [...dc.custom_sections];
                            arr[i] = { ...arr[i], title: e.target.value };
                            update({ custom_sections: arr });
                          }}
                          placeholder="Tiêu đề phần"
                          className="px-3 py-2 rounded-lg text-xs text-white outline-none font-medium"
                          style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
                        />
                        <button
                          onClick={() => update({ custom_sections: dc.custom_sections.filter((_, j) => j !== i) })}
                          className="text-xs text-slate-600 hover:text-red-400 px-1">✕</button>
                      </div>
                      <textarea
                        value={sec.content}
                        onChange={e => {
                          const arr = [...dc.custom_sections];
                          arr[i] = { ...arr[i], content: e.target.value };
                          update({ custom_sections: arr });
                        }}
                        placeholder="Nội dung (mỗi dòng = 1 đoạn, dùng - ở đầu dòng cho bullet)"
                        rows={3}
                        className="w-full px-3 py-2 rounded-lg text-xs text-white outline-none resize-none"
                        style={{ background: 'rgba(5,15,30,0.8)', border: '1px solid rgba(30,58,95,0.8)' }}
                      />
                    </div>
                  ))}
                  {dc.custom_sections.length === 0 && (
                    <p className="text-xs" style={{ color: '#334155' }}>
                      Chưa có — nội dung sẽ chỉ gồm phần AI tạo ra
                    </p>
                  )}
                </div>
              </div>
            </>);
          })()}
        </div>
      </div>

      {/* ── Save bar ── */}
      <div className="grid grid-flow-col items-center gap-4 px-1 justify-start">
        <button
          onClick={save}
          disabled={saving}
          className={`grid items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${saved ? 'admin-pulse-glow' : ''}`}
          style={{
            gridTemplateColumns: 'auto 1fr',
            background: saving ? 'rgba(22,163,74,0.4)' : saved ? '#16a34a' : 'linear-gradient(135deg, #15803d, #16a34a)',
            color: saving ? 'rgba(255,255,255,0.5)' : 'white',
            boxShadow: saved ? '0 0 20px rgba(34,197,94,0.3)' : '0 4px 12px rgba(22,163,74,0.25)',
            transform: saving ? 'scale(0.98)' : 'scale(1)',
          }}
        >
          {saving ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          ) : saved ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          )}
          {saving ? 'Đang lưu…' : saved ? 'Đã lưu thành công!' : 'Lưu template'}
        </button>

        {template.updated_at && (
          <span className="text-xs ml-auto" style={{ color: '#334155' }}>
            Cập nhật lúc {new Date(template.updated_at).toLocaleString('vi-VN')}
          </span>
        )}
      </div>

      {/* ── Revision history ── */}
      {revisions.length > 0 && (
        <div className="rounded-2xl overflow-hidden"
          style={{ border: '1px solid rgba(30,58,95,0.8)', background: 'rgba(10,20,40,0.6)' }}>
          <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(30,58,95,0.6)' }}>
            <div className="grid grid-flow-col items-center gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.25)' }}>
                <svg className="w-4 h-4" fill="none" stroke="#818cf8" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Lịch sử thay đổi</h3>
                <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
                  {revisions.length} lần thay đổi — mới nhất lên trên
                </p>
              </div>
            </div>
          </div>
          <div className="p-3 space-y-1.5 max-h-64 overflow-y-auto admin-scroll">
            {revisions.map((rev, i) => (
              <div key={i}
                className="grid items-center gap-3 px-4 py-2.5 rounded-xl"
                style={{ gridTemplateColumns: 'auto 1fr auto', background: 'rgba(15,25,45,0.7)', border: '1px solid rgba(30,58,95,0.5)' }}
              >
                {/* Action badge */}
                <div className="w-6 h-6 rounded-md grid place-items-center"
                  style={{
                    background: rev.action === 'upload' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.1)',
                    border: rev.action === 'upload' ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(239,68,68,0.2)',
                  }}>
                  {rev.action === 'upload' ? (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="#4ade80" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5"
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="#f87171" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5"
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: '#cbd5e1' }}>{rev.filename}</p>
                  <div className="grid grid-flow-col items-center gap-2 mt-0.5 justify-start">
                    <span className="text-xs font-medium"
                      style={{ color: rev.action === 'upload' ? '#4ade80' : '#f87171' }}>
                      {rev.action === 'upload' ? 'Upload' : 'Xoá'}
                    </span>
                    {rev.size != null && (
                      <span className="text-xs" style={{ color: '#334155' }}>· {formatBytes(rev.size)}</span>
                    )}
                  </div>
                </div>
                <span className="text-xs" style={{ color: '#334155' }}>
                  {new Date(rev.timestamp + 'Z').toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main admin page ──────────────────────────────────────────────────────────

export default function AdminPageClient() {
  const { isAdmin, token } = useAdminAuth();
  const [showLogin, setShowLogin]     = useState(false);
  const [activeSection, setActiveSection] = useState<'templates' | 'users'>('templates');
  const [activeGroup, setActiveGroup] = useState(0);
  const [activeType, setActiveType]   = useState(DOC_TYPE_GROUPS[0].types[0].id);

  if (!isAdmin) {
    return (
      <div className="grid place-items-center min-h-[70vh] text-center px-4">
        <div className="admin-scale-in">
          {/* Lock icon with glow */}
          <div className="relative mx-auto mb-6 w-24 h-24">
            <div className="absolute inset-0 rounded-full blur-xl opacity-30"
              style={{ background: 'radial-gradient(circle, #f59e0b, transparent)' }} />
            <div className="relative w-24 h-24 rounded-full grid place-items-center"
              style={{
                background: 'linear-gradient(135deg, rgba(245,158,11,0.15), rgba(245,158,11,0.05))',
                border: '1px solid rgba(245,158,11,0.3)',
              }}>
              <svg className="w-10 h-10" fill="none" stroke="#f59e0b" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
          </div>

          <h2 className="text-2xl font-bold text-white mb-3">Khu vực dành cho Admin</h2>
          <p className="text-base mb-8 max-w-sm mx-auto leading-relaxed" style={{ color: '#64748b' }}>
            Bạn cần đăng nhập bằng tài khoản admin để truy cập và quản lý template đánh giá.
          </p>
          <button
            onClick={() => setShowLogin(true)}
            className="inline-grid items-center gap-2 px-8 py-3.5 rounded-2xl font-semibold text-base transition-all duration-200 hover:scale-105 active:scale-95"
            style={{
              gridTemplateColumns: 'auto 1fr',
              background: 'linear-gradient(135deg, #15803d, #16a34a)',
              color: 'white',
              boxShadow: '0 4px 20px rgba(22,163,74,0.35)',
            }}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
            Đăng nhập Admin
          </button>
          {showLogin && <AdminLoginModal onClose={() => setShowLogin(false)} />}
        </div>
      </div>
    );
  }

  const currentGroup = DOC_TYPE_GROUPS[activeGroup];
  const currentType  = currentGroup.types.find(t => t.id === activeType) ?? currentGroup.types[0];

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full admin-fade-in">
      {/* ── Header ── */}
      <div className="mb-8">
        <div className="grid grid-flow-col items-center gap-3 mb-2 justify-start">
          <div className="w-10 h-10 rounded-xl grid place-items-center"
            style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.2), rgba(34,197,94,0.08))', border: '1px solid rgba(34,197,94,0.3)' }}>
            <svg className="w-5 h-5" fill="none" stroke="#4ade80" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
            <p className="text-sm" style={{ color: '#64748b' }}>
              Quản lý template và tiêu chí đánh giá Halal
            </p>
          </div>
        </div>

        {/* Section tabs */}
        <div className="grid grid-flow-col gap-2 mt-5 justify-start">
          {[
            { key: 'templates', label: 'Template đánh giá' },
            { key: 'users',     label: 'Quản lý Users' },
          ].map(tab => (
            <button key={tab.key}
              onClick={() => setActiveSection(tab.key as 'templates' | 'users')}
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all"
              style={{
                background: activeSection === tab.key ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.03)',
                color: activeSection === tab.key ? '#4ade80' : '#64748b',
                border: activeSection === tab.key ? '1px solid rgba(34,197,94,0.3)' : '1px solid #1e3a5f',
              }}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Users section ── */}
      {activeSection === 'users' && (
        <div className="rounded-2xl p-6" style={{ background: 'rgba(10,20,40,0.6)', border: '1px solid rgba(30,58,95,0.6)' }}>
          <AdminUserManager token={token!} />
        </div>
      )}

      {/* ── Templates section ── */}
      {activeSection === 'templates' && <div className="grid gap-6 flex-1 lg:min-h-0" style={{ gridTemplateColumns: '16rem 1fr' }}>
        {/* ── Sidebar ── */}
        <div className="space-y-2 admin-scroll overflow-y-auto" style={{ maxHeight: 'calc(100vh - 180px)' }}>
          {DOC_TYPE_GROUPS.map((grp, gi) => (
            <div key={gi} className="rounded-2xl overflow-hidden"
              style={{ background: 'rgba(10,20,40,0.6)', border: '1px solid rgba(30,58,95,0.6)' }}>
              {/* Group header */}
              <div className="grid grid-flow-col items-center gap-2.5 px-4 py-3 justify-start"
                style={{ borderBottom: '1px solid rgba(30,58,95,0.4)' }}>
                <span style={{ color: '#475569' }}>{grp.icon}</span>
                <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#475569' }}>
                  {grp.group}
                </p>
              </div>
              {/* Type items */}
              <div className="p-2 space-y-1">
                {grp.types.map(dt => {
                  const isActive = activeType === dt.id;
                  return (
                    <button key={dt.id}
                      onClick={() => { setActiveGroup(gi); setActiveType(dt.id); }}
                      className="relative w-full text-left px-3.5 rounded-xl text-sm transition-all duration-200 hover:scale-[1.02] h-9 grid items-center"
                      style={{
                        background: isActive ? 'rgba(34,197,94,0.12)' : 'transparent',
                        color: isActive ? '#4ade80' : '#64748b',
                        border: isActive ? '1px solid rgba(34,197,94,0.25)' : '1px solid transparent',
                        fontWeight: isActive ? '600' : '400',
                      }}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full admin-fade-in"
                          style={{ background: 'linear-gradient(180deg, #4ade80, #16a34a)' }} />
                      )}
                      <span className={isActive ? 'pl-1.5' : ''}>{dt.label}</span>
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
          <div className="rounded-2xl px-6 py-5 mb-5"
            style={{
              background: 'linear-gradient(135deg, rgba(15,30,53,0.9), rgba(10,22,42,0.9))',
              border: '1px solid rgba(30,58,95,0.8)',
            }}>
            <div className="grid grid-flow-col items-center gap-3 justify-start">
              <div className="w-9 h-9 rounded-xl grid place-items-center"
                style={{ background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.25)' }}>
                <svg className="w-4 h-4" fill="none" stroke="#4ade80" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">{currentType.label}</h2>
                <p className="text-sm" style={{ color: '#475569' }}>
                  Template · Tiêu chí · Hướng dẫn AI
                </p>
              </div>
            </div>
          </div>

          {/* Editor — key triggers re-mount + animation */}
          <div key={activeType} className="admin-tab-enter">
            <AdminErrorBoundary onReset={() => {}}>
              <TemplateEditor docTypeId={activeType} label={currentType.label} token={token!} />
            </AdminErrorBoundary>
          </div>
        </div>
      </div>}
    </div>
  );
}
