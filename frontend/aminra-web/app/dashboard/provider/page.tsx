'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useUserAuth } from '@/components/UserAuthContext';

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Chào buổi sáng';
  if (h < 18) return 'Chào buổi chiều';
  return 'Chào buổi tối';
}

export default function ProviderDashboard() {
  const router = useRouter();
  const { user, isAuthenticated, loading, logout } = useUserAuth();

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider')) {
      router.replace('/provider/login');
    }
  }, [loading, isAuthenticated, user, router]);

  if (loading || !user) {
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="text-slate-400 text-sm">Đang tải...</div>
      </div>
    );
  }

  const isAdmin = user.email === 'admin@aminra.com';

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full">
      {/* Header */}
      <div className="grid items-start mb-6" style={{ gridTemplateColumns: '1fr auto' }}>
        <div>
          <p className="text-sm mb-1" style={{ color: '#64748b' }}>{greeting()},</p>
          <h1 className="text-2xl font-bold text-white">{user.company_name}</h1>
          <div className="grid grid-flow-col items-center gap-3 mt-2 justify-start">
            <p className="text-slate-500 text-sm">{user.email}</p>
            <span className="inline-grid items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
              style={{
                gridTemplateColumns: 'auto 1fr',
                background: user.status === 'active' ? 'rgba(37,99,235,0.1)' : 'rgba(245,158,11,0.1)',
                color: user.status === 'active' ? '#60a5fa' : '#fbbf24',
                border: `1px solid ${user.status === 'active' ? 'rgba(37,99,235,0.3)' : 'rgba(245,158,11,0.3)'}`,
              }}>
              <span className={`w-1.5 h-1.5 rounded-full inline-block ${user.status === 'active' ? 'bg-blue-400' : 'bg-yellow-400'}`} />
              {user.status === 'active' ? 'Đã xác nhận' : 'Đang chờ duyệt'}
            </span>
          </div>
        </div>
        <button onClick={() => { logout(); router.push('/'); }}
          className="text-xs text-slate-400 hover:text-red-400 transition-colors px-3 py-2 rounded-lg"
          style={{ border: '1px solid #1e3a5f' }}>
          Đăng xuất
        </button>
      </div>

      {/* Pending notice */}
      {user.status === 'pending' && (
        <div className="mb-6 p-5 rounded-xl"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
          <div className="grid items-start gap-3" style={{ gridTemplateColumns: '1.25rem 1fr' }}>
            <svg className="w-5 h-5 mt-0.5" style={{ color: '#fbbf24' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium" style={{ color: '#fbbf24' }}>Tài khoản đang chờ xét duyệt</p>
              <p className="text-xs text-slate-400 mt-1">
                Đội ngũ AMINRA đang xem xét hồ sơ của tổ chức bạn. Trong thời gian chờ, bạn có thể khám phá tính năng AI.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Welcome card */}
      <div className="rounded-2xl p-6 mb-6"
        style={{ background: 'linear-gradient(135deg, #0f2236, #162847)', border: '1px solid #1e3a5f' }}>
        <div className="grid items-center gap-4" style={{ gridTemplateColumns: 'auto 1fr' }}>
          <div className="w-14 h-14 rounded-2xl grid place-items-center"
            style={{ background: 'rgba(37,99,235,0.15)', border: '1px solid rgba(37,99,235,0.3)' }}>
            <svg className="w-7 h-7" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Cổng dành cho Tổ chức chứng nhận</h2>
            <p className="text-sm mt-1" style={{ color: '#94a3b8' }}>
              Quản lý tiêu chuẩn, đánh giá doanh nghiệp và hỗ trợ quy trình chứng nhận Halal
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-2 gap-4">
        <Link href="/"
          className="grid items-center gap-4 p-5 rounded-xl transition-all hover:scale-[1.01]"
          style={{ gridTemplateColumns: '2.5rem 1fr', background: '#162847', border: '1px solid #1e3a5f' }}>
          <div className="w-10 h-10 rounded-xl grid place-items-center"
            style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
            <svg className="w-5 h-5" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Hỏi đáp AI</div>
            <div className="text-xs text-slate-400 mt-0.5">Tra cứu tiêu chuẩn Halal</div>
          </div>
        </Link>

        <Link href="/upload"
          className="grid items-center gap-4 p-5 rounded-xl transition-all hover:scale-[1.01]"
          style={{ gridTemplateColumns: '2.5rem 1fr', background: '#162847', border: '1px solid #1e3a5f' }}>
          <div className="w-10 h-10 rounded-xl grid place-items-center"
            style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>
            <svg className="w-5 h-5" style={{ color: '#4ade80' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Đánh giá tài liệu</div>
            <div className="text-xs text-slate-400 mt-0.5">Upload & phân tích compliance</div>
          </div>
        </Link>

        {isAdmin && (
          <Link href="/admin"
            className="grid items-center gap-4 p-5 rounded-xl transition-all hover:scale-[1.01]"
            style={{ gridTemplateColumns: '2.5rem 1fr', background: '#162847', border: '1px solid #1e3a5f' }}>
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}>
              <svg className="w-5 h-5" style={{ color: '#fbbf24' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-white">Quản trị hệ thống</div>
              <div className="text-xs text-slate-400 mt-0.5">Template, users & phê duyệt</div>
            </div>
          </Link>
        )}
      </div>
    </div>
  );
}
