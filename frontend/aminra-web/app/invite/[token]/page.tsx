'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';

interface InviteInfo {
  email: string;
  business_name: string;
  role: string | null;
  department: string | null;
}

export default function InviteAcceptPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    fetch(`/api/auth/invite/${token}`)
      .then(r => {
        if (r.status === 410) throw new Error('Link đã hết hạn hoặc đã được sử dụng.');
        if (!r.ok) throw new Error('Link không hợp lệ.');
        return r.json();
      })
      .then(d => setInfo(d))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');
    if (password !== confirmPw) { setSubmitError('Mật khẩu xác nhận không khớp'); return; }
    if (password.length < 10) { setSubmitError('Mật khẩu phải có ít nhất 10 ký tự'); return; }

    setSubmitting(true);
    try {
      const res = await fetch(`/api/auth/invite/${token}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, display_name: displayName || info?.email }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || 'Có lỗi xảy ra');
      }
      setSuccess(true);
    } catch (err: any) {
      setSubmitError(err.message);
    } finally { setSubmitting(false); }
  };

  if (loading) return (
    <div className="min-h-screen grid place-items-center" style={{ background: '#F5F1E8' }}>
      <div className="flex items-center gap-1.5">
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
        <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
      </div>
    </div>
  );

  if (error) return (
    <div className="min-h-screen grid place-items-center p-6" style={{ background: '#F5F1E8' }}>
      <div className="max-w-md text-center">
        <div className="w-16 h-16 rounded-full grid place-items-center mx-auto mb-4" style={{ background: '#FEF2F2' }}>
          <svg className="w-8 h-8" style={{ color: '#DC2626' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h1 className="text-xl font-bold mb-2" style={{ color: '#0A1F44' }}>Không thể truy cập</h1>
        <p className="text-sm" style={{ color: '#6B7280' }}>{error}</p>
      </div>
    </div>
  );

  if (success) return (
    <div className="min-h-screen grid place-items-center p-6" style={{ background: '#F5F1E8' }}>
      <div className="max-w-md text-center">
        <div className="w-16 h-16 rounded-full grid place-items-center mx-auto mb-4" style={{ background: '#DCE3F0' }}>
          <svg className="w-8 h-8" style={{ color: '#102A5C' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-xl font-bold mb-2" style={{ color: '#0A1F44' }}>Tham gia thành công!</h1>
        <p className="text-sm mb-6" style={{ color: '#6B7280' }}>
          Bạn đã gia nhập <strong>{info?.business_name}</strong>. Đăng nhập để bắt đầu.
        </p>
        <Link href="/business/login"
          className="inline-block px-6 py-3 rounded-xl font-semibold text-white" style={{ background: '#0A1F44' }}>
          Đăng nhập ngay
        </Link>
      </div>
    </div>
  );

  if (!info) return null;

  const inputStyle = { background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0A1F44' };

  return (
    <div className="min-h-screen grid place-items-center p-6" style={{ background: '#F5F1E8' }} data-page>
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8 animate-section">
          <div className="w-14 h-14 rounded-2xl grid place-items-center mx-auto mb-4" style={{ background: '#0A1F44' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-9 h-9" />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: '#0A1F44' }}>Lời mời tham gia</h1>
          <p className="text-sm mt-2" style={{ color: '#6B7280' }}>
            <strong style={{ color: '#374151' }}>{info.business_name}</strong> mời bạn tham gia tổ chức trên AMINRA
          </p>
        </div>

        {/* Info */}
        <div className="rounded-2xl p-5 mb-6 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span style={{ color: '#6B7280' }}>Email</span>
              <span className="font-medium" style={{ color: '#0A1F44' }}>{info.email}</span>
            </div>
            {info.role && (
              <div className="flex justify-between">
                <span style={{ color: '#6B7280' }}>Vai trò</span>
                <span className="font-medium" style={{ color: '#0A1F44' }}>{info.role}</span>
              </div>
            )}
            {info.department && (
              <div className="flex justify-between">
                <span style={{ color: '#6B7280' }}>Phòng ban</span>
                <span className="font-medium" style={{ color: '#0A1F44' }}>{info.department}</span>
              </div>
            )}
          </div>
        </div>

        {/* Form */}
        <div className="rounded-2xl p-6 animate-section" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Họ tên</label>
              <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)}
                placeholder="VD: Nguyễn Văn A"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none" style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Tạo mật khẩu *</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Tối thiểu 10 ký tự, gồm hoa, thường, số" required
                className="w-full px-4 py-3 rounded-xl text-sm outline-none" style={inputStyle} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Xác nhận mật khẩu *</label>
              <input type="password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
                placeholder="Nhập lại mật khẩu" required
                className="w-full px-4 py-3 rounded-xl text-sm outline-none" style={inputStyle} />
            </div>

            {submitError && (
              <p className="text-xs px-3 py-2 rounded-lg" style={{ background: '#FEF2F2', color: '#DC2626', border: '1px solid #FECACA' }}>
                {submitError}
              </p>
            )}

            <button type="submit" disabled={submitting || !password || !confirmPw}
              className="w-full py-3 rounded-xl font-semibold text-sm text-white transition-all"
              style={{ background: (!password || !confirmPw) ? '#E2E8F0' : '#0A1F44', color: (!password || !confirmPw) ? '#9CA3AF' : '#fff' }}>
              {submitting ? 'Đang xử lý...' : 'Tham gia tổ chức'}
            </button>
          </form>
        </div>

        <p className="text-xs text-center mt-4" style={{ color: '#9CA3AF' }}>
          Bạn sẽ tham gia với vai trò thành viên của {info.business_name}
        </p>
      </div>
    </div>
  );
}
