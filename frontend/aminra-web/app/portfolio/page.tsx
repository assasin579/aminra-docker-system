'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

interface Business {
  id: string;
  company_name: string;
  email: string;
  phone: string;
  address: string;
  submission_count: number;
  approved_count: number;
  active_certs: number;
  expiring_soon: number;
  nearest_expiry: string | null;
  audit_count: number;
  last_audit: string | null;
  latest_score: number | null;
  open_ncr: number;
}

function fmtDate(iso: string | null) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return iso; }
}

function daysUntil(iso: string | null) {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000);
}

function scoreColor(s: number | null) {
  if (s === null) return '#94A3B8';
  if (s >= 80) return '#087653';
  if (s >= 60) return '#D97706';
  return '#DC2626';
}

export default function PortfolioPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [fetching, setFetching] = useState(true);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider' || !user?.is_owner))
      router.replace('/dashboard/provider');
  }, [loading, isAuthenticated, user, router]);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch('/api/api/audits/businesses', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setBusinesses((await res.json()).businesses || []);
    } finally { setFetching(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchData(); }, [isAuthenticated, fetchData]);

  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
      </div>
    </div>
  );

  const filtered = search
    ? businesses.filter(b => b.company_name.toLowerCase().includes(search.toLowerCase()) || b.email.toLowerCase().includes(search.toLowerCase()))
    : businesses;

  const totalCerts = businesses.reduce((s, b) => s + b.active_certs, 0);
  const totalExpiring = businesses.reduce((s, b) => s + b.expiring_soon, 0);
  const totalNcr = businesses.reduce((s, b) => s + b.open_ncr, 0);

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6 animate-section" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: 'rgba(8,118,83,0.12)', border: '1px solid rgba(8,118,83,0.25)' }}>
              <svg className="w-5 h-5" style={{ color: '#087653' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#1A2332' }}>Doanh nghiệp</h1>
              <p className="text-sm" style={{ color: '#5F6F80' }}>{businesses.length} doanh nghiệp đang quản lý</p>
            </div>
          </div>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Tìm doanh nghiệp..."
            className="px-4 py-2.5 rounded-xl text-sm outline-none w-full sm:w-64"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }} />
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6 animate-section">
        {[
          { label: 'Doanh nghiệp', value: businesses.length, color: '#087653', bg: '#ECFDF5' },
          { label: 'Cert đang hoạt động', value: totalCerts, color: '#2563EB', bg: '#DBEAFE' },
          { label: 'Sắp hết hạn', value: totalExpiring, color: '#D97706', bg: '#FEF3C7' },
          { label: 'NCR mở', value: totalNcr, color: '#DC2626', bg: '#FEF2F2' },
        ].map((s, i) => (
          <div key={s.label} className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${i + 1}`}
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <div className="text-2xl font-bold animate-count" style={{ color: s.color }}>{s.value}</div>
            <div className="text-xs font-medium mt-0.5" style={{ color: '#5F6F80' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Business list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className={`rounded-xl p-5 animate-list-item stagger-${i}`} style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                <div className="flex gap-4"><div className="shimmer w-10 h-10 rounded-full" /><div className="flex-1 space-y-2"><div className="shimmer skeleton-text w-40" /><div className="shimmer skeleton-text w-24" /></div></div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 animate-scale-in">
            <svg className="w-16 h-16 mx-auto mb-4 animate-empty-icon" style={{ color: '#CBD5E1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
            </svg>
            <p className="font-semibold" style={{ color: '#1A2332' }}>{search ? 'Không tìm thấy' : 'Chưa có doanh nghiệp nào'}</p>
            <p className="text-sm mt-1" style={{ color: '#94A3B8' }}>Doanh nghiệp sẽ xuất hiện khi gửi hồ sơ hoặc được kiểm định</p>
          </div>
        ) : (
          filtered.map((biz, idx) => {
            const isOpen = expanded === biz.id;
            const expiryDays = daysUntil(biz.nearest_expiry);
            return (
              <div key={biz.id} className={`rounded-xl overflow-hidden doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                {/* Header */}
                <button onClick={() => setExpanded(isOpen ? null : biz.id)}
                  className="w-full px-5 py-4 text-left transition-colors hover:bg-black/[0.02]">
                  <div className="flex items-center gap-4">
                    {/* Avatar */}
                    <div className="w-11 h-11 rounded-full grid place-items-center flex-shrink-0 text-sm font-bold"
                      style={{ background: 'rgba(8,118,83,0.1)', color: '#087653', border: '1px solid rgba(8,118,83,0.2)' }}>
                      {biz.company_name.charAt(0).toUpperCase()}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold truncate" style={{ color: '#1A2332' }}>{biz.company_name}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-1">
                        {biz.active_certs > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: '#ECFDF5', color: '#087653' }}>
                            {biz.active_certs} cert
                          </span>
                        )}
                        {biz.expiring_soon > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: '#FEF3C7', color: '#D97706' }}>
                            {biz.expiring_soon} sắp hết hạn
                          </span>
                        )}
                        {biz.open_ncr > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: '#FEF2F2', color: '#DC2626' }}>
                            {biz.open_ncr} NCR mở
                          </span>
                        )}
                        {biz.latest_score !== null && (
                          <span className="text-xs font-bold" style={{ color: scoreColor(biz.latest_score) }}>
                            {biz.latest_score}%
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Chevron */}
                    <svg className={`w-4 h-4 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`}
                      style={{ color: '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </button>

                {/* Expanded details */}
                {isOpen && (
                  <div className="px-5 pb-5 animate-tab-content" style={{ borderTop: '1px solid #F0F0F0' }}>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 py-4">
                      <div>
                        <p className="text-xs" style={{ color: '#94A3B8' }}>Hồ sơ gửi</p>
                        <p className="text-sm font-bold" style={{ color: '#1A2332' }}>{biz.submission_count}</p>
                      </div>
                      <div>
                        <p className="text-xs" style={{ color: '#94A3B8' }}>Đã duyệt</p>
                        <p className="text-sm font-bold" style={{ color: '#087653' }}>{biz.approved_count}</p>
                      </div>
                      <div>
                        <p className="text-xs" style={{ color: '#94A3B8' }}>Kiểm định</p>
                        <p className="text-sm font-bold" style={{ color: '#2563EB' }}>{biz.audit_count}</p>
                      </div>
                      <div>
                        <p className="text-xs" style={{ color: '#94A3B8' }}>Lần kiểm cuối</p>
                        <p className="text-sm font-bold" style={{ color: '#1A2332' }}>{fmtDate(biz.last_audit)}</p>
                      </div>
                    </div>

                    {/* Contact */}
                    <div className="text-sm space-y-1 mb-4" style={{ color: '#5B6B7D' }}>
                      {biz.email && <p>📧 {biz.email}</p>}
                      {biz.phone && <p>📞 {biz.phone}</p>}
                      {biz.address && <p>📍 {biz.address}</p>}
                    </div>

                    {/* Cert expiry warning */}
                    {biz.nearest_expiry && expiryDays !== null && expiryDays <= 90 && (
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg mb-3"
                        style={{ background: expiryDays <= 30 ? '#FEF2F2' : '#FEF3C7', border: `1px solid ${expiryDays <= 30 ? '#FECACA' : '#FDE68A'}` }}>
                        <span className="text-sm" style={{ color: expiryDays <= 30 ? '#DC2626' : '#D97706' }}>
                          ⚠️ Chứng nhận hết hạn {expiryDays <= 0 ? 'đã quá hạn' : `trong ${expiryDays} ngày`} ({fmtDate(biz.nearest_expiry)})
                        </span>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2">
                      <Link href="/submissions"
                        className="px-4 py-2 rounded-lg text-xs font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(8,118,83,0.1)', color: '#087653', border: '1px solid rgba(8,118,83,0.2)' }}>
                        Xem hồ sơ
                      </Link>
                      <Link href={`/audits`}
                        className="px-4 py-2 rounded-lg text-xs font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(37,99,235,0.1)', color: '#2563EB', border: '1px solid rgba(37,99,235,0.2)' }}>
                        Kiểm định
                      </Link>
                      <Link href="/certificates"
                        className="px-4 py-2 rounded-lg text-xs font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(124,58,237,0.1)', color: '#7C3AED', border: '1px solid rgba(124,58,237,0.2)' }}>
                        Chứng nhận
                      </Link>
                    </div>
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
