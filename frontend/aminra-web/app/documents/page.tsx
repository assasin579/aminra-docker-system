'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

interface DocumentItem {
  id: string;
  original_filename: string;
  doc_type: string | null;
  doc_type_label: string | null;
  compliance_score: number | null;
  overall_status: string | null;
  file_size: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string;
  revision_count?: number | null;
}

interface RevisionItem {
  id: string;
  original_filename: string;
  compliance_score: number | null;
  overall_status: string | null;
  file_size: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string;
}

interface RevisionListResponse {
  doc_type: string;
  doc_type_label: string | null;
  revisions: RevisionItem[];
  total: number;
}

const STATUS_CONFIG: Record<string, { label: string; bg: string; color: string; glow: string }> = {
  compliant:     { label: 'Đạt chuẩn',   bg: 'rgba(34,197,94,0.12)',  color: '#4ade80', glow: '0 0 12px rgba(34,197,94,0.3)' },
  needs_review:  { label: 'Cần xem xét', bg: 'rgba(245,158,11,0.12)', color: '#fbbf24', glow: '0 0 12px rgba(245,158,11,0.3)' },
  non_compliant: { label: 'Không đạt',   bg: 'rgba(239,68,68,0.12)',  color: '#f87171', glow: '0 0 12px rgba(239,68,68,0.3)' },
};

function scoreColor(s: number | null) {
  if (s === null) return '#475569';
  if (s >= 75) return '#4ade80';
  if (s >= 50) return '#fbbf24';
  return '#f87171';
}

function formatSize(bytes: number | null) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86400000);
  if (d === 0) return 'Hôm nay';
  if (d === 1) return 'Hôm qua';
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

function MiniScore({ score }: { score: number | null }) {
  if (score === null) return <span className="text-sm" style={{ color: '#334155' }}>—</span>;
  const pct = Math.min(score, 100);
  const color = scoreColor(score);
  return (
    <div className="relative w-12 h-12 flex-shrink-0">
      <svg viewBox="0 0 40 40" className="w-full h-full -rotate-90">
        <circle cx="20" cy="20" r="16" fill="none" stroke="#1e3a5f" strokeWidth="3" />
        <circle cx="20" cy="20" r="16" fill="none" stroke={color} strokeWidth="3"
          strokeLinecap="round" strokeDasharray={`${pct * 1.005} 100.5`}
          style={{ transition: 'stroke-dasharray 0.6s ease' }} />
      </svg>
      <span className="absolute inset-0 grid place-items-center text-xs font-bold" style={{ color }}>
        {score}
      </span>
    </div>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [fetching, setFetching] = useState(false);

  const [filterStatus, setFilterStatus] = useState('');
  const filterType = '';

  const [removeId, setRemoveId] = useState<string | null>(null);
  const [evalDetail, setEvalDetail] = useState<any | null>(null);
  const [loadingEval, setLoadingEval] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<RevisionListResponse | null>(null);
  const [loadingHistory, setLoadingHistory] = useState<string | null>(null);
  const [promotingId, setPromotingId] = useState<string | null>(null);

  // Submit to provider
  const [showSubmit, setShowSubmit] = useState(false);
  const [providers, setProviders] = useState<Array<{ id: string; company_name: string; email: string }>>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [submitNotes, setSubmitNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const PAGE_SIZE = 15;

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.replace('/business/login');
    } else if (!loading && isAuthenticated && user?.role !== 'business') {
      router.replace(user?.role === 'provider' ? '/dashboard/provider' : '/');
    }
  }, [loading, isAuthenticated, user, router]);

  const fetchDocs = useCallback(async (p = 1) => {
    if (!token) return;
    setFetching(true);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) });
      if (filterType)   params.set('doc_type', filterType);
      if (filterStatus) params.set('status', filterStatus);
      const res = await fetch(`/api/api/documents?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setDocs(data.documents);
        setTotal(data.total);
        setPage(p);
      }
    } finally {
      setFetching(false);
    }
  }, [token, filterType, filterStatus]);

  useEffect(() => { if (isAuthenticated) fetchDocs(1); }, [isAuthenticated, fetchDocs]);

  const openEval = async (id: string) => {
    setLoadingEval(id);
    try {
      const res = await fetch(`/api/api/documents/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        if (!data.extracted_text && data.evaluation_result?.extracted_text) {
          data.extracted_text = data.evaluation_result.extracted_text;
        }
        // Merge criteria_scores from evaluation_result
        if (data.evaluation_result?.criteria_scores) {
          data.criteria_scores = data.evaluation_result.criteria_scores;
        }
        if (data.evaluation_result?.signature_detection) {
          data.signature_detection = data.evaluation_result.signature_detection;
        }
        setEvalDetail(data);
      }
    } finally {
      setLoadingEval(null);
    }
  };

  const openView = (id: string) => {
    window.open(`/api/api/documents/${id}/preview?token=${encodeURIComponent(token || '')}`, '_blank');
  };

  const openHistory = async (docType: string) => {
    setLoadingHistory(docType);
    try {
      const res = await fetch(`/api/api/documents/revisions/${encodeURIComponent(docType)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setHistoryData(await res.json());
    } finally { setLoadingHistory(null); }
  };

  const handlePromote = async (id: string, docType: string) => {
    if (!confirm('Chọn phiên bản này làm tài liệu chính thức? Phiên bản này sẽ thay thế version hiện tại.')) return;
    setPromotingId(id);
    try {
      const res = await fetch(`/api/api/documents/${id}/promote`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        // Refresh history and doc list
        await openHistory(docType);
        fetchDocs(page);
      }
    } finally {
      setPromotingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Xác nhận xoá tài liệu này?')) return;
    setRemoveId(id);
    try {
      await fetch(`/api/api/documents/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      fetchDocs(page);
    } finally { setRemoveId(null); }
  };

  const openSubmitModal = async () => {
    try {
      const res = await fetch('/api/api/submissions/providers', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setProviders(d.providers || []);
      }
    } catch {}
    setSelectedDocs(new Set(docs.map(d => d.id)));
    setShowSubmit(true);
  };

  const handleSubmit = async () => {
    if (!selectedProvider || selectedDocs.size === 0) return;
    setSubmitting(true);
    try {
      const res = await fetch('/api/api/submissions/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          provider_id: selectedProvider,
          document_ids: Array.from(selectedDocs),
          notes: submitNotes,
        }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Gửi thất bại'); }
      const d = await res.json();
      alert(d.message);
      setShowSubmit(false);
      setSubmitNotes('');
    } catch (e: any) { alert(e.message); }
    finally { setSubmitting(false); }
  };

  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="text-slate-400 text-sm">Đang tải...</div>
    </div>
  );

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Stats
  const compliantCount = docs.filter(d => d.overall_status === 'compliant').length;
  const reviewCount = docs.filter(d => d.overall_status === 'needs_review').length;
  const failCount = docs.filter(d => d.overall_status === 'non_compliant').length;

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden">
      {/* ── Header ── */}
      <div className="rounded-2xl p-6 mb-6"
        style={{ background: 'linear-gradient(135deg, #0f2236 0%, #162847 50%, #0d1f35 100%)', border: '1px solid #1e3a5f' }}>
        <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
          <div>
            <div className="grid grid-flow-col items-center gap-3 justify-start mb-2">
              <div className="w-10 h-10 rounded-xl grid place-items-center"
                style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}>
                <svg className="w-5 h-5" style={{ color: '#818cf8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Tài liệu</h1>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {docs.length > 0 && (
              <button onClick={openSubmitModal}
                className="grid items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(37,99,235,0.15)', color: '#60a5fa', border: '1px solid rgba(37,99,235,0.3)' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Gửi hồ sơ
              </button>
            )}
            <Link href="/upload"
              className="grid items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105 active:scale-95"
              style={{ gridTemplateColumns: 'auto 1fr', background: 'linear-gradient(135deg, #15803d, #16a34a)', boxShadow: '0 4px 15px rgba(22,163,74,0.3)' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
              </svg>
              Upload tài liệu
            </Link>
          </div>
        </div>
      </div>

      {/* ── Filter ── */}
      <div className="mb-5">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="text-sm px-4 py-2.5 rounded-xl text-slate-300 outline-none transition-all"
          style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
          <option value="">Tất cả trạng thái</option>
          <option value="compliant">Đạt chuẩn</option>
          <option value="needs_review">Cần xem xét</option>
          <option value="non_compliant">Không đạt</option>
        </select>
      </div>

      {/* ── Document cards ── */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="rounded-2xl h-24 animate-pulse"
                style={{ background: '#162847', opacity: 1 - i * 0.2 }} />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="rounded-2xl p-16 text-center"
            style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <svg className="w-16 h-16 mx-auto mb-4" style={{ color: '#1e3a5f' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-white font-semibold mb-2">Chưa có tài liệu nào</p>
            <p className="text-sm mb-5" style={{ color: '#475569' }}>Upload tài liệu đầu tiên để bắt đầu đánh giá Halal</p>
            <Link href="/upload"
              className="inline-grid items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
              style={{ gridTemplateColumns: 'auto 1fr', background: '#16a34a' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Upload tài liệu
            </Link>
          </div>
        ) : (
          docs.map((doc, i) => {
            const st = STATUS_CONFIG[doc.overall_status || ''];
            return (
              <div key={doc.id}
                className="rounded-2xl p-5 transition-colors duration-200 doc-card-hover"
                style={{
                  background: 'linear-gradient(135deg, #162847, #0f2236)',
                  border: '1px solid #1e3a5f',
                }}>
                {/* Row 1: score + doc type + status + actions */}
                <div className="grid items-center gap-4" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                  <MiniScore score={doc.compliance_score} />

                  <div className="min-w-0">
                    {/* Doc type + status badges */}
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <span className="px-3 py-1 rounded-lg text-xs font-bold"
                        style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.25)' }}>
                        {doc.doc_type_label || 'Chưa phân loại'}
                      </span>
                      {st && (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.bg, color: st.color, boxShadow: st.glow }}>
                          {st.label}
                        </span>
                      )}
                    </div>
                    {/* Filename */}
                    <h3 className="text-sm font-semibold text-white truncate" title={doc.original_filename}>
                      {doc.original_filename}
                    </h3>
                    {/* Meta */}
                    <p className="text-sm mt-1" style={{ color: '#475569' }}>
                      {formatSize(doc.file_size)} · {new Date(doc.uploaded_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>

                  {/* Actions — compact icon buttons */}
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button onClick={() => openEval(doc.id)} title="Kết quả đánh giá"
                      disabled={loadingEval === doc.id}
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}>
                      {loadingEval === doc.id ? (
                        <svg className="w-4 h-4 animate-spin" style={{ color: '#fbbf24' }} fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" style={{ color: '#fbbf24' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      )}
                    </button>
                    <button onClick={() => openView(doc.id)} title="Xem file gốc"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
                      <svg className="w-4 h-4" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    </button>
                    <a href={`/api/api/documents/${doc.id}/file?token=${encodeURIComponent(token || '')}`}
                      download onClick={e => e.stopPropagation()} title="Tải xuống"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>
                      <svg className="w-4 h-4" style={{ color: '#4ade80' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </a>
                    {doc.doc_type && (doc.revision_count ?? 0) > 1 && (
                      <button onClick={() => openHistory(doc.doc_type!)} title="Lịch sử"
                        disabled={loadingHistory === doc.doc_type}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.2)' }}>
                        <svg className="w-4 h-4" style={{ color: '#a78bfa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </button>
                    )}
                    {user.is_owner && (
                      <button onClick={() => handleDelete(doc.id)} title="Xoá"
                        disabled={removeId === doc.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                        {removeId === doc.id ? (
                          <svg className="w-4 h-4 animate-spin" style={{ color: '#64748b' }} fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" style={{ color: '#64748b' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div className="grid grid-flow-col items-center gap-3 mt-5 justify-center flex-shrink-0">
          <button disabled={page === 1} onClick={() => fetchDocs(page - 1)}
            className="px-4 py-2 rounded-xl text-sm transition-all hover:scale-105 disabled:opacity-30"
            style={{ background: '#162847', border: '1px solid #1e3a5f', color: '#94a3b8' }}>
            ← Trước
          </button>
          <span className="text-sm px-3" style={{ color: '#64748b' }}>
            Trang <strong className="text-white">{page}</strong> / {totalPages}
          </span>
          <button disabled={page === totalPages} onClick={() => fetchDocs(page + 1)}
            className="px-4 py-2 rounded-xl text-sm transition-all hover:scale-105 disabled:opacity-30"
            style={{ background: '#162847', border: '1px solid #1e3a5f', color: '#94a3b8' }}>
            Sau →
          </button>
        </div>
      )}

      {/* ── Evaluation Detail Modal ── */}
      {evalDetail && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-3xl rounded-2xl flex flex-col"
            style={{ background: '#111725', border: '1px solid #1e3a5f', maxHeight: 'calc(100vh - 4rem)', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>

            {/* Header */}
            <div className="px-6 py-5 flex-shrink-0"
              style={{ borderBottom: '1px solid #1e3a5f', background: 'linear-gradient(135deg, #0f2236, #162847)' }}>
              <div className="grid items-center gap-4" style={{ gridTemplateColumns: '1fr auto' }}>
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="px-3 py-1 rounded-lg text-xs font-bold"
                      style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.25)' }}>
                      {evalDetail.doc_type_label || evalDetail.doc_type}
                    </span>
                    {(() => {
                      const st = STATUS_CONFIG[evalDetail.overall_status || ''];
                      return st ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.bg, color: st.color }}>{st.label}</span>
                      ) : null;
                    })()}
                  </div>
                  <h2 className="text-base font-bold text-white">{evalDetail.original_filename}</h2>
                </div>
                <div className="flex items-center gap-4">
                  {/* Big score */}
                  <div className="text-center">
                    <div className="text-3xl font-bold" style={{ color: scoreColor(evalDetail.compliance_score) }}>
                      {evalDetail.compliance_score ?? '—'}
                    </div>
                    <div className="text-xs" style={{ color: '#475569' }}>điểm</div>
                  </div>
                  <button onClick={() => setEvalDetail(null)}
                    className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                    style={{ background: 'rgba(255,255,255,0.05)' }}>
                    <span className="text-slate-400 hover:text-white">✕</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
              {/* Summary */}
              {evalDetail.summary && (
                <div className="rounded-xl p-4" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
                  <p className="text-sm leading-relaxed" style={{ color: '#cbd5e1' }}>{evalDetail.summary}</p>
                </div>
              )}

              {/* Criteria scores */}
              {evalDetail.criteria_scores && evalDetail.criteria_scores.length > 0 && (
                <div>
                  <h3 className="text-sm font-bold text-white mb-3">Điểm theo tiêu chí</h3>
                  <div className="space-y-2">
                    {evalDetail.criteria_scores.map((cs: any, i: number) => (
                      <div key={i} className="rounded-xl p-4" style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}>
                        <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
                          <div>
                            <p className="text-sm font-medium text-white">{cs.criterion}</p>
                            {cs.reason && <p className="text-sm mt-1" style={{ color: '#64748b' }}>{cs.reason}</p>}
                          </div>
                          <div className="text-right flex-shrink-0">
                            <span className="text-lg font-bold" style={{ color: scoreColor(cs.score) }}>
                              {cs.score}
                            </span>
                            <span className="text-sm" style={{ color: '#475569' }}>/{cs.weight}</span>
                          </div>
                        </div>
                        {/* Progress bar */}
                        <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: '#1e3a5f' }}>
                          <div className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${cs.weight > 0 ? (cs.score / cs.weight) * 100 : 0}%`, background: scoreColor(cs.score) }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Issues */}
              {evalDetail.issues && evalDetail.issues.length > 0 && (
                <div>
                  <h3 className="text-sm font-bold text-white mb-3">Vấn đề phát hiện ({evalDetail.issues.length})</h3>
                  <div className="space-y-2">
                    {evalDetail.issues.map((issue: any, i: number) => (
                      <div key={i} className="rounded-xl p-4" style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-xs font-bold px-2 py-0.5 rounded"
                            style={{
                              color: issue.severity === 'critical' ? '#f87171' : issue.severity === 'major' ? '#fbbf24' : '#94a3b8',
                              background: issue.severity === 'critical' ? 'rgba(239,68,68,0.12)' : issue.severity === 'major' ? 'rgba(245,158,11,0.12)' : 'rgba(148,163,184,0.12)',
                            }}>
                            {issue.severity?.toUpperCase()}
                          </span>
                          <span className="text-sm" style={{ color: '#64748b' }}>{issue.section}</span>
                        </div>
                        <p className="text-sm" style={{ color: '#cbd5e1' }}>{issue.issue}</p>
                        {issue.recommendation && (
                          <p className="text-sm mt-1.5" style={{ color: '#4ade80' }}>→ {issue.recommendation}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Strengths */}
              {evalDetail.strengths && evalDetail.strengths.length > 0 && (
                <div>
                  <h3 className="text-sm font-bold text-white mb-3">Điểm mạnh</h3>
                  <div className="space-y-1.5">
                    {evalDetail.strengths.map((s: string, i: number) => (
                      <div key={i} className="grid gap-2 text-sm" style={{ gridTemplateColumns: 'auto 1fr', color: '#94a3b8' }}>
                        <span style={{ color: '#4ade80' }}>✓</span>{s}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {evalDetail.recommendations && evalDetail.recommendations.length > 0 && (
                <div>
                  <h3 className="text-sm font-bold text-white mb-3">Đề xuất cải thiện</h3>
                  <div className="space-y-1.5">
                    {evalDetail.recommendations.map((r: string, i: number) => (
                      <div key={i} className="grid gap-2 text-sm" style={{ gridTemplateColumns: 'auto 1fr', color: '#94a3b8' }}>
                        <span style={{ color: '#fbbf24' }}>→</span>{r}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Signature */}
              {evalDetail.signature_detection && (
                <div>
                  <h3 className="text-sm font-bold text-white mb-3">Chữ ký & Con dấu</h3>
                  <div className="rounded-xl p-4" style={{
                    background: '#0f1e35', border: '1px solid #1e3a5f',
                    borderLeftWidth: 3,
                    borderLeftColor: evalDetail.signature_detection.signature_status === 'confirmed' ? '#4ade80'
                      : evalDetail.signature_detection.signature_status === 'likely' ? '#60a5fa'
                      : evalDetail.signature_detection.signature_status === 'placeholder' ? '#f87171' : '#334155',
                  }}>
                    <p className="text-sm" style={{ color: '#cbd5e1' }}>{evalDetail.signature_detection.summary}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── History Modal ── */}
      {historyData && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-2xl rounded-2xl flex flex-col"
            style={{ background: '#111725', border: '1px solid #1e3a5f', maxHeight: 'calc(100vh - 4rem)', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>

            <div className="px-6 py-5 flex-shrink-0" style={{ borderBottom: '1px solid #1e3a5f', background: 'linear-gradient(135deg, #0f2236, #162847)' }}>
              <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
                <div>
                  <h2 className="text-base font-bold text-white">Lịch sử — {historyData.doc_type_label || historyData.doc_type}</h2>
                  <p className="text-sm mt-1" style={{ color: '#475569' }}>{historyData.total} phiên bản</p>
                </div>
                <button onClick={() => setHistoryData(null)}
                  className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                  style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <span className="text-slate-400 hover:text-white">✕</span>
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto">
              {historyData.revisions.map((rev, i) => {
                const st = STATUS_CONFIG[rev.overall_status || ''];
                const isLatest = i === 0;
                return (
                  <div key={rev.id}
                    className="px-6 py-4 transition-all hover:bg-white/[0.02]"
                    style={{ borderBottom: '1px solid #1e3a5f' }}>
                    <div className="grid items-center gap-4" style={{ gridTemplateColumns: 'auto auto 1fr auto auto' }}>
                      {/* Version number */}
                      <div className="w-8 h-8 rounded-lg grid place-items-center text-xs font-bold flex-shrink-0"
                        style={{
                          background: isLatest ? 'rgba(34,197,94,0.15)' : 'rgba(100,116,139,0.1)',
                          color: isLatest ? '#4ade80' : '#64748b',
                          border: isLatest ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(100,116,139,0.2)',
                        }}>
                        v{historyData.total - i}
                      </div>
                      <MiniScore score={rev.compliance_score} />
                      <div>
                        <div className="grid grid-flow-col items-center gap-2 justify-start">
                          <p className="text-sm font-medium text-white">{rev.original_filename}</p>
                          {isLatest && (
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                              style={{ background: 'rgba(34,197,94,0.15)', color: '#4ade80' }}>
                              Hiện tại
                            </span>
                          )}
                        </div>
                        <div className="grid grid-flow-col items-center gap-2 mt-1 justify-start text-sm" style={{ color: '#475569' }}>
                          <span>{new Date(rev.uploaded_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                          <span>·</span>
                          <span>{formatSize(rev.file_size)}</span>
                        </div>
                      </div>
                      {st && (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-medium"
                          style={{ background: st.bg, color: st.color }}>
                          {st.label}
                        </span>
                      )}
                      <div className="grid grid-flow-col gap-2">
                        <button
                          onClick={() => openView(rev.id)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                          style={{ background: 'rgba(37,99,235,0.1)', color: '#60a5fa', border: '1px solid rgba(37,99,235,0.2)' }}>
                          Xem
                        </button>
                        {!isLatest && (
                          <button
                            onClick={() => handlePromote(rev.id, historyData.doc_type)}
                            disabled={promotingId === rev.id}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
                            style={{ background: 'rgba(245,158,11,0.1)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.2)' }}>
                            {promotingId === rev.id ? '...' : 'Lựa chọn'}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Submit Modal ── */}
      {showSubmit && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-lg rounded-2xl flex flex-col"
            style={{ background: '#111725', border: '1px solid #1e3a5f', maxHeight: 'calc(100vh - 4rem)', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>
            <div className="px-6 py-5 flex-shrink-0"
              style={{ borderBottom: '1px solid #1e3a5f', background: 'linear-gradient(135deg, #0f2236, #162847)' }}>
              <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
                <div>
                  <h2 className="text-base font-bold text-white">Gửi hồ sơ đến tổ chức chứng nhận</h2>
                  <p className="text-sm mt-1" style={{ color: '#64748b' }}>Chọn tổ chức và tài liệu cần gửi</p>
                </div>
                <button onClick={() => setShowSubmit(false)}
                  className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: 'rgba(255,255,255,0.05)' }}>
                  <span className="text-slate-400 hover:text-white">✕</span>
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5">
              {/* Provider select */}
              <div>
                <label className="text-xs font-medium mb-1.5 block" style={{ color: '#94a3b8' }}>Tổ chức chứng nhận *</label>
                {providers.length === 0 ? (
                  <p className="text-sm" style={{ color: '#475569' }}>Chưa có tổ chức nào trong hệ thống</p>
                ) : (
                  <div className="space-y-2">
                    {providers.map(p => (
                      <button key={p.id} onClick={() => setSelectedProvider(p.id)}
                        className="w-full grid items-center gap-3 px-4 py-3 rounded-xl text-left transition-all"
                        style={{
                          gridTemplateColumns: 'auto 1fr',
                          background: selectedProvider === p.id ? 'rgba(37,99,235,0.12)' : '#0f1e35',
                          border: `1px solid ${selectedProvider === p.id ? 'rgba(37,99,235,0.4)' : '#1e3a5f'}`,
                        }}>
                        <div className="w-8 h-8 rounded-lg grid place-items-center"
                          style={{ background: 'rgba(37,99,235,0.15)', color: '#60a5fa' }}>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                          </svg>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-white">{p.company_name}</p>
                          <p className="text-xs" style={{ color: '#475569' }}>{p.email}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Document selection */}
              <div>
                <label className="text-xs font-medium mb-1.5 block" style={{ color: '#94a3b8' }}>
                  Tài liệu gửi ({selectedDocs.size}/{docs.length})
                </label>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {docs.map(doc => (
                    <label key={doc.id} className="grid items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all"
                      style={{
                        gridTemplateColumns: 'auto 1fr auto',
                        background: selectedDocs.has(doc.id) ? 'rgba(34,197,94,0.08)' : '#0f1e35',
                        border: `1px solid ${selectedDocs.has(doc.id) ? 'rgba(34,197,94,0.25)' : '#1e3a5f'}`,
                      }}>
                      <input type="checkbox" checked={selectedDocs.has(doc.id)}
                        onChange={e => {
                          const next = new Set(selectedDocs);
                          e.target.checked ? next.add(doc.id) : next.delete(doc.id);
                          setSelectedDocs(next);
                        }} className="rounded" />
                      <span className="text-sm text-white truncate">{doc.original_filename}</span>
                      <span className="text-xs" style={{ color: '#475569' }}>{doc.doc_type_label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="text-xs font-medium mb-1.5 block" style={{ color: '#94a3b8' }}>Ghi chú (tuỳ chọn)</label>
                <textarea value={submitNotes} onChange={e => setSubmitNotes(e.target.value)}
                  placeholder="Thông tin thêm cho tổ chức chứng nhận..."
                  rows={3}
                  className="w-full px-4 py-3 rounded-xl text-sm text-white outline-none resize-none"
                  style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
              </div>
            </div>

            <div className="px-6 py-4 flex-shrink-0" style={{ borderTop: '1px solid #1e3a5f' }}>
              <button onClick={handleSubmit}
                disabled={submitting || !selectedProvider || selectedDocs.size === 0}
                className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all"
                style={{
                  background: (!selectedProvider || selectedDocs.size === 0) ? '#1e3a5f' : 'linear-gradient(135deg, #1d4ed8, #2563eb)',
                  boxShadow: selectedProvider && selectedDocs.size > 0 ? '0 4px 15px rgba(37,99,235,0.3)' : 'none',
                }}>
                {submitting ? 'Đang gửi...' : `Gửi ${selectedDocs.size} tài liệu`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
