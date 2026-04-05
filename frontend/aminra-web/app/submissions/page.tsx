'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

interface Submission {
  id: string; company_name: string; status: string;
  notes: string | null; auditor_notes: string | null;
  doc_count: number; document_ids: string[];
  auditor_id: string | null; auditor_name: string | null;
  submitted_at: string; updated_at: string;
}

interface SubDoc {
  id: string; original_filename: string; doc_type: string | null;
  doc_type_label: string | null; compliance_score: number | null;
  overall_status: string | null; file_size: number | null; uploaded_at: string;
}

const STATUS_MAP: Record<string, { label: string; color: string; bg: string }> = {
  pending:   { label: 'Chờ đánh giá', color: '#fbbf24', bg: 'rgba(245,158,11,0.12)' },
  reviewing: { label: 'Đang đánh giá', color: '#60a5fa', bg: 'rgba(37,99,235,0.12)' },
  returned:  { label: 'Đã gửi lại',  color: '#f87171', bg: 'rgba(239,68,68,0.12)' },
  approved:  { label: 'Đã duyệt',    color: '#4ade80', bg: 'rgba(34,197,94,0.12)' },
};

function scoreColor(s: number | null) {
  if (s === null) return '#475569';
  if (s >= 75) return '#4ade80';
  if (s >= 50) return '#fbbf24';
  return '#f87171';
}

export default function SubmissionsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  const [subs, setSubs] = useState<Submission[]>([]);
  const [fetching, setFetching] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [subDocs, setSubDocs] = useState<SubDoc[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider'))
      router.replace(user?.role === 'business' ? '/dashboard/business' : '/provider/login');
  }, [loading, isAuthenticated, user, router]);

  const [auditors, setAuditors] = useState<Array<{ id: string; display_name: string; specialty: string | null }>>([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);

  // Fetch auditors for assignment dropdown
  useEffect(() => {
    if (!token || !isAuthenticated || user?.role !== 'provider') return;
    fetch('/api/auth/provider/auditors', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => setAuditors(d.auditors || []))
      .catch(() => {});
  }, [token, isAuthenticated, user]);

  const assignAuditor = async (subId: string, auditorId: string) => {
    setAssigningId(subId);
    try {
      await fetch(`/api/api/submissions/received/${subId}/assign`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ auditor_id: auditorId }),
      });
      fetchSubs();
    } finally { setAssigningId(null); }
  };

  const fetchSubs = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch('/api/api/submissions/received', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setSubs(d.submissions || []); }
    } finally { setFetching(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchSubs(); }, [isAuthenticated, fetchSubs]);

  const toggleExpand = async (id: string) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    setLoadingDocs(true);
    try {
      const res = await fetch(`/api/api/submissions/received/${id}/documents`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setSubDocs(d.documents || []); }
    } finally { setLoadingDocs(false); }
  };

  const updateStatus = async (id: string, status: string) => {
    setUpdatingId(id);
    try {
      await fetch(`/api/api/submissions/received/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      });
      fetchSubs();
    } finally { setUpdatingId(null); }
  };

  const viewDoc = (docId: string) => {
    window.open(`/api/api/documents/${docId}/preview?token=${encodeURIComponent(token || '')}`, '_blank');
  };

  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="text-slate-400 text-sm">Đang tải...</div>
    </div>
  );

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden">
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6"
        style={{ background: 'linear-gradient(135deg, #0f2236, #162847)', border: '1px solid #1e3a5f' }}>
        <div className="grid grid-flow-col items-center gap-3 justify-start">
          <div className="w-10 h-10 rounded-xl grid place-items-center"
            style={{ background: 'rgba(37,99,235,0.15)', border: '1px solid rgba(37,99,235,0.3)' }}>
            <svg className="w-5 h-5" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Hồ sơ nhận được</h1>
            <p className="text-sm" style={{ color: '#64748b' }}>{subs.length} hồ sơ từ doanh nghiệp</p>
          </div>
        </div>
      </div>

      {/* Submissions list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="rounded-2xl h-24 animate-pulse" style={{ background: '#162847', opacity: 1 - i * 0.2 }} />)}
          </div>
        ) : subs.length === 0 ? (
          <div className="rounded-2xl p-12 text-center" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <p className="text-white font-semibold mb-2">Chưa có hồ sơ nào</p>
            <p className="text-sm" style={{ color: '#475569' }}>Hồ sơ từ doanh nghiệp sẽ xuất hiện tại đây</p>
          </div>
        ) : (
          subs.map(sub => {
            const st = STATUS_MAP[sub.status] || STATUS_MAP.pending;
            const isOpen = expanded === sub.id;
            return (
              <div key={sub.id} className="rounded-2xl overflow-hidden"
                style={{ background: 'linear-gradient(135deg, #162847, #0f2236)', border: '1px solid #1e3a5f' }}>
                {/* Header row */}
                <button onClick={() => toggleExpand(sub.id)}
                  className="w-full px-5 py-4 text-left transition-colors hover:bg-white/[0.02]">
                  <div className="grid items-center gap-4" style={{ gridTemplateColumns: '1fr auto auto' }}>
                    <div>
                      <p className="text-sm font-semibold text-white">{sub.company_name || 'Doanh nghiệp'}</p>
                      <p className="text-sm mt-0.5" style={{ color: '#475569' }}>
                        {sub.doc_count} tài liệu · {new Date(sub.submitted_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </p>
                      {sub.notes && <p className="text-sm mt-1" style={{ color: '#64748b' }}>"{sub.notes}"</p>}
                    </div>
                    <span className="px-3 py-1 rounded-full text-xs font-medium"
                      style={{ background: st.bg, color: st.color }}>
                      {st.label}
                    </span>
                    <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                      style={{ color: '#475569' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded content */}
                {isOpen && (
                  <div className="px-5 pb-5" style={{ borderTop: '1px solid #1e3a5f' }}>
                    {/* Status actions */}
                    <div className="grid grid-flow-col items-center gap-2 justify-start py-3">
                      {(['reviewing', 'returned', 'approved'] as const).map(s => {
                        const cfg = STATUS_MAP[s];
                        return (
                          <button key={s} onClick={() => updateStatus(sub.id, s)}
                            disabled={updatingId === sub.id || sub.status === s}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                            style={{
                              background: sub.status === s ? cfg.bg : 'rgba(255,255,255,0.03)',
                              color: sub.status === s ? cfg.color : '#64748b',
                              border: `1px solid ${sub.status === s ? cfg.color + '40' : '#1e3a5f'}`,
                              opacity: sub.status === s ? 1 : 0.7,
                            }}>
                            {cfg.label}
                          </button>
                        );
                      })}
                    </div>

                    {/* Assign auditor */}
                    {user?.is_owner && (
                      <div className="grid items-center gap-2 pb-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                        <span className="text-xs font-medium" style={{ color: '#94a3b8' }}>Auditor:</span>
                        {auditors.length === 0 ? (
                          <>
                            <a href="/auditors" className="text-xs" style={{ color: '#60a5fa' }}>
                              Chưa có auditor — Tạo auditor →
                            </a>
                            <div />
                          </>
                        ) : (
                          <>
                            <select
                              defaultValue={sub.auditor_id || ''}
                              id={`auditor-${sub.id}`}
                              className="text-sm px-3 py-2 rounded-lg text-white outline-none"
                              style={{ background: '#0a1929', border: '1px solid #1e3a5f' }}>
                              <option value="">— Chọn auditor —</option>
                              {auditors.map(a => (
                                <option key={a.id} value={a.id}>
                                  {a.display_name}{a.specialty ? ` (${a.specialty})` : ''}
                                </option>
                              ))}
                            </select>
                            <button
                              onClick={() => {
                                const sel = (document.getElementById(`auditor-${sub.id}`) as HTMLSelectElement)?.value;
                                if (sel) assignAuditor(sub.id, sel);
                              }}
                              disabled={assigningId === sub.id}
                              className="px-4 py-2 rounded-lg text-xs font-semibold text-white transition-all hover:scale-105"
                              style={{ background: 'linear-gradient(135deg, #15803d, #16a34a)', whiteSpace: 'nowrap' }}>
                              {assigningId === sub.id ? 'Đang gán...' : 'Lưu & Thông báo'}
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    {sub.auditor_name && (
                      <p className="text-xs pb-2 flex items-center gap-2" style={{ color: '#fbbf24' }}>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        Auditor: {sub.auditor_name}
                      </p>
                    )}

                    {/* Documents */}
                    {loadingDocs ? (
                      <p className="text-sm py-4 text-center" style={{ color: '#475569' }}>Đang tải tài liệu...</p>
                    ) : (
                      <div className="space-y-2">
                        {subDocs.map(doc => (
                          <div key={doc.id} className="grid items-center gap-3 px-4 py-3 rounded-xl"
                            style={{ gridTemplateColumns: '1fr auto auto', background: '#0a1929', border: '1px solid #1e3a5f' }}>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                {doc.doc_type_label && (
                                  <span className="px-2 py-0.5 rounded text-xs font-bold"
                                    style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>
                                    {doc.doc_type_label}
                                  </span>
                                )}
                                <p className="text-sm text-white truncate">{doc.original_filename}</p>
                              </div>
                            </div>
                            {doc.compliance_score !== null && (
                              <span className="text-sm font-bold" style={{ color: scoreColor(doc.compliance_score) }}>
                                {doc.compliance_score}%
                              </span>
                            )}
                            <div className="flex items-center gap-1.5">
                              <button onClick={() => viewDoc(doc.id)} title="Xem"
                                className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
                                <svg className="w-3.5 h-3.5" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                              </button>
                              <a href={`/api/api/documents/${doc.id}/file?token=${encodeURIComponent(token || '')}`}
                                download title="Tải xuống"
                                className="w-7 h-7 rounded-lg grid place-items-center transition-all hover:scale-110"
                                style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>
                                <svg className="w-3.5 h-3.5" style={{ color: '#4ade80' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
