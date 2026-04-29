'use client';

import { use, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

interface Revision {
  id: string;
  original_filename: string;
  compliance_score: number | null;
  file_size: number | null;
  uploaded_at: string;
  overall_status: string | null;
  cb_approved_by: string | null;
  status: string | null;
}
interface DocBucket {
  doc_type: string;
  revision_count: number;
  current: Revision | null;
  revisions: Revision[];
}
interface SubmissionRow {
  id: string;
  status: string;
  document_ids: string[];
  deadline: string | null;
  auditor_id: string | null;
  auditor_notes: string;
  submitted_at: string | null;
  updated_at: string;
}
interface AuditVisit {
  id: string;
  status: string;
  visit_type: string;
  scheduled_date: string;
  compliance_score: number | null;
  auditor_id: string | null;
}
interface Dossier {
  business: { id: string; company_name: string; email: string; phone: string; address: string };
  submissions: SubmissionRow[];
  documents_by_type: DocBucket[];
  audit_visits: AuditVisit[];
}
interface ScoreCard {
  business_id: string;
  composite_score: number | null;
  rating: 'excellent' | 'good' | 'fair' | 'needs_improvement' | 'unrated';
  doc_component:    { score: number | null; doc_types_evaluated: number; min: number | null; max: number | null; weight: number };
  audit_component:  { score: number | null; completed_visits: number; scored_visits: number; min: number | null; max: number | null; weight: number };
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Đang chờ', assigned: 'Đã giao auditor', reviewing: 'Đang đánh giá',
  revision_required: 'Cần sửa', returned: 'Đã trả lại', rejected: 'Bị từ chối',
  approved: 'Đã duyệt',
  scheduled: 'Đã lên lịch', in_progress: 'Đang kiểm', completed: 'Đã kiểm xong', report_submitted: 'Đã có báo cáo',
};
const STATUS_COLOR: Record<string, string> = {
  pending: '#94A3B8', assigned: '#3B82F6', reviewing: '#F59E0B', revision_required: '#EF4444',
  returned: '#94A3B8', rejected: '#DC2626', approved: '#0A1F44',
  scheduled: '#3B82F6', in_progress: '#F59E0B', completed: '#0A1F44', report_submitted: '#0A1F44',
};
const RATING_LABEL: Record<string, { label: string; color: string; bg: string }> = {
  excellent:         { label: 'Xuất sắc',     color: '#0A1F44', bg: '#DCE3F0' },
  good:              { label: 'Tốt',          color: '#0EA5E9', bg: '#E0F2FE' },
  fair:              { label: 'Trung bình',   color: '#D97706', bg: '#FEF3C7' },
  needs_improvement: { label: 'Cần cải thiện', color: '#DC2626', bg: '#FEF2F2' },
  unrated:           { label: 'Chưa chấm điểm', color: '#64748B', bg: '#F1F5F9' },
};

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return iso; }
}
function fmtSize(bytes: number | null) {
  if (!bytes) return '—';
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
}

export default function ProviderBusinessPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [score, setScore]     = useState<ScoreCard | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError]   = useState('');
  const [openType, setOpenType] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider' || !user?.is_owner))
      router.replace('/dashboard/provider');
  }, [loading, isAuthenticated, user, router]);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    setError('');
    try {
      const [dRes, sRes] = await Promise.all([
        fetch(`/api/api/audits/businesses/${id}/dossier`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`/api/api/audits/businesses/${id}/score`,   { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!dRes.ok) throw new Error('Không tải được hồ sơ doanh nghiệp');
      if (!sRes.ok) throw new Error('Không tính được điểm doanh nghiệp');
      setDossier(await dRes.json());
      setScore(await sRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi tải dữ liệu');
    } finally {
      setFetching(false);
    }
  }, [token, id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading || fetching) {
    return <div className="max-w-5xl mx-auto px-4 py-12 text-sm" style={{ color: '#94A3B8' }}>Đang tải...</div>;
  }
  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div role="alert" className="rounded-lg p-4 text-sm" style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#991B1B' }}>{error}</div>
      </div>
    );
  }
  if (!dossier || !score) return null;

  const rating = RATING_LABEL[score.rating];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8" data-page>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <Link href="/portfolio" className="inline-flex items-center min-h-[32px] text-sm font-medium" style={{ color: '#0A1F44' }}>← Portfolio</Link>
          <h1 className="text-2xl font-bold mt-1" style={{ color: '#0A1F44' }}>{dossier.business.company_name}</h1>
          <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>
            {dossier.business.email}{dossier.business.phone ? ' • ' + dossier.business.phone : ''}
          </p>
        </div>
      </div>

      {/* Composite score widget */}
      <section className="rounded-2xl p-6 mb-6" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide font-semibold mb-1" style={{ color: '#64748B' }}>Điểm doanh nghiệp</p>
            <div className="flex items-baseline gap-3">
              <span className="text-5xl font-black" style={{ color: rating.color }}>
                {score.composite_score ?? '—'}
                <span className="text-xl font-bold ml-0.5" style={{ color: '#94A3B8' }}>{score.composite_score !== null ? '/100' : ''}</span>
              </span>
              <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ background: rating.bg, color: rating.color }}>{rating.label}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ScoreComponent
              title="Tài liệu"
              score={score.doc_component.score}
              meta={`${score.doc_component.doc_types_evaluated} loại tài liệu`}
              weight={score.doc_component.weight}
            />
            <ScoreComponent
              title="Kiểm định thực tế"
              score={score.audit_component.score}
              meta={`${score.audit_component.completed_visits} lần kiểm`}
              weight={score.audit_component.weight}
            />
          </div>
        </div>
        <p className="text-xs mt-4 leading-relaxed" style={{ color: '#64748B' }}>
          Điểm tổng = 40% điểm tài liệu (lấy revision mới nhất mỗi loại) + 60% điểm kiểm định thực tế (visit đã hoàn thành).
          Khi chỉ có 1 nguồn dữ liệu, dùng 100% nguồn đó.
        </p>
      </section>

      {/* Documents by type — the "folder" */}
      <section className="rounded-2xl mb-6" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
        <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid #F0F0F0' }}>
          <h2 className="text-base font-bold" style={{ color: '#0A1F44' }}>Thư mục tài liệu — {dossier.documents_by_type.length} loại</h2>
        </div>
        {dossier.documents_by_type.length === 0 ? (
          <p className="px-6 py-8 text-sm text-center" style={{ color: '#94A3B8' }}>Chưa có tài liệu nào từ doanh nghiệp này</p>
        ) : (
          <div>
            {dossier.documents_by_type.map(b => {
              const isOpen = openType === b.doc_type;
              return (
                <div key={b.doc_type} style={{ borderBottom: '1px solid #F8F8F8' }}>
                  <button onClick={() => setOpenType(isOpen ? null : b.doc_type)}
                    className="w-full px-6 py-4 text-left transition-colors hover:bg-black/[0.02]">
                    <div className="flex items-center gap-4">
                      <div className="w-9 h-9 rounded-lg grid place-items-center flex-shrink-0"
                        style={{ background: 'rgba(10,31,68,0.08)', color: '#0A1F44' }}>📁</div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold" style={{ color: '#0A1F44' }}>{b.doc_type}</p>
                        <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>
                          {b.revision_count} revision • Mới nhất: {b.current?.original_filename ?? '—'}
                          {b.current?.compliance_score !== null && b.current?.compliance_score !== undefined && (
                            <span className="ml-2 font-bold" style={{ color: '#0A1F44' }}>{b.current.compliance_score}/100</span>
                          )}
                        </p>
                      </div>
                      <svg className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} style={{ color: '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"/>
                      </svg>
                    </div>
                  </button>
                  {isOpen && (
                    <div className="px-6 pb-4 animate-tab-content">
                      <table className="w-full text-xs">
                        <thead>
                          <tr style={{ color: '#94A3B8' }}>
                            <th className="text-left py-2 font-medium">Tên file</th>
                            <th className="text-left py-2 font-medium">Upload</th>
                            <th className="text-right py-2 font-medium">Kích thước</th>
                            <th className="text-right py-2 font-medium">Điểm</th>
                            <th className="text-right py-2 font-medium">CB approved</th>
                          </tr>
                        </thead>
                        <tbody>
                          {b.revisions.map((r, i) => (
                            <tr key={r.id} style={{ borderTop: '1px solid #F8F8F8' }}>
                              <td className="py-2.5" style={{ color: '#0A1F44' }}>
                                {i === 0 && <span className="px-1.5 py-0.5 rounded text-[10px] font-bold mr-2" style={{ background: '#DCE3F0', color: '#0A1F44' }}>HIỆN TẠI</span>}
                                {r.original_filename}
                              </td>
                              <td className="py-2.5" style={{ color: '#64748B' }}>{fmtDate(r.uploaded_at)}</td>
                              <td className="py-2.5 text-right" style={{ color: '#64748B' }}>{fmtSize(r.file_size)}</td>
                              <td className="py-2.5 text-right font-semibold" style={{ color: r.compliance_score === null ? '#94A3B8' : (r.compliance_score >= 80 ? '#0A1F44' : r.compliance_score >= 60 ? '#D97706' : '#DC2626') }}>
                                {r.compliance_score ?? '—'}
                              </td>
                              <td className="py-2.5 text-right" style={{ color: r.overall_status === 'cb_approved' ? '#0A1F44' : '#94A3B8' }}>
                                {r.overall_status === 'cb_approved' ? '✓' : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Submissions */}
      <section className="rounded-2xl mb-6" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
        <div className="px-6 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
          <h2 className="text-base font-bold" style={{ color: '#0A1F44' }}>Hồ sơ đã gửi — {dossier.submissions.length}</h2>
        </div>
        {dossier.submissions.length === 0 ? (
          <p className="px-6 py-8 text-sm text-center" style={{ color: '#94A3B8' }}>Chưa có hồ sơ nào</p>
        ) : (
          <div>
            {dossier.submissions.map(s => (
              <div key={s.id} className="px-6 py-3.5 flex items-center gap-4" style={{ borderBottom: '1px solid #F8F8F8' }}>
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: STATUS_COLOR[s.status] + '20', color: STATUS_COLOR[s.status] }}>
                  {STATUS_LABEL[s.status] ?? s.status}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm" style={{ color: '#0A1F44' }}>
                    {s.document_ids.length} tài liệu • Gửi {fmtDate(s.submitted_at)}
                    {s.deadline && <span className="ml-2 text-xs" style={{ color: '#D97706' }}>(deadline {fmtDate(s.deadline)})</span>}
                  </p>
                  {s.auditor_notes && <p className="text-xs mt-0.5" style={{ color: '#64748B' }}>{s.auditor_notes}</p>}
                </div>
                <Link href={`/submissions`} className="text-xs font-medium" style={{ color: '#0A1F44' }}>Mở →</Link>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Audit visits */}
      <section className="rounded-2xl" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
        <div className="px-6 py-4" style={{ borderBottom: '1px solid #F0F0F0' }}>
          <h2 className="text-base font-bold" style={{ color: '#0A1F44' }}>Kiểm định thực tế — {dossier.audit_visits.length}</h2>
        </div>
        {dossier.audit_visits.length === 0 ? (
          <p className="px-6 py-8 text-sm text-center" style={{ color: '#94A3B8' }}>Chưa có lần kiểm định nào</p>
        ) : (
          <div>
            {dossier.audit_visits.map(v => (
              <div key={v.id} className="px-6 py-3.5 flex items-center gap-4" style={{ borderBottom: '1px solid #F8F8F8' }}>
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: STATUS_COLOR[v.status] + '20', color: STATUS_COLOR[v.status] }}>
                  {STATUS_LABEL[v.status] ?? v.status}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm" style={{ color: '#0A1F44' }}>{v.visit_type} • {fmtDate(v.scheduled_date)}</p>
                </div>
                {v.compliance_score !== null && (
                  <span className="text-sm font-bold" style={{ color: v.compliance_score >= 80 ? '#0A1F44' : v.compliance_score >= 60 ? '#D97706' : '#DC2626' }}>
                    {v.compliance_score}/100
                  </span>
                )}
                <Link href={`/audits/${v.id}`} className="text-xs font-medium" style={{ color: '#0A1F44' }}>Mở →</Link>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ScoreComponent({ title, score, meta, weight }: { title: string; score: number | null; meta: string; weight: number }) {
  return (
    <div className="text-right">
      <p className="text-xs" style={{ color: '#64748B' }}>{title} <span className="opacity-60">({Math.round(weight * 100)}%)</span></p>
      <p className="text-2xl font-bold" style={{ color: score === null ? '#94A3B8' : score >= 80 ? '#0A1F44' : score >= 60 ? '#D97706' : '#DC2626' }}>
        {score ?? '—'}
        {score !== null && <span className="text-xs font-medium opacity-60 ml-1">/100</span>}
      </p>
      <p className="text-xs" style={{ color: '#94A3B8' }}>{meta}</p>
    </div>
  );
}
