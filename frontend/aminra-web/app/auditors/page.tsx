'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';
import { openAuthed } from '@/lib/authedOpen';
import { parseApiError } from '@/lib/apiError';

interface Auditor {
  id: string; email: string; display_name: string;
  specialty: string | null; status: string; created_at: string;
}

interface Certificate {
  id: string; filename: string; size: number; uploaded_at: string;
}

export default function AuditorsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const [auditors, setAuditors] = useState<Auditor[]>([]);
  const [fetching, setFetching] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [invite, setInvite] = useState({ email: '', password: '', display_name: '', specialty: '' });
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState('');
  const [removeId, setRemoveId] = useState<string | null>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ display_name: '', specialty: '', email: '', password: '' });
  const [saving, setSaving] = useState(false);

  // Certificates
  const [certsOpen, setCertsOpen] = useState<string | null>(null); // auditor id
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [certsLoading, setCertsLoading] = useState(false);
  const [certUploading, setCertUploading] = useState(false);
  const certInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loading && (!isAuthenticated || user?.role !== 'provider' || !user?.is_owner))
      router.replace(user?.role === 'provider' ? '/dashboard/provider' : '/provider/login');
  }, [loading, isAuthenticated, user, router]);

  const fetchAuditors = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch('/api/auth/provider/auditors', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setAuditors(d.auditors || []); }
    } finally { setFetching(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchAuditors(); }, [isAuthenticated, fetchAuditors]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(''); setInviting(true);
    try {
      const res = await fetch('/api/auth/provider/auditors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(invite),
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(parseApiError(err, 'Tạo thất bại')); }
      setShowInvite(false);
      setInvite({ email: '', password: '', display_name: '', specialty: '' });
      fetchAuditors();
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : 'Lỗi');
    } finally { setInviting(false); }
  };

  const handleRemove = async (id: string) => {
    if (!confirm('Xác nhận xoá auditor này?')) return;
    setRemoveId(id);
    try {
      await fetch(`/api/auth/provider/auditors/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      fetchAuditors();
    } finally { setRemoveId(null); }
  };

  const startEdit = (a: Auditor) => {
    setEditId(a.id);
    setEditData({ display_name: a.display_name, specialty: a.specialty || '', email: a.email, password: '' });
  };

  const handleSave = async () => {
    if (!editId) return;
    setSaving(true);
    try {
      // Reuse the admin update user endpoint or create a dedicated one
      // For now update via direct fetch
      const payload: Record<string, string> = { display_name: editData.display_name, specialty: editData.specialty, email: editData.email };
      if (editData.password) payload.password = editData.password;
      await fetch(`/api/auth/provider/auditors/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      setEditId(null);
      fetchAuditors();
    } finally { setSaving(false); }
  };

  // Certificate management
  const openCerts = async (auditorId: string) => {
    setCertsOpen(auditorId);
    setCertsLoading(true);
    try {
      const res = await fetch(`/api/auth/provider/auditors/${auditorId}/certificates`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) { const d = await res.json(); setCerts(d.certificates || []); }
    } finally { setCertsLoading(false); }
  };

  const uploadCert = async (auditorId: string, file: File) => {
    setCertUploading(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch(`/api/auth/provider/auditors/${auditorId}/certificates`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); alert(e.detail || 'Upload thất bại'); return; }
      openCerts(auditorId);
    } finally {
      setCertUploading(false);
      if (certInputRef.current) certInputRef.current.value = '';
    }
  };

  const viewCert = (auditorId: string, certId: string) => {
    openAuthed(`/api/auth/provider/auditors/${auditorId}/certificates/${certId}/view`, token || '');
  };

  const deleteCert = async (auditorId: string, certId: string) => {
    if (!confirm('Xác nhận xoá chứng chỉ này?')) return;
    await fetch(`/api/auth/provider/auditors/${auditorId}/certificates/${certId}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
    });
    openCerts(auditorId);
  };

  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="flex items-center gap-1.5">
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
      </div>
    </div>
  );

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden" data-page>
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
        <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
          <div className="grid grid-flow-col items-center gap-3 justify-start">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)' }}>
              <svg className="w-5 h-5" style={{ color: '#F59E0B' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#0F5132' }}>Quản lý Auditor</h1>
              <p className="text-sm" style={{ color: '#6B7280' }}>{auditors.length} auditor · {user.company_name}</p>
            </div>
          </div>
          <button onClick={() => setShowInvite(true)}
            className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
            style={{ gridTemplateColumns: 'auto 1fr', background: '#0F5132', boxShadow: '0 4px 12px rgba(15,81,50,0.3)' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
            </svg>
            Thêm Auditor
          </button>
        </div>
      </div>

      {/* Auditor list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2].map(i => <div key={i} className="rounded-2xl h-20 animate-pulse" style={{ background: '#F7F1E6', opacity: 1 - i * 0.2 }} />)}
          </div>
        ) : auditors.length === 0 ? (
          <div className="rounded-2xl p-12 text-center" style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
            <p className="font-semibold mb-2" style={{ color: '#0F5132' }}>Chưa có auditor nào</p>
            <p className="text-sm" style={{ color: '#6B7280' }}>Tạo auditor để gán đánh giá hồ sơ doanh nghiệp</p>
          </div>
        ) : (
          auditors.map((a, idx) => (
            <div key={a.id} className={`rounded-xl p-4 transition-colors doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
              style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
              {editId === a.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#6B7280' }}>Họ tên</label>
                      <input value={editData.display_name} onChange={e => setEditData(d => ({ ...d, display_name: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
                    </div>
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#6B7280' }}>Chuyên môn</label>
                      <input value={editData.specialty} onChange={e => setEditData(d => ({ ...d, specialty: e.target.value }))}
                        placeholder="Food Safety, Halal..."
                        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
                    </div>
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#6B7280' }}>Email</label>
                      <input type="email" value={editData.email} onChange={e => setEditData(d => ({ ...d, email: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
                    </div>
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#6B7280' }}>Mật khẩu mới</label>
                      <input type="password" value={editData.password} onChange={e => setEditData(d => ({ ...d, password: e.target.value }))}
                        placeholder="Để trống nếu không đổi"
                        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={handleSave} disabled={saving}
                      className="px-4 py-1.5 rounded-lg text-xs font-medium text-white"
                      style={{ background: '#0F5132' }}>
                      {saving ? 'Lưu...' : 'Lưu'}
                    </button>
                    <button onClick={() => setEditId(null)}
                      className="px-4 py-1.5 rounded-lg text-xs" style={{ color: '#6B7280', border: '1px solid #E2E8F0' }}>
                      Huỷ
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                  <div className="w-10 h-10 rounded-full grid place-items-center text-sm font-bold"
                    style={{ background: 'rgba(245,158,11,0.15)', color: '#F59E0B', border: '1px solid rgba(245,158,11,0.25)' }}>
                    {a.display_name?.[0]?.toUpperCase() || '?'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold" style={{ color: '#0F5132' }}>{a.display_name}</p>
                      {a.specialty && (
                        <span className="px-2.5 py-0.5 rounded-lg text-xs font-medium"
                          style={{ background: 'rgba(245,158,11,0.12)', color: '#F59E0B', border: '1px solid rgba(245,158,11,0.25)' }}>
                          {a.specialty}
                        </span>
                      )}
                    </div>
                    <p className="text-sm mt-0.5" style={{ color: '#6B7280' }}>
                      {a.email}
                      <span className="ml-2 px-2 py-0.5 rounded text-xs" style={{ background: '#DBEAFE', color: '#2563EB' }}>Thành viên</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => openCerts(a.id)} title="Chứng chỉ"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
                      <svg className="w-4 h-4" style={{ color: '#B45309' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </button>
                    <button onClick={() => startEdit(a)} title="Sửa"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(14,165,233,0.1)', border: '1px solid rgba(14,165,233,0.2)' }}>
                      <svg className="w-4 h-4" style={{ color: '#0EA5E9' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button onClick={() => handleRemove(a.id)} title="Xoá"
                      disabled={removeId === a.id}
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                      <svg className="w-4 h-4" style={{ color: '#6B7280' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 25px 60px rgba(0,0,0,0.15)' }}>
            <div className="grid items-center mb-5" style={{ gridTemplateColumns: '1fr auto' }}>
              <h3 className="text-base font-bold" style={{ color: '#0F5132' }}>Thêm Auditor</h3>
              <button onClick={() => setShowInvite(false)}
                className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: 'rgba(0,0,0,0.05)' }}>
                <span className="hover:text-gray-700">✕</span>
              </button>
            </div>
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Họ tên *</label>
                <input type="text" required value={invite.display_name}
                  onChange={e => setInvite(i => ({ ...i, display_name: e.target.value }))}
                  placeholder="Nguyễn Văn A"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Chuyên môn</label>
                <input value={invite.specialty}
                  onChange={e => setInvite(i => ({ ...i, specialty: e.target.value }))}
                  placeholder="Food Safety, Halal Compliance..."
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Email *</label>
                <input type="email" required value={invite.email}
                  onChange={e => setInvite(i => ({ ...i, email: e.target.value }))}
                  placeholder="auditor@org.vn"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#6B7280' }}>Mật khẩu *</label>
                <input type="password" required value={invite.password}
                  onChange={e => setInvite(i => ({ ...i, password: e.target.value }))}
                  placeholder="Tối thiểu 8 ký tự"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }} />
              </div>
              {inviteError && <p className="text-xs text-red-400">{inviteError}</p>}
              <button type="submit" disabled={inviting}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{ background: inviting ? '#E2E8F0' : '#0F5132', color: inviting ? '#6B7280' : 'white' }}>
                {inviting ? 'Đang tạo...' : 'Tạo Auditor'}
              </button>
              <p className="text-xs text-center" style={{ color: '#94A3B8' }}>
                Auditor đăng nhập bằng email + mật khẩu trên, tại cổng Tổ chức.
              </p>
            </form>
          </div>
        </div>
      )}

      {/* Certificates modal */}
      {certsOpen && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }}
          onClick={() => setCertsOpen(null)}>
          <div className="w-full max-w-lg rounded-2xl animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 25px 60px rgba(0,0,0,0.1)', maxHeight: 'calc(100vh - 4rem)' }}
            onClick={e => e.stopPropagation()}>

            {/* Header */}
            <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid #E2E8F0' }}>
              <div>
                <h3 className="text-base font-bold" style={{ color: '#0F5132' }}>Chứng chỉ & Bằng cấp</h3>
                <p className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
                  {auditors.find(a => a.id === certsOpen)?.display_name}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input ref={certInputRef} type="file" className="hidden" accept=".pdf,.docx,.jpg,.jpeg,.png"
                  onChange={e => { const f = e.target.files?.[0]; if (f && certsOpen) uploadCert(certsOpen, f); }} />
                <button onClick={() => certInputRef.current?.click()} disabled={certUploading}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-all"
                  style={{ background: '#0F5132' }}>
                  {certUploading ? 'Đang upload...' : 'Upload chứng chỉ'}
                </button>
                <button onClick={() => setCertsOpen(null)}
                  className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: 'rgba(0,0,0,0.05)' }}>
                  <span style={{ color: '#6B7280' }}>✕</span>
                </button>
              </div>
            </div>

            {/* Certificate list */}
            <div className="px-6 py-4 space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 12rem)' }}>
              {certsLoading ? (
                <div className="flex items-center justify-center gap-1.5 py-8">
                  <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
                  <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
                  <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
                </div>
              ) : certs.length === 0 ? (
                <div className="py-12 text-center">
                  <svg className="w-12 h-12 mx-auto mb-3" style={{ color: '#E2E8F0' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-sm font-medium" style={{ color: '#374151' }}>Chưa có chứng chỉ nào</p>
                  <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>Upload bằng đại học, chứng chỉ đào tạo, giấy phép hành nghề,...</p>
                </div>
              ) : (
                certs.map(c => (
                  <div key={c.id} className="flex items-center gap-3 px-4 py-3 rounded-xl group"
                    style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-lg grid place-items-center flex-shrink-0"
                      style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
                      <svg className="w-5 h-5" style={{ color: '#B45309' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: '#0F5132' }}>{c.filename}</p>
                      <p className="text-xs" style={{ color: '#9CA3AF' }}>
                        {(c.size / 1024).toFixed(0)} KB · {new Date(c.uploaded_at + 'Z').toLocaleDateString('vi-VN')}
                      </p>
                    </div>
                    {/* Actions */}
                    <div className="flex items-center gap-1">
                      <button onClick={() => viewCert(certsOpen!, c.id)} title="Xem"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: '#F0F9FF', border: '1px solid #BAE6FD' }}>
                        <svg className="w-4 h-4" style={{ color: '#0369A1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      <button onClick={() => deleteCert(certsOpen!, c.id)} title="Xoá"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110 opacity-0 group-hover:opacity-100"
                        style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                        <svg className="w-4 h-4" style={{ color: '#DC2626' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Footer hint */}
            <div className="px-6 py-3" style={{ borderTop: '1px solid #E2E8F0' }}>
              <p className="text-xs" style={{ color: '#9CA3AF' }}>Hỗ trợ: PDF, DOCX, JPG, PNG · Tối đa 10MB</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
