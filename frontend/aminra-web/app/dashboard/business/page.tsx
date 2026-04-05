'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

interface DocTypeProgress {
  doc_type: string;
  label: string;
  score: number | null;
  status: string | null;
  filename: string | null;
  uploaded_at: string | null;
}
interface RecentItem {
  filename: string;
  doc_type_label: string | null;
  score: number | null;
  status: string | null;
  uploaded_by: string | null;
  uploaded_at: string | null;
}
interface DashboardStats {
  readiness: number;
  compliant_count: number;
  total_types: number;
  submitted_count: number;
  total_documents: number;
  avg_score: number | null;
  member_count: number;
  doc_type_progress: DocTypeProgress[];
  recent_activity: RecentItem[];
}

const STATUS_STYLE = {
  compliant:     { label: 'Đạt',        bg: 'rgba(34,197,94,0.15)',   color: '#4ade80' },
  needs_review:  { label: 'Cần sửa',    bg: 'rgba(245,158,11,0.15)', color: '#fbbf24' },
  non_compliant: { label: 'Chưa đạt',   bg: 'rgba(239,68,68,0.15)',  color: '#f87171' },
};

function scoreColor(s: number | null) {
  if (s === null) return '#334155';
  if (s >= 75) return '#4ade80';
  if (s >= 50) return '#fbbf24';
  return '#f87171';
}

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return 'Hôm nay';
  if (d === 1) return 'Hôm qua';
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Chào buổi sáng';
  if (h < 18) return 'Chào buổi chiều';
  return 'Chào buổi tối';
}

export default function BusinessDashboard() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading, logout } = useUserAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'business')) {
      router.replace('/business/login');
    }
  }, [loading, isAuthenticated, user, router]);

  const fetchStats = useCallback(async () => {
    if (!token) return;
    setLoadingStats(true);
    try {
      const res = await fetch('/api/api/dashboard/stats', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setStats(await res.json());
    } finally {
      setLoadingStats(false);
    }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchStats(); }, [isAuthenticated, fetchStats]);

  if (loading || !user) {
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="text-slate-400 text-sm">Đang tải...</div>
      </div>
    );
  }

  const s = stats;

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full">
      {/* Header */}
      <div className="grid items-start mb-6" style={{ gridTemplateColumns: '1fr auto' }}>
        <div>
          <p className="text-sm mb-1" style={{ color: '#64748b' }}>{greeting()},</p>
          <h1 className="text-2xl font-bold text-white">{user.company_name}</h1>
          <p className="text-slate-500 text-sm mt-1">{user.email}</p>
        </div>
        <button onClick={() => { logout(); router.push('/'); }}
          className="text-xs text-slate-400 hover:text-red-400 transition-colors px-3 py-2 rounded-lg"
          style={{ border: '1px solid #1e3a5f' }}>
          Đăng xuất
        </button>
      </div>

      {/* Certification Readiness */}
      {s && (
        <div className="rounded-2xl p-6 mb-6"
          style={{ background: 'linear-gradient(135deg, #0f2236, #162847)', border: '1px solid #1e3a5f' }}>
          <div className="grid items-center gap-6" style={{ gridTemplateColumns: 'auto 1fr' }}>
            {/* Circular progress */}
            <div className="relative w-24 h-24">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#1e3a5f" strokeWidth="8" />
                <circle cx="50" cy="50" r="42" fill="none"
                  stroke={s.readiness >= 75 ? '#22c55e' : s.readiness >= 40 ? '#f59e0b' : '#ef4444'}
                  strokeWidth="8" strokeLinecap="round"
                  strokeDasharray={`${s.readiness * 2.64} 264`} />
              </svg>
              <div className="absolute inset-0 grid place-items-center">
                <div className="text-center">
                  <span className="text-2xl font-bold text-white">{s.readiness}%</span>
                </div>
              </div>
            </div>
            <div>
              <h2 className="text-lg font-bold text-white mb-1">Sẵn sàng chứng nhận</h2>
              <p className="text-sm" style={{ color: '#94a3b8' }}>
                <strong className="text-white">{s.compliant_count}</strong>/{s.total_types} loại tài liệu đạt chuẩn
                {s.submitted_count > 0 && s.submitted_count < s.total_types && (
                  <span> · {s.total_types - s.submitted_count} chưa upload</span>
                )}
              </p>
              {/* Mini progress bar */}
              <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: '#1e3a5f' }}>
                <div className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${s.readiness}%`,
                    background: s.readiness >= 75 ? '#22c55e' : s.readiness >= 40 ? '#f59e0b' : '#ef4444',
                  }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Tài liệu', value: s?.total_documents ?? '—', sub: 'đã upload', color: '#60a5fa' },
          { label: 'Điểm TB', value: s?.avg_score !== null && s?.avg_score !== undefined ? `${s.avg_score}%` : '—', sub: 'compliance', color: scoreColor(s?.avg_score ?? null) },
          { label: 'Đạt chuẩn', value: s?.compliant_count ?? '—', sub: `/ ${s?.total_types ?? 13} loại`, color: '#4ade80' },
          { label: 'Thành viên', value: `${user.member_count ?? 0}/7`, sub: 'đang hoạt động', color: '#818cf8' },
        ].map(st => (
          <div key={st.label} className="rounded-xl p-4" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <div className="text-xl font-bold mb-0.5" style={{ color: st.color }}>{st.value}</div>
            <div className="text-xs text-white font-medium">{st.label}</div>
            <div className="text-xs mt-0.5" style={{ color: '#475569' }}>{st.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 flex-1 lg:min-h-0" style={{ gridTemplateColumns: '1fr 22rem' }}>
        {/* Left: Document progress */}
        <div className="flex flex-col lg:min-h-0">
          <div className="grid items-center mb-3" style={{ gridTemplateColumns: '1fr auto' }}>
            <h3 className="text-sm font-bold text-white">Tiến trình tài liệu</h3>
            <Link href="/upload" className="text-xs font-medium" style={{ color: '#4ade80' }}>
              Upload tài liệu →
            </Link>
          </div>
          <div className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: '1px solid #1e3a5f' }}>
            {loadingStats ? (
              <div className="p-8 text-center text-slate-500 text-sm">Đang tải...</div>
            ) : (
              <table className="w-full text-sm">
                <thead style={{ background: '#0f1e35', position: 'sticky', top: 0 }}>
                  <tr>
                    {['Loại tài liệu', 'File', 'Điểm', 'Trạng thái'].map(h => (
                      <th key={h} className="text-left px-4 py-2.5 text-xs text-slate-400 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(s?.doc_type_progress ?? []).map((dt, i) => {
                    const st = STATUS_STYLE[dt.status as keyof typeof STATUS_STYLE];
                    const submitted = dt.score !== null;
                    return (
                      <tr key={dt.doc_type} style={{
                        background: i % 2 === 0 ? '#162847' : '#0f1e35',
                        borderTop: '1px solid #1e3a5f',
                        opacity: submitted ? 1 : 0.5,
                      }}>
                        <td className="px-4 py-3">
                          <span className="text-white text-xs font-medium">{dt.label}</span>
                        </td>
                        <td className="px-4 py-3">
                          {dt.filename ? (
                            <span className="text-xs truncate block max-w-[140px]" style={{ color: '#64748b' }} title={dt.filename}>
                              {dt.filename}
                            </span>
                          ) : (
                            <span className="text-xs" style={{ color: '#334155' }}>—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs font-bold" style={{ color: scoreColor(dt.score) }}>
                            {dt.score !== null ? `${dt.score}%` : '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {st ? (
                            <span className="px-2 py-0.5 rounded-full text-xs" style={{ background: st.bg, color: st.color }}>
                              {st.label}
                            </span>
                          ) : (
                            <span className="text-xs" style={{ color: '#334155' }}>Chưa upload</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right: Recent activity + Quick actions */}
        <div className="flex flex-col gap-5">
          {/* Recent activity */}
          <div className="rounded-xl" style={{ border: '1px solid #1e3a5f' }}>
            <div className="px-4 py-3" style={{ borderBottom: '1px solid #1e3a5f', background: '#0f1e35' }}>
              <h3 className="text-xs font-bold text-white">Hoạt động gần đây</h3>
            </div>
            <div className="divide-y" style={{ borderColor: '#1e3a5f' }}>
              {(s?.recent_activity ?? []).length === 0 ? (
                <div className="p-6 text-center text-xs" style={{ color: '#334155' }}>Chưa có hoạt động</div>
              ) : (
                (s?.recent_activity ?? []).map((r, i) => (
                  <div key={i} className="px-4 py-3" style={{ borderColor: '#1e3a5f' }}>
                    <p className="text-xs text-white font-medium truncate" title={r.filename}>{r.filename}</p>
                    <div className="grid grid-flow-col items-center gap-2 mt-1 justify-start text-xs" style={{ color: '#475569' }}>
                      {r.score !== null && (
                        <span className="font-bold" style={{ color: scoreColor(r.score) }}>{r.score}%</span>
                      )}
                      <span>{r.doc_type_label || '—'}</span>
                      <span>·</span>
                      <span>{timeAgo(r.uploaded_at)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick actions */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold text-white px-1">Thao tác nhanh</h3>
            {[
              { href: '/upload', label: 'Đánh giá tài liệu', desc: 'Upload & kiểm tra Halal', color: '#4ade80',
                icon: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12' },
              { href: '/', label: 'Hỏi đáp AI', desc: 'Tư vấn quy trình chứng nhận', color: '#60a5fa',
                icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
              { href: '/documents', label: 'Tài liệu', desc: 'Xem & quản lý tài liệu', color: '#818cf8',
                icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
              ...(user.is_owner ? [{ href: '/members', label: 'Thành viên', desc: `${user.member_count ?? 0}/7 thành viên`, color: '#c084fc',
                icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' }] : []),
            ].map(a => (
              <Link key={a.href} href={a.href}
                className="grid items-center gap-3 px-4 py-3 rounded-xl transition-all hover:scale-[1.01]"
                style={{ gridTemplateColumns: '2rem 1fr', background: '#162847', border: '1px solid #1e3a5f' }}>
                <div className="w-8 h-8 rounded-lg grid place-items-center"
                  style={{ background: `${a.color}15`, border: `1px solid ${a.color}30` }}>
                  <svg className="w-4 h-4" style={{ color: a.color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={a.icon} />
                  </svg>
                </div>
                <div>
                  <div className="text-xs font-semibold text-white">{a.label}</div>
                  <div className="text-xs" style={{ color: '#475569' }}>{a.desc}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
