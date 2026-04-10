'use client';

import { useState, useEffect, useRef } from 'react';
import { useUserAuth } from '@/components/UserAuthContext';
import Link from 'next/link';

export default function SettingsPage() {
  const { user, token, isAuthenticated } = useUserAuth();

  const [loading, setLoading] = useState(true);

  // Password
  const [pwForm, setPwForm] = useState({ current: '', newPw: '', confirm: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  // Notifications
  const [notif, setNotif] = useState({ notify_eval_done: true, notify_submission_reply: true });
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);

  // Logo
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const logoRef = useRef<HTMLInputElement>(null);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    setLoading(true);
    Promise.all([
      fetch('/api/auth/notification-preferences', { headers }).then(r => r.ok ? r.json() : null),
    ]).then(([notifData]) => {
      if (notifData) setNotif(notifData);
      if (user?.tenant_id) setLogoUrl(`/api/auth/company-logo/${user.tenant_id}`);
    }).finally(() => setLoading(false));
  }, [isAuthenticated, token]);

  const handleChangePassword = async () => {
    setPwMsg(null);
    if (pwForm.newPw !== pwForm.confirm) { setPwMsg({ type: 'err', text: 'Mật khẩu xác nhận không khớp' }); return; }
    setPwSaving(true);
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: pwForm.current, new_password: pwForm.newPw }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Đổi mật khẩu thất bại'); }
      setPwMsg({ type: 'ok', text: 'Đã đổi mật khẩu thành công' });
      setPwForm({ current: '', newPw: '', confirm: '' });
    } catch (err: unknown) {
      setPwMsg({ type: 'err', text: err instanceof Error ? err.message : 'Lỗi' });
    } finally { setPwSaving(false); }
  };

  const handleNotifSave = async () => {
    setNotifSaving(true); setNotifSaved(false);
    try {
      await fetch('/api/auth/notification-preferences', {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(notif),
      });
      setNotifSaved(true);
      setTimeout(() => setNotifSaved(false), 3000);
    } finally { setNotifSaving(false); }
  };

  const handleLogoUpload = async (file: File) => {
    setLogoUploading(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch('/api/auth/company-logo', { method: 'POST', headers, body: fd });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Upload thất bại'); }
      setLogoUrl(`/api/auth/company-logo/${user?.tenant_id}?t=${Date.now()}`);
    } catch (err: unknown) { alert(err instanceof Error ? err.message : 'Upload thất bại'); }
    finally { setLogoUploading(false); }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="text-center space-y-4">
          <p style={{ color: '#6B7280' }}>Vui lòng đăng nhập</p>
          <Link href="/business/login" className="inline-block px-6 py-3 rounded-xl font-semibold text-white" style={{ background: '#087653' }}>Đăng nhập</Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
        </div>
      </div>
    );
  }

  const isOwner = user?.is_owner;
  const cardStyle = { background: '#FFFFFF', border: '1px solid #E2E8F0' };
  const inputStyle = { background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' };

  return (
    <div data-page style={{ background: '#FAFCF9' }}>
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">

        <div className="rounded-2xl p-6 mb-6 animate-section" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center" style={{ background: 'rgba(8,118,83,0.12)', border: '1px solid rgba(8,118,83,0.25)' }}>
              <svg className="w-5 h-5" style={{ color: '#087653' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#1A2332' }}>Cài đặt tài khoản</h1>
              <p className="text-sm" style={{ color: '#6B7280' }}>Bảo mật, thông báo và cá nhân hóa</p>
            </div>
          </div>
        </div>

        {/* ── Logo công ty ── */}
        {isOwner && (
          <div className="animate-section rounded-2xl p-6 doc-card-hover" style={cardStyle}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#1A2332' }}>Logo công ty</h2>
            <div className="flex items-center gap-4">
              <div className="w-20 h-20 rounded-xl grid place-items-center overflow-hidden"
                style={{ background: '#FAFCF9', border: '2px dashed #E2E8F0' }}>
                {logoUrl ? (
                  <img src={logoUrl} alt="Logo" className="w-full h-full object-contain" onError={() => setLogoUrl(null)} />
                ) : (
                  <svg className="w-8 h-8" style={{ color: '#D1D5DB' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                )}
              </div>
              <div>
                <input ref={logoRef} type="file" className="hidden" accept="image/png,image/jpeg,image/webp"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleLogoUpload(f); }} />
                <button onClick={() => logoRef.current?.click()} disabled={logoUploading}
                  className="px-4 py-2 rounded-lg text-xs font-medium transition-all"
                  style={{ background: 'rgba(8,118,83,0.1)', color: '#087653', border: '1px solid rgba(8,118,83,0.2)' }}>
                  {logoUploading ? 'Đang upload...' : 'Thay đổi logo'}
                </button>
                <p className="text-xs mt-1.5" style={{ color: '#9CA3AF' }}>PNG, JPG hoặc WebP. Tối đa 2MB.</p>
              </div>
            </div>
          </div>
        )}

        {/* ── Đổi mật khẩu ── */}
        <div className="animate-section rounded-2xl p-6 space-y-4 doc-card-hover" style={cardStyle}>
          <h2 className="text-sm font-semibold" style={{ color: '#1A2332' }}>Đổi mật khẩu</h2>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Mật khẩu hiện tại</label>
            <input type="password" value={pwForm.current} onChange={e => setPwForm(p => ({ ...p, current: e.target.value }))}
              placeholder="Nhập mật khẩu hiện tại" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Mật khẩu mới</label>
            <input type="password" value={pwForm.newPw} onChange={e => setPwForm(p => ({ ...p, newPw: e.target.value }))}
              placeholder="Tối thiểu 10 ký tự, gồm hoa, thường, số" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Xác nhận mật khẩu mới</label>
            <input type="password" value={pwForm.confirm} onChange={e => setPwForm(p => ({ ...p, confirm: e.target.value }))}
              placeholder="Nhập lại mật khẩu mới" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
          </div>
          {pwMsg && (
            <div className="px-3 py-2 rounded-lg text-xs animate-toast"
              style={pwMsg.type === 'ok'
                ? { background: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669' }
                : { background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626' }}>
              {pwMsg.text}
            </div>
          )}
          <button onClick={handleChangePassword} disabled={pwSaving || !pwForm.current || !pwForm.newPw || !pwForm.confirm}
            className="w-full py-2.5 rounded-xl font-semibold text-sm transition-all text-white"
            style={{ background: (!pwForm.current || !pwForm.newPw || !pwForm.confirm) ? '#E2E8F0' : '#087653',
                     color: (!pwForm.current || !pwForm.newPw || !pwForm.confirm) ? '#9CA3AF' : '#fff' }}>
            {pwSaving ? 'Đang xử lý...' : 'Đổi mật khẩu'}
          </button>
        </div>

        {/* ── Thông báo ── */}
        <div className="animate-section rounded-2xl p-6 space-y-4 doc-card-hover" style={cardStyle}>
          <h2 className="text-sm font-semibold" style={{ color: '#1A2332' }}>Thông báo</h2>
          {[
            { key: 'notify_eval_done' as const, label: 'Đánh giá tài liệu hoàn tất', desc: 'Nhận thông báo khi AI hoàn thành đánh giá' },
            { key: 'notify_submission_reply' as const, label: 'Phản hồi hồ sơ', desc: 'Nhận thông báo khi tổ chức chứng nhận phản hồi' },
          ].map(item => (
            <div key={item.key} className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl"
              style={{ background: '#FAFCF9', border: '1px solid #E2E8F0' }}>
              <div>
                <p className="text-sm font-medium" style={{ color: '#1A2332' }}>{item.label}</p>
                <p className="text-xs mt-0.5" style={{ color: '#9CA3AF' }}>{item.desc}</p>
              </div>
              <button onClick={() => setNotif(n => ({ ...n, [item.key]: !n[item.key] }))}
                className="w-11 h-6 rounded-full transition-colors duration-200 relative flex-shrink-0"
                style={{ background: notif[item.key] ? '#087653' : '#E2E8F0' }}>
                <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200"
                  style={{ transform: notif[item.key] ? 'translateX(22px)' : 'translateX(2px)' }} />
              </button>
            </div>
          ))}
          {notifSaved && (
            <div className="px-3 py-2 rounded-lg text-xs animate-toast" style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', color: '#059669' }}>Đã lưu</div>
          )}
          <button onClick={handleNotifSave} disabled={notifSaving}
            className="w-full py-2.5 rounded-xl font-semibold text-sm transition-all text-white"
            style={{ background: notifSaving ? '#E2E8F0' : '#087653' }}>
            {notifSaving ? 'Đang lưu...' : 'Lưu cài đặt thông báo'}
          </button>
        </div>

        <div className="pb-6" />
      </div>
    </div>
  );
}
