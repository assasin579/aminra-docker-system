'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

interface Stats {
  pending: number;
  reviewing: number;
  approved: number;
  returned: number;
  total: number;
  overdue: number;
  avg_response_hours: number | null;
  recent: Array<{
    id: string;
    company_name: string;
    status: string;
    doc_count: number;
    submitted_at: string;
    deadline: string | null;
  }>;
}

const STATUS_MAP: Record<string, { label: string; bg: string; color: string; icon: string }> = {
  pending:   { label: 'Chờ duyệt',   bg: '#F3F4F6', color: '#6B7280', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  reviewing: { label: 'Đang xét',    bg: '#DBEAFE', color: '#2563EB', icon: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
  approved:  { label: 'Đã duyệt',   bg: '#ECFDF5', color: '#059669', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  returned:  { label: 'Trả lại',    bg: '#FEF3C7', color: '#D97706', icon: 'M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6' },
};

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Chào buổi sáng';
  if (h < 18) return 'Chào buổi chiều';
  return 'Chào buổi tối';
}

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return 'Hôm nay';
  if (d === 1) return 'Hôm qua';
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

export default function ProviderDashboard() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading, logout } = useUserAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider')) {
      router.replace('/provider/login');
    }
  }, [loading, isAuthenticated, user, router]);

  const fetchStats = useCallback(async () => {
    if (!token) return;
    setLoadingStats(true);
    try {
      const res = await fetch('/api/api/submissions/stats', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setStats(await res.json());
    } finally { setLoadingStats(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchStats(); }, [isAuthenticated, fetchStats]);

  if (loading || !user) {
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
        </div>
      </div>
    );
  }

  const s = stats;

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* Header */}
      <div className="mb-6 animate-section">
        <p className="text-sm mb-1" style={{ color: '#5F6F80' }}>{greeting()},</p>
        <h1 className="text-2xl font-bold" style={{ color: '#1A2332' }}>{user.company_name}</h1>
        <div className="flex items-center gap-3 mt-2">
          <p className="text-sm" style={{ color: '#5B6B7D' }}>{user.email}</p>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
            style={{
              background: user.status === 'active' ? 'rgba(8,118,83,0.08)' : 'rgba(245,158,11,0.1)',
              color: user.status === 'active' ? '#087653' : '#D97706',
              border: `1px solid ${user.status === 'active' ? 'rgba(8,118,83,0.2)' : 'rgba(245,158,11,0.3)'}`,
            }}>
            <span className={`w-1.5 h-1.5 rounded-full ${user.status === 'active' ? 'bg-emerald-500' : 'bg-yellow-400'}`} />
            {user.status === 'active' ? 'Đã xác nhận' : 'Đang chờ duyệt'}
          </span>
          {!user.is_owner && (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium"
              style={{ background: '#DBEAFE', color: '#2563EB', border: '1px solid #BFDBFE' }}>
              Auditor
            </span>
          )}
        </div>
      </div>

      {/* Pending notice */}
      {user.status === 'pending' && (
        <div className="mb-6 p-5 rounded-xl animate-section"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" style={{ color: '#F59E0B' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium" style={{ color: '#F59E0B' }}>Tài khoản đang chờ xét duyệt</p>
              <p className="text-xs mt-1" style={{ color: '#5F6F80' }}>
                Đội ngũ AMINRA đang xem xét hồ sơ của tổ chức bạn. Trong thời gian chờ, bạn có thể khám phá tính năng AI.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats cards */}
      {s && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 animate-section">
          {([
            { key: 'pending',   label: 'Chờ duyệt',  value: s.pending,   color: '#6B7280', bg: '#F3F4F6' },
            { key: 'reviewing', label: 'Đang xét',   value: s.reviewing, color: '#2563EB', bg: '#DBEAFE' },
            { key: 'approved',  label: 'Đã duyệt',  value: s.approved,  color: '#059669', bg: '#ECFDF5' },
            { key: 'returned',  label: 'Trả lại',   value: s.returned,  color: '#D97706', bg: '#FEF3C7' },
          ] as const).map((st, i) => (
            <div key={st.key} className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
              <div className="flex items-center justify-between mb-2">
                <span className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: st.bg }}>
                  <svg className="w-4 h-4" style={{ color: st.color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={STATUS_MAP[st.key].icon} />
                  </svg>
                </span>
                {st.key === 'pending' && s.overdue > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full font-bold" style={{ background: '#FEF2F2', color: '#DC2626' }}>
                    {s.overdue} quá hạn
                  </span>
                )}
              </div>
              <div className="text-2xl font-bold animate-count" style={{ color: st.color }}>{st.value}</div>
              <div className="text-xs font-medium mt-0.5" style={{ color: '#5F6F80' }}>{st.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Metrics row */}
      {s && (
        <div className="grid grid-cols-2 gap-4 mb-6 animate-section">
          <div className="rounded-xl p-4" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <p className="text-xs font-medium" style={{ color: '#94A3B8' }}>Tổng hồ sơ nhận</p>
            <p className="text-xl font-bold mt-1" style={{ color: '#1A2332' }}>{s.total}</p>
          </div>
          <div className="rounded-xl p-4" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <p className="text-xs font-medium" style={{ color: '#94A3B8' }}>Thời gian phản hồi TB</p>
            <p className="text-xl font-bold mt-1" style={{ color: '#1A2332' }}>
              {s.avg_response_hours !== null ? `${s.avg_response_hours}h` : '—'}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-6 flex-1 lg:min-h-0 grid-cols-1 lg:grid-cols-[1fr_20rem] animate-section">
        {/* Recent submissions */}
        <div className="flex flex-col lg:min-h-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold" style={{ color: '#1A2332' }}>Hồ sơ gần đây</h3>
            <Link href="/submissions" className="text-xs font-medium" style={{ color: '#087653' }}>
              Xem tất cả →
            </Link>
          </div>
          <div className="rounded-xl overflow-hidden flex-1 lg:min-h-0 lg:overflow-y-auto"
            style={{ border: '1px solid #E2E8F0' }}>
            {loadingStats ? (
              <div className="p-4 space-y-3">
                {[1,2,3].map(i => (
                  <div key={i} className="flex gap-3 items-center">
                    <div className="shimmer skeleton-text flex-1" />
                    <div className="shimmer skeleton-text w-16" />
                  </div>
                ))}
              </div>
            ) : !s?.recent.length ? (
              <div className="p-8 text-center">
                <svg className="w-12 h-12 mx-auto mb-3 animate-empty-icon" style={{ color: '#CBD5E1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
                <p className="text-sm font-medium" style={{ color: '#1A2332' }}>Chưa có hồ sơ nào</p>
                <p className="text-xs mt-1" style={{ color: '#94A3B8' }}>Doanh nghiệp sẽ gửi hồ sơ cho bạn khi sẵn sàng</p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: '#F0F0F0' }}>
                {s.recent.map((r, i) => {
                  const st = STATUS_MAP[r.status] || STATUS_MAP.pending;
                  return (
                    <Link key={r.id} href="/submissions"
                      className={`flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors animate-list-item stagger-${Math.min(i + 1, 12)}`}>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate" style={{ color: '#1A2332' }}>{r.company_name}</p>
                        <p className="text-xs mt-0.5" style={{ color: '#94A3B8' }}>
                          {r.doc_count} tài liệu · {timeAgo(r.submitted_at)}
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ml-2"
                        style={{ background: st.bg, color: st.color }}>
                        {st.label}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="space-y-3">
          <h3 className="text-sm font-bold" style={{ color: '#1A2332' }}>Thao tác nhanh</h3>
          {[
            { href: '/submissions', label: 'Hồ sơ nhận', desc: 'Xem & đánh giá hồ sơ', color: '#087653',
              icon: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4' },
            { href: '/chat', label: 'Hỏi đáp AI', desc: 'Tra cứu tiêu chuẩn Halal', color: '#64748B',
              icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
            ...(user.is_owner ? [
              { href: '/auditors', label: 'Quản lý Auditor', desc: 'Thêm & quản lý auditor', color: '#7C3AED',
                icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
            ] : []),
            { href: '/upload', label: 'Đánh giá tài liệu', desc: 'Upload & kiểm tra compliance', color: '#0EA5E9',
              icon: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12' },
          ].map((a, i) => (
            <Link key={a.href} href={a.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl doc-card-hover animate-list-item stagger-${i + 1}`}
              style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
              <div className="w-9 h-9 rounded-lg grid place-items-center flex-shrink-0"
                style={{ background: `${a.color}12`, border: `1px solid ${a.color}25` }}>
                <svg className="w-4.5 h-4.5" style={{ color: a.color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d={a.icon} />
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: '#1A2332' }}>{a.label}</div>
                <div className="text-xs" style={{ color: '#5F6F80' }}>{a.desc}</div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
