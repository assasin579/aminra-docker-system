'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

interface Auditor {
  id: string; email: string; display_name: string;
  specialty: string | null; status: string; created_at: string;
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
  const [editData, setEditData] = useState({ display_name: '', specialty: '' });
  const [saving, setSaving] = useState(false);

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
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Tạo thất bại'); }
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
    setEditData({ display_name: a.display_name, specialty: a.specialty || '' });
  };

  const handleSave = async () => {
    if (!editId) return;
    setSaving(true);
    try {
      // Reuse the admin update user endpoint or create a dedicated one
      // For now update via direct fetch
      await fetch(`/api/auth/provider/auditors/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(editData),
      });
      setEditId(null);
      fetchAuditors();
    } finally { setSaving(false); }
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
        <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
          <div className="grid grid-flow-col items-center gap-3 justify-start">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)' }}>
              <svg className="w-5 h-5" style={{ color: '#fbbf24' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Quản lý Auditor</h1>
              <p className="text-sm" style={{ color: '#64748b' }}>{auditors.length} auditor · {user.company_name}</p>
            </div>
          </div>
          <button onClick={() => setShowInvite(true)}
            className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
            style={{ gridTemplateColumns: 'auto 1fr', background: 'linear-gradient(135deg, #15803d, #16a34a)', boxShadow: '0 4px 12px rgba(22,163,74,0.3)' }}>
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
            {[1, 2].map(i => <div key={i} className="rounded-2xl h-20 animate-pulse" style={{ background: '#162847', opacity: 1 - i * 0.2 }} />)}
          </div>
        ) : auditors.length === 0 ? (
          <div className="rounded-2xl p-12 text-center" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <p className="text-white font-semibold mb-2">Chưa có auditor nào</p>
            <p className="text-sm" style={{ color: '#475569' }}>Tạo auditor để gán đánh giá hồ sơ doanh nghiệp</p>
          </div>
        ) : (
          auditors.map(a => (
            <div key={a.id} className="rounded-xl p-4 transition-colors doc-card-hover"
              style={{ background: 'linear-gradient(135deg, #162847, #0f2236)', border: '1px solid #1e3a5f' }}>
              {editId === a.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#94a3b8' }}>Họ tên</label>
                      <input value={editData.display_name} onChange={e => setEditData(d => ({ ...d, display_name: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                        style={{ background: '#0a1929', border: '1px solid #1e3a5f' }} />
                    </div>
                    <div>
                      <label className="text-xs font-medium mb-1 block" style={{ color: '#94a3b8' }}>Chuyên môn</label>
                      <input value={editData.specialty} onChange={e => setEditData(d => ({ ...d, specialty: e.target.value }))}
                        placeholder="Food Safety, Halal..."
                        className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                        style={{ background: '#0a1929', border: '1px solid #1e3a5f' }} />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={handleSave} disabled={saving}
                      className="px-4 py-1.5 rounded-lg text-xs font-medium text-white"
                      style={{ background: '#16a34a' }}>
                      {saving ? 'Lưu...' : 'Lưu'}
                    </button>
                    <button onClick={() => setEditId(null)}
                      className="px-4 py-1.5 rounded-lg text-xs" style={{ color: '#64748b', border: '1px solid #1e3a5f' }}>
                      Huỷ
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                  <div className="w-10 h-10 rounded-full grid place-items-center text-sm font-bold"
                    style={{ background: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.25)' }}>
                    {a.display_name?.[0]?.toUpperCase() || '?'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-white">{a.display_name}</p>
                      {a.specialty && (
                        <span className="px-2.5 py-0.5 rounded-lg text-xs font-medium"
                          style={{ background: 'rgba(245,158,11,0.12)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.25)' }}>
                          {a.specialty}
                        </span>
                      )}
                    </div>
                    <p className="text-sm mt-0.5" style={{ color: '#475569' }}>{a.email}</p>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => startEdit(a)} title="Sửa"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
                      <svg className="w-4 h-4" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button onClick={() => handleRemove(a.id)} title="Xoá"
                      disabled={removeId === a.id}
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                      <svg className="w-4 h-4" style={{ color: '#64748b' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6"
            style={{ background: '#111725', border: '1px solid #1e3a5f', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>
            <div className="grid items-center mb-5" style={{ gridTemplateColumns: '1fr auto' }}>
              <h3 className="text-base font-bold text-white">Thêm Auditor</h3>
              <button onClick={() => setShowInvite(false)}
                className="w-8 h-8 rounded-lg grid place-items-center" style={{ background: 'rgba(255,255,255,0.05)' }}>
                <span className="text-slate-400 hover:text-white">✕</span>
              </button>
            </div>
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Họ tên *</label>
                <input type="text" required value={invite.display_name}
                  onChange={e => setInvite(i => ({ ...i, display_name: e.target.value }))}
                  placeholder="Nguyễn Văn A"
                  className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                  style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Chuyên môn</label>
                <input value={invite.specialty}
                  onChange={e => setInvite(i => ({ ...i, specialty: e.target.value }))}
                  placeholder="Food Safety, Halal Compliance..."
                  className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                  style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Email *</label>
                <input type="email" required value={invite.email}
                  onChange={e => setInvite(i => ({ ...i, email: e.target.value }))}
                  placeholder="auditor@org.vn"
                  className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                  style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Mật khẩu *</label>
                <input type="password" required value={invite.password}
                  onChange={e => setInvite(i => ({ ...i, password: e.target.value }))}
                  placeholder="Tối thiểu 8 ký tự"
                  className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                  style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
              </div>
              {inviteError && <p className="text-xs text-red-400">{inviteError}</p>}
              <button type="submit" disabled={inviting}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{ background: inviting ? '#1e3a5f' : 'linear-gradient(135deg, #15803d, #16a34a)' }}>
                {inviting ? 'Đang tạo...' : 'Tạo Auditor'}
              </button>
              <p className="text-xs text-center" style={{ color: '#334155' }}>
                Auditor đăng nhập bằng email + mật khẩu trên, tại cổng Tổ chức.
              </p>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
