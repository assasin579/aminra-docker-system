'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';
import { openAuthed } from '@/lib/authedOpen';
import { parseApiError } from '@/lib/apiError';

/* ── Types ── */
interface Template {
  id: string;
  name: string;
  standard: string;
  provider_name: string;
  item_count: number;
}
interface AssessmentSummary {
  id: string;
  name: string;
  standard: string;
  status: 'in_progress' | 'completed';
  score: number | null;
  total_items: number;
  passed_items: number;
  created_at: string;
}
interface AssessmentItem {
  code: string;
  category: string;
  criteria: string;
  severity: string;
  clause: string;
  audit_method: string;
  documents: string;
  result: 'pass' | 'fail' | 'na' | null;
  note: string;
}
interface AssessmentDetail {
  id: string;
  name: string;
  standard: string;
  status: 'in_progress' | 'completed';
  score: number | null;
  total_items: number;
  passed_items: number;
  items: AssessmentItem[];
  created_at: string;
}

/* ── Constants ── */
const STATUS_MAP: Record<string, { label: string; bg: string; color: string }> = {
  in_progress: { label: 'Dang danh gia', bg: '#DBEAFE', color: '#2563EB' },
  completed:   { label: 'Hoan thanh',     bg: '#E8F5EF', color: '#0F5132' },
};
const SEVERITY_MAP: Record<string, { label: string; bg: string; color: string }> = {
  critical: { label: 'Nghiem trong', bg: '#FEF2F2', color: '#DC2626' },
  major:    { label: 'Lon',          bg: '#FFF7ED', color: '#D97706' },
  minor:    { label: 'Nho',          bg: '#F3F4F6', color: '#6B7280' },
};
const RESULT_OPTIONS: { value: 'pass' | 'fail' | 'na'; label: string; color: string }[] = [
  { value: 'pass', label: 'Dat',      color: '#0F5132' },
  { value: 'fail', label: 'Chua dat', color: '#DC2626' },
  { value: 'na',   label: 'N/A',      color: '#6B7280' },
];

const fmtDate = (iso: string | null) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return iso; }
};

function scoreColor(s: number | null) {
  if (s === null) return '#6B7280';
  if (s >= 75) return '#0F5132';
  if (s >= 50) return '#F59E0B';
  return '#f87171';
}

function gapColor(pct: number) {
  if (pct >= 75) return '#0F5132';
  if (pct >= 50) return '#D97706';
  return '#DC2626';
}

/* ── Badge ── */
const Badge = ({ map, value }: { map: Record<string, { label: string; bg: string; color: string }>; value: string }) => {
  const m = map[value] || { label: value, bg: '#F3F4F6', color: '#6B7280' };
  return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap" style={{ background: m.bg, color: m.color }}>{m.label}</span>;
};

/* ── Score Circle ── */
const ScoreCircle = ({ score, size = 80 }: { score: number | null; size?: number }) => {
  const pct = score ?? 0;
  const r = 42;
  const circumference = 2 * Math.PI * r;
  const dash = (pct / 100) * circumference;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#E2E8F0" strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none"
          className="animate-score-fill"
          stroke={scoreColor(score)}
          strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`} />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span className="font-bold" style={{ color: '#0F5132', fontSize: size * 0.25 }}>
          {score !== null ? `${score}%` : '--'}
        </span>
      </div>
    </div>
  );
};

/* ── Main Component ── */
export default function SelfAssessmentPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();

  /* ── State: list view ── */
  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [fetching, setFetching] = useState(false);

  /* ── State: detail view ── */
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AssessmentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  /* ── State: create modal ── */
  const [showCreate, setShowCreate] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [createForm, setCreateForm] = useState({ template_id: '', name: '' });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  /* ── State: completing ── */
  const [completing, setCompleting] = useState(false);

  /* ── State: deleting ── */
  const [deleting, setDeleting] = useState(false);

  /* ── Debounce refs ── */
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  /* ── Auth guard ── */
  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'business'))
      router.replace('/');
  }, [loading, isAuthenticated, user, router]);

  /* ── Fetch list ── */
  const fetchAssessments = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch('/api/api/assessments/', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setAssessments(d.assessments || []);
      }
    } finally { setFetching(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchAssessments(); }, [isAuthenticated, fetchAssessments]);

  /* ── Fetch templates ── */
  const fetchTemplates = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch('/api/api/assessments/templates', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d = await res.json();
        setTemplates(d.templates || []);
      }
    } catch { /* ignore */ }
  }, [token]);

  /* ── Fetch detail ── */
  const fetchDetail = useCallback(async (id: string) => {
    if (!token) return;
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/api/assessments/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const d: AssessmentDetail = await res.json();
        setDetail(d);
      }
    } finally { setDetailLoading(false); }
  }, [token]);

  /* ── Select assessment ── */
  const openDetail = (id: string) => {
    setSelectedId(id);
    fetchDetail(id);
  };

  const backToList = () => {
    setSelectedId(null);
    setDetail(null);
    fetchAssessments();
  };

  /* ── Create ── */
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.template_id || !createForm.name) return;
    setCreateError(''); setCreating(true);
    try {
      const res = await fetch('/api/api/assessments/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ template_id: createForm.template_id, name: createForm.name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Tao that bai'));
      }
      const d = await res.json();
      setShowCreate(false);
      setCreateForm({ template_id: '', name: '' });
      openDetail(d.id);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Loi');
    } finally { setCreating(false); }
  };

  /* ── Update item result ── */
  const setItemResult = async (index: number, result: 'pass' | 'fail' | 'na') => {
    if (!detail || !selectedId) return;
    // Optimistic update
    setDetail(prev => {
      if (!prev) return prev;
      const items = [...prev.items];
      items[index] = { ...items[index], result };
      return { ...prev, items };
    });
    await fetch(`/api/api/assessments/${selectedId}/items/${index}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ result, note: detail.items[index].note }),
    });
  };

  /* ── Update item note (debounced) ── */
  const setItemNote = (index: number, note: string) => {
    if (!detail || !selectedId) return;
    setDetail(prev => {
      if (!prev) return prev;
      const items = [...prev.items];
      items[index] = { ...items[index], note };
      return { ...prev, items };
    });
    const key = `note-${index}`;
    clearTimeout(debounceTimers.current[key]);
    debounceTimers.current[key] = setTimeout(async () => {
      const item = detail.items[index];
      await fetch(`/api/api/assessments/${selectedId}/items/${index}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ result: item.result || 'na', note }),
      });
    }, 800);
  };

  /* ── Complete ── */
  const handleComplete = async () => {
    if (!selectedId || !confirm('Xac nhan hoan thanh danh gia?')) return;
    setCompleting(true);
    try {
      const res = await fetch(`/api/api/assessments/${selectedId}/complete`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchDetail(selectedId);
      }
    } finally { setCompleting(false); }
  };

  /* ── Delete ── */
  const handleDelete = async () => {
    if (!selectedId || !confirm('Xac nhan xoa danh gia nay?')) return;
    setDeleting(true);
    try {
      await fetch(`/api/api/assessments/${selectedId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      backToList();
    } finally { setDeleting(false); }
  };

  /* ── Export PDF ── */
  const handleExportPdf = () => {
    if (!selectedId) return;
    openAuthed(`/api/api/assessments/${selectedId}/export-pdf`, token || '');
  };

  /* ── Loading state ── */
  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="flex items-center gap-1.5">
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
      </div>
    </div>
  );

  /* ── Derived stats ── */
  const completedCount = assessments.filter(a => a.status === 'completed').length;
  const avgScore = completedCount > 0
    ? Math.round(assessments.filter(a => a.status === 'completed' && a.score !== null).reduce((s, a) => s + (a.score || 0), 0) / completedCount)
    : 0;

  /* ── Style helpers ── */
  const card = "bg-white rounded-xl p-4 mb-3 border border-[#E2E8F0]";
  const btnPrimary = "py-3 rounded-xl border-none bg-[#0F5132] text-white text-sm font-bold cursor-pointer transition-all active:scale-[0.98]";
  const btnOutline = "px-4 py-2.5 rounded-lg border-[1.5px] border-[#E2E8F0] bg-white text-sm font-semibold cursor-pointer transition-all active:scale-[0.98] text-center";
  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-[#E2E8F0] text-sm outline-none transition-all focus:border-[rgba(15,81,50,0.4)] focus:shadow-[0_0_0_3px_rgba(15,81,50,0.08)]";
  const labelCls = "text-xs font-semibold text-[#6B7280] mb-1 block";

  /* ══════════════════════════════════════════════
     DETAIL VIEW
     ══════════════════════════════════════════════ */
  if (selectedId) {
    if (detailLoading || !detail) return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
          <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
        </div>
      </div>
    );

    // Group items by category
    const grouped: Record<string, { item: AssessmentItem; index: number }[]> = {};
    detail.items.forEach((item, idx) => {
      const cat = item.category || 'Khac';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push({ item, index: idx });
    });

    // Gap analysis
    const totalItems = detail.items.length;
    const passedItems = detail.items.filter(it => it.result === 'pass').length;
    const failedItems = detail.items.filter(it => it.result === 'fail').length;
    const naItems = detail.items.filter(it => it.result === 'na').length;
    const answeredItems = passedItems + failedItems + naItems;
    const applicableItems = totalItems - naItems;
    const gapPct = applicableItems > 0 ? Math.round((passedItems / applicableItems) * 100) : 0;
    const remaining = applicableItems - passedItems;

    return (
      <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden" data-page>
        {/* Back + header */}
        <div className="flex items-center gap-3 py-4 animate-section">
          <button onClick={backToList}
            className="w-9 h-9 rounded-xl grid place-items-center flex-shrink-0 transition-all hover:bg-black/5"
            style={{ border: '1px solid #E2E8F0' }}>
            <svg className="w-5 h-5" style={{ color: '#6B7280' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold truncate" style={{ color: '#0F5132' }}>{detail.name}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs" style={{ color: '#6B7280' }}>{detail.standard}</span>
              <Badge map={STATUS_MAP} value={detail.status} />
            </div>
          </div>
          <ScoreCircle score={detail.score} size={56} />
        </div>

        {/* Gap analysis summary */}
        <div className="rounded-xl p-4 mb-4 animate-section"
          style={{ background: `${gapColor(gapPct)}10`, border: `1px solid ${gapColor(gapPct)}30` }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
              style={{ background: `${gapColor(gapPct)}18` }}>
              <svg className="w-5 h-5" style={{ color: gapColor(gapPct) }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm font-bold" style={{ color: gapColor(gapPct) }}>
                Dat {passedItems}/{applicableItems} — con {remaining} hang muc can cai thien
              </p>
              <div className="flex items-center gap-3 mt-1.5">
                <span className="text-xs" style={{ color: '#0F5132' }}>Dat: {passedItems}</span>
                <span className="text-xs" style={{ color: '#DC2626' }}>Chua dat: {failedItems}</span>
                <span className="text-xs" style={{ color: '#6B7280' }}>N/A: {naItems}</span>
                <span className="text-xs" style={{ color: '#94A3B8' }}>Chua tra loi: {totalItems - answeredItems}</span>
              </div>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: '#E2E8F0' }}>
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${gapPct}%`, background: gapColor(gapPct) }} />
          </div>
        </div>

        {/* Completed: prominent score + gap list */}
        {detail.status === 'completed' && (
          <div className={`${card} text-center animate-section`}>
            <ScoreCircle score={detail.score} size={96} />
            <p className="text-base font-bold mt-3" style={{ color: '#0F5132' }}>Ket qua danh gia</p>
            <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
              {detail.score !== null && detail.score >= 75
                ? 'Doanh nghiep dat muc chuan bi tot. Tiep tuc duy tri!'
                : detail.score !== null && detail.score >= 50
                ? 'Can cai thien them mot so hang muc de dat chuan.'
                : 'Nhieu hang muc can cai thien. Hay xem chi tiet ben duoi.'}
            </p>
            {failedItems > 0 && (
              <div className="mt-3 text-left">
                <p className="text-xs font-bold mb-2" style={{ color: '#DC2626' }}>Hang muc chua dat:</p>
                <div className="space-y-1">
                  {detail.items.filter(it => it.result === 'fail').map((it, i) => (
                    <div key={i} className="flex items-start gap-2 px-3 py-2 rounded-lg" style={{ background: '#FEF2F2' }}>
                      <span className="px-1.5 py-0.5 rounded text-xs font-bold flex-shrink-0" style={{ background: '#DBEAFE', color: '#2563EB' }}>{it.code}</span>
                      <span className="text-xs" style={{ color: '#374151' }}>{it.criteria}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Items grouped by category */}
        <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-1 pb-24">
          {Object.entries(grouped).map(([cat, catItems]) => (
            <div key={cat} className="mb-4">
              <h3 className="text-sm font-bold py-2 mb-2 border-b-2 border-[#E2E8F0] animate-section" style={{ color: '#0F5132' }}>{cat}</h3>
              {catItems.map(({ item, index }) => {
                const sev = SEVERITY_MAP[item.severity] || SEVERITY_MAP.minor;
                return (
                  <div key={index} className={`${card} doc-card-hover animate-list-item stagger-${Math.min(index + 1, 12)}`}>
                    {/* Top row: code + criteria + severity */}
                    <div className="flex items-start gap-2 mb-2">
                      {item.code && (
                        <span className="px-2 py-0.5 rounded text-xs font-bold flex-shrink-0" style={{ background: '#DBEAFE', color: '#2563EB' }}>{item.code}</span>
                      )}
                      <span className="flex-1 text-sm leading-snug" style={{ color: '#0F5132' }}>{item.criteria}</span>
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0" style={{ background: sev.bg, color: sev.color }}>{sev.label}</span>
                    </div>

                    {/* Clause */}
                    {item.clause && (
                      <p className="text-xs mb-2" style={{ color: '#94A3B8' }}>Dieu khoan: {item.clause}</p>
                    )}

                    {/* Audit method */}
                    {item.audit_method && (
                      <p className="text-xs mb-2">
                        <span className="px-1.5 py-0.5 rounded" style={{ background: '#F3E8FF', color: '#7C3AED' }}>{item.audit_method}</span>
                      </p>
                    )}

                    {/* Documents */}
                    {item.documents && (
                      <p className="text-xs mb-2" style={{ color: '#94A3B8' }}>Tai lieu: {item.documents}</p>
                    )}

                    {/* Result pills */}
                    <div className="grid grid-cols-3 gap-1.5 mb-2.5">
                      {RESULT_OPTIONS.map(r => {
                        const active = item.result === r.value;
                        return (
                          <button key={r.value}
                            onClick={() => detail.status !== 'completed' && setItemResult(index, r.value)}
                            disabled={detail.status === 'completed'}
                            className="py-2 rounded-full text-xs font-bold transition-all active:scale-95"
                            style={{
                              border: `1.5px solid ${r.color}`,
                              background: active ? r.color : '#fff',
                              color: active ? '#fff' : r.color,
                              opacity: detail.status === 'completed' ? 0.7 : 1,
                              cursor: detail.status === 'completed' ? 'default' : 'pointer',
                            }}>
                            {r.label}
                          </button>
                        );
                      })}
                    </div>

                    {/* Note input */}
                    <input
                      className={inputCls}
                      placeholder="Ghi chu..."
                      value={item.note || ''}
                      onChange={e => setItemNote(index, e.target.value)}
                      disabled={detail.status === 'completed'}
                    />
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="fixed bottom-0 left-0 right-0 z-40 px-4 py-3 lg:pl-[280px]"
          style={{ background: 'rgba(255,255,255,0.95)', backdropFilter: 'blur(12px)', borderTop: '1px solid #E2E8F0' }}>
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            {detail.status === 'in_progress' && (
              <button onClick={handleComplete} disabled={completing}
                className={`${btnPrimary} flex-1 px-6`}
                style={{ background: completing ? '#E2E8F0' : '#0F5132', color: completing ? '#6B7280' : 'white' }}>
                {completing ? 'Dang hoan thanh...' : 'Hoan thanh danh gia'}
              </button>
            )}
            <button onClick={handleExportPdf}
              className={`${btnOutline} flex items-center justify-center gap-2`}
              style={{ color: '#0EA5E9', borderColor: '#0EA5E9' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Xuat PDF
            </button>
            <button onClick={handleDelete} disabled={deleting}
              className={`${btnOutline}`}
              style={{ color: '#DC2626', borderColor: 'rgba(220,38,38,0.3)' }}>
              {deleting ? '...' : 'Xoa'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ══════════════════════════════════════════════
     LIST VIEW
     ══════════════════════════════════════════════ */
  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden" data-page>
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(15,81,50,0.12)', border: '1px solid rgba(15,81,50,0.25)' }}>
              <svg className="w-5 h-5" style={{ color: '#0F5132' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#0F5132' }}>Tu danh gia</h1>
              <p className="text-sm" style={{ color: '#6B7280' }}>Danh gia muc do san sang cua doanh nghiep</p>
            </div>
          </div>
          <button onClick={() => { setShowCreate(true); fetchTemplates(); }}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
            style={{ background: '#0F5132', boxShadow: '0 4px 12px rgba(15,81,50,0.3)' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
            </svg>
            Bat dau danh gia moi
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          { label: 'Tong danh gia', value: assessments.length, color: '#2563EB', bg: '#DBEAFE' },
          { label: 'Hoan thanh', value: completedCount, color: '#0F5132', bg: '#E8F5EF' },
          { label: 'Diem trung binh', value: `${avgScore}%`, color: scoreColor(avgScore), bg: avgScore >= 75 ? '#E8F5EF' : avgScore >= 50 ? '#FFF7ED' : '#FEF2F2' },
        ].map((s, i) => (
          <div key={i} className={`rounded-xl p-4 text-center animate-section stagger-${i + 1}`}
            style={{ background: s.bg, border: '1px solid #E2E8F0' }}>
            <p className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</p>
            <p className="text-xs mt-1" style={{ color: '#6B7280' }}>{s.label}</p>
          </div>
        ))}
      </div>

      {/* Assessment list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="rounded-2xl h-24 animate-pulse" style={{ background: '#F7F1E6', opacity: 1 - i * 0.15 }} />)}
          </div>
        ) : assessments.length === 0 ? (
          <div className="rounded-2xl p-12 text-center animate-section" style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
            <svg className="w-16 h-16 mx-auto mb-4 animate-empty-icon" style={{ color: '#E2E8F0' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="font-semibold mb-2" style={{ color: '#0F5132' }}>Chua co danh gia nao</p>
            <p className="text-sm" style={{ color: '#6B7280' }}>Bat dau tu danh gia de xem muc do san sang cua doanh nghiep</p>
          </div>
        ) : (
          assessments.map((a, idx) => {
            const st = STATUS_MAP[a.status] || STATUS_MAP.in_progress;
            return (
              <div key={a.id}
                className={`rounded-xl p-4 transition-colors doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', cursor: 'pointer' }}
                onClick={() => openDetail(a.id)}>
                <div className="flex items-center gap-4">
                  {/* Score circle */}
                  <ScoreCircle score={a.score} size={52} />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <p className="text-sm font-semibold truncate" style={{ color: '#0F5132' }}>{a.name}</p>
                      <span className="px-2 py-0.5 rounded-lg text-xs font-medium"
                        style={{ background: st.bg, color: st.color }}>
                        {st.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs" style={{ color: '#6B7280' }}>
                      <span>{a.standard}</span>
                      <span>{a.passed_items}/{a.total_items} dat</span>
                      <span>{fmtDate(a.created_at)}</span>
                    </div>
                  </div>

                  {/* Arrow */}
                  <svg className="w-5 h-5 flex-shrink-0" style={{ color: '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 25px 60px rgba(0,0,0,0.15)' }}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-base font-bold" style={{ color: '#0F5132' }}>Bat dau danh gia moi</h3>
              <button onClick={() => setShowCreate(false)}
                className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: 'rgba(0,0,0,0.05)' }}>
                <span className="hover:text-gray-700">x</span>
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className={labelCls}>Mau danh gia *</label>
                <select value={createForm.template_id}
                  onChange={e => setCreateForm(f => ({ ...f, template_id: e.target.value }))}
                  required
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }}>
                  <option value="">-- Chon mau --</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.standard} - {t.item_count} hang muc)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls}>Ten danh gia *</label>
                <input type="text" required value={createForm.name}
                  onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="VD: Tu danh gia Halal Q2/2026"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
              </div>
              {createError && <p className="text-xs text-red-400">{createError}</p>}
              <button type="submit" disabled={creating}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{ background: creating ? '#E2E8F0' : '#0F5132', color: creating ? '#6B7280' : 'white' }}>
                {creating ? 'Dang tao...' : 'Bat dau danh gia'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
