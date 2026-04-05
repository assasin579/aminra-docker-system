'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

interface Member {
  id: string; email: string; display_name: string;
  ihc_role: string | null; department: string | null;
  status: string; created_at: string;
}

const DEFAULT_ROLES = ['Chairman', 'Halal Executive', 'Trưởng phòng', 'Thành viên'];

interface MinutesItem {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  mime_type: string;
  uploaded_at: string;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function MembersPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [fetching, setFetching] = useState(false);

  // Invite
  const [showInvite, setShowInvite] = useState(false);
  const [invite, setInvite] = useState({ email: '', password: '', display_name: '', ihc_role: '', department: '' });
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState('');

  // Edit
  const [editId, setEditId] = useState<string | null>(null);
  const [editData, setEditData] = useState({ ihc_role: '', department: '', display_name: '' });
  const [saving, setSaving] = useState(false);

  const [removeId, setRemoveId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<'members' | 'minutes'>('members');

  // Minutes
  const [minutes, setMinutes] = useState<MinutesItem[]>([]);
  const [fetchingMinutes, setFetchingMinutes] = useState(false);
  const [uploadingMinutes, setUploadingMinutes] = useState(false);
  const [deletingMinuteId, setDeletingMinuteId] = useState<string | null>(null);
  const minutesInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loading && !isAuthenticated) router.replace('/business/login');
    else if (!loading && isAuthenticated && (user?.role !== 'business' || !user?.is_owner))
      router.replace(user?.role === 'provider' ? '/dashboard/provider' : '/');
  }, [loading, isAuthenticated, user, router]);

  const fetchMembers = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch('/api/auth/business/members', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setMembers(d.members); }
    } finally { setFetching(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated) fetchMembers(); }, [isAuthenticated, fetchMembers]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(''); setInviting(true);
    try {
      const res = await fetch('/api/auth/business/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(invite),
      });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || 'Mời thất bại'); }
      setShowInvite(false);
      setInvite({ email: '', password: '', display_name: '', ihc_role: '', department: '' });
      fetchMembers();
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : 'Lỗi');
    } finally { setInviting(false); }
  };

  const startEdit = (m: Member) => {
    setEditId(m.id);
    setEditData({ ihc_role: m.ihc_role || '', department: m.department || '', display_name: m.display_name });
  };

  const handleSave = async () => {
    if (!editId) return;
    setSaving(true);
    try {
      await fetch(`/api/auth/business/members/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(editData),
      });
      setEditId(null);
      fetchMembers();
    } finally { setSaving(false); }
  };

  const handleRemove = async (id: string) => {
    if (!confirm('Xác nhận xoá thành viên này?')) return;
    setRemoveId(id);
    try {
      await fetch(`/api/auth/business/members/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      fetchMembers();
    } finally { setRemoveId(null); }
  };

  const handleExportIHC = async () => {
    setExporting(true);
    try {
      const res = await fetch('/api/auth/business/export-ihc', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Export thất bại');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const cd = res.headers.get('Content-Disposition') || '';
      a.href = url; a.download = cd.match(/filename="([^"]+)"/)?.[1] || 'IHC_Document.docx'; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { alert(e.message); }
    finally { setExporting(false); }
  };

  // Minutes functions
  const fetchMinutes = useCallback(async () => {
    if (!token) return;
    setFetchingMinutes(true);
    try {
      const res = await fetch('/api/auth/business/minutes', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) { const d = await res.json(); setMinutes(d.minutes || []); }
    } finally { setFetchingMinutes(false); }
  }, [token]);

  useEffect(() => { if (isAuthenticated && activeTab === 'minutes') fetchMinutes(); }, [isAuthenticated, activeTab, fetchMinutes]);

  const handleUploadMinutes = async (file: File) => {
    setUploadingMinutes(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch('/api/auth/business/minutes', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
      });
      if (!res.ok) throw new Error('Upload thất bại');
      fetchMinutes();
    } catch (e: any) { alert(e.message); }
    finally {
      setUploadingMinutes(false);
      if (minutesInputRef.current) minutesInputRef.current.value = '';
    }
  };

  const viewMinutes = (fileId: string) => {
    window.open(`/api/auth/business/minutes/${fileId}/view?token=${encodeURIComponent(token || '')}`, '_blank');
  };

  const deleteMinutes = async (fileId: string) => {
    if (!confirm('Xác nhận xoá biên bản này?')) return;
    setDeletingMinuteId(fileId);
    try {
      await fetch(`/api/auth/business/minutes/${fileId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
      fetchMinutes();
    } finally { setDeletingMinuteId(null); }
  };

  if (loading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="text-slate-400 text-sm">Đang tải...</div>
    </div>
  );

  const MAX = 7;
  const roleGroups = new Map<string, Member[]>();
  members.forEach(m => {
    const role = m.ihc_role || 'Chưa phân vai trò';
    if (!roleGroups.has(role)) roleGroups.set(role, []);
    roleGroups.get(role)!.push(m);
  });

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden">
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6"
        style={{ background: 'linear-gradient(135deg, #0f2236, #162847)', border: '1px solid #1e3a5f' }}>
        <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
          <div className="grid grid-flow-col items-center gap-3 justify-start">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}>
              <svg className="w-5 h-5" style={{ color: '#818cf8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Internal Halal Committee</h1>
              <p className="text-sm" style={{ color: '#64748b' }}>
                {members.length}/{MAX} thành viên · {user.company_name}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleExportIHC} disabled={exporting || members.length === 0}
              className="grid items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all hover:scale-105 disabled:opacity-40"
              style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(37,99,235,0.15)', color: '#60a5fa', border: '1px solid rgba(37,99,235,0.3)' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {exporting ? 'Đang xuất...' : 'Xuất tài liệu IHC'}
            </button>
            {members.length < MAX && (
              <button onClick={() => setShowInvite(true)}
                className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: 'linear-gradient(135deg, #15803d, #16a34a)', boxShadow: '0 4px 12px rgba(22,163,74,0.3)' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
                </svg>
                Mời thành viên
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-2 gap-2 mb-5">
        {([
          { id: 'members' as const, label: 'Thành viên', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
          { id: 'minutes' as const, label: 'Biên bản họp', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
        ]).map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className="grid grid-flow-col items-center gap-2 justify-center py-3 rounded-xl text-sm font-medium transition-all"
            style={{
              background: activeTab === tab.id ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.03)',
              color: activeTab === tab.id ? '#a5b4fc' : '#64748b',
              border: `1px solid ${activeTab === tab.id ? 'rgba(99,102,241,0.3)' : '#1e3a5f'}`,
            }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={tab.icon} />
            </svg>
            {tab.label}
            {tab.id === 'minutes' && minutes.length > 0 && (
              <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: 'rgba(99,102,241,0.2)', color: '#818cf8' }}>
                {minutes.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab: Members ── */}
      {activeTab === 'members' && (<>

      {/* Owner card */}
      <div className="rounded-xl p-4 mb-4 doc-card-hover"
        style={{ background: 'linear-gradient(135deg, #162847, #0f2236)', border: '1px solid rgba(34,197,94,0.3)' }}>
        <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
          <div className="w-10 h-10 rounded-full grid place-items-center text-sm font-bold"
            style={{ background: 'rgba(34,197,94,0.15)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)' }}>
            {user.company_name?.[0]?.toUpperCase() || 'O'}
          </div>
          <div>
            <p className="text-sm font-semibold text-white">{user.email}</p>
            <p className="text-sm" style={{ color: '#64748b' }}>Chủ tài khoản</p>
          </div>
          <span className="px-3 py-1 rounded-lg text-xs font-bold"
            style={{ background: 'rgba(34,197,94,0.12)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.25)' }}>
            Owner
          </span>
        </div>
      </div>

      {/* Member list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="rounded-2xl h-20 animate-pulse" style={{ background: '#162847', opacity: 1 - i * 0.2 }} />
            ))}
          </div>
        ) : members.length === 0 ? (
          <div className="rounded-2xl p-12 text-center" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <svg className="w-16 h-16 mx-auto mb-4" style={{ color: '#1e3a5f' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <p className="text-white font-semibold mb-2">Chưa có thành viên IHC</p>
            <p className="text-sm mb-4" style={{ color: '#475569' }}>Mời thành viên và phân vai trò trong Internal Halal Committee</p>
          </div>
        ) : (
          members.map((m, i) => {
            const isEditing = editId === m.id;
            return (
              <div key={m.id} className="rounded-xl p-4 transition-colors doc-card-hover"
                style={{ background: 'linear-gradient(135deg, #162847, #0f2236)', border: '1px solid #1e3a5f' }}>
                {isEditing ? (
                  /* Edit mode */
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#94a3b8' }}>Họ tên</label>
                        <input value={editData.display_name} onChange={e => setEditData(d => ({ ...d, display_name: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                          style={{ background: '#0a1929', border: '1px solid #1e3a5f' }} />
                      </div>
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#94a3b8' }}>Vai trò IHC</label>
                        <input value={editData.ihc_role} onChange={e => setEditData(d => ({ ...d, ihc_role: e.target.value }))}
                          list="ihc-roles" placeholder="Chọn hoặc nhập..."
                          className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                          style={{ background: '#0a1929', border: '1px solid #1e3a5f' }} />
                        <datalist id="ihc-roles">
                          {DEFAULT_ROLES.map(r => <option key={r} value={r} />)}
                        </datalist>
                      </div>
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#94a3b8' }}>Bộ phận</label>
                        <input value={editData.department} onChange={e => setEditData(d => ({ ...d, department: e.target.value }))}
                          placeholder="VD: Sản xuất, QA/QC..."
                          className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                          style={{ background: '#0a1929', border: '1px solid #1e3a5f' }} />
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={handleSave} disabled={saving}
                        className="px-4 py-1.5 rounded-lg text-xs font-medium text-white"
                        style={{ background: '#16a34a' }}>
                        {saving ? 'Đang lưu...' : 'Lưu'}
                      </button>
                      <button onClick={() => setEditId(null)}
                        className="px-4 py-1.5 rounded-lg text-xs" style={{ color: '#64748b', border: '1px solid #1e3a5f' }}>
                        Huỷ
                      </button>
                    </div>
                  </div>
                ) : (
                  /* View mode */
                  <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                    <div className="w-10 h-10 rounded-full grid place-items-center text-sm font-bold"
                      style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.25)' }}>
                      {m.display_name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-white">{m.display_name}</p>
                        {m.ihc_role && (
                          <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold"
                            style={{
                              background: m.ihc_role.toLowerCase().includes('chairman') ? 'rgba(245,158,11,0.12)' :
                                m.ihc_role.toLowerCase().includes('executive') ? 'rgba(99,102,241,0.12)' : 'rgba(148,163,184,0.1)',
                              color: m.ihc_role.toLowerCase().includes('chairman') ? '#fbbf24' :
                                m.ihc_role.toLowerCase().includes('executive') ? '#a5b4fc' : '#94a3b8',
                              border: `1px solid ${m.ihc_role.toLowerCase().includes('chairman') ? 'rgba(245,158,11,0.25)' :
                                m.ihc_role.toLowerCase().includes('executive') ? 'rgba(99,102,241,0.25)' : 'rgba(148,163,184,0.2)'}`,
                            }}>
                            {m.ihc_role}
                          </span>
                        )}
                      </div>
                      <p className="text-sm mt-0.5" style={{ color: '#475569' }}>
                        {m.email}
                        {m.department && <span> · {m.department}</span>}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => startEdit(m)} title="Sửa"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
                        <svg className="w-4 h-4" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button onClick={() => handleRemove(m.id)} title="Xoá"
                        disabled={removeId === m.id}
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
            );
          })
        )}
      </div>

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6"
            style={{ background: '#111725', border: '1px solid #1e3a5f', boxShadow: '0 25px 60px rgba(0,0,0,0.5)' }}>
            <div className="grid items-center mb-5" style={{ gridTemplateColumns: '1fr auto' }}>
              <h3 className="text-base font-bold text-white">Mời thành viên IHC</h3>
              <button onClick={() => setShowInvite(false)}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: 'rgba(255,255,255,0.05)' }}>
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-slate-400">Vai trò IHC</label>
                  <input value={invite.ihc_role}
                    onChange={e => setInvite(i => ({ ...i, ihc_role: e.target.value }))}
                    list="invite-roles" placeholder="Chairman, Executive..."
                    className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                    style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
                  <datalist id="invite-roles">
                    {DEFAULT_ROLES.map(r => <option key={r} value={r} />)}
                  </datalist>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-slate-400">Bộ phận</label>
                  <input value={invite.department}
                    onChange={e => setInvite(i => ({ ...i, department: e.target.value }))}
                    placeholder="Sản xuất, QA/QC..."
                    className="w-full px-4 py-2.5 rounded-xl text-sm text-white outline-none"
                    style={{ background: '#0f1e35', border: '1px solid #1e3a5f' }} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Email *</label>
                <input type="email" required value={invite.email}
                  onChange={e => setInvite(i => ({ ...i, email: e.target.value }))}
                  placeholder="email@company.vn"
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
                {inviting ? 'Đang gửi lời mời...' : 'Mời thành viên'}
              </button>
              <p className="text-xs text-center" style={{ color: '#334155' }}>
                Thành viên đăng nhập bằng email + mật khẩu trên. Chỉ có quyền xem, không thể chỉnh sửa.
              </p>
            </form>
          </div>
        </div>
      )}

      </>)}

      {/* ── Tab: Meeting Minutes ── */}
      {activeTab === 'minutes' && (
        <div className="flex-1 lg:min-h-0 flex flex-col">
          {/* Upload bar */}
          <div className="grid items-center gap-3 mb-4" style={{ gridTemplateColumns: '1fr auto' }}>
            <p className="text-sm" style={{ color: '#64748b' }}>{minutes.length} biên bản họp</p>
            <div>
              <input ref={minutesInputRef} type="file" className="hidden"
                accept=".pdf,.docx,.doc,.pptx,.txt,.md"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUploadMinutes(f); }} />
              <button onClick={() => minutesInputRef.current?.click()} disabled={uploadingMinutes}
                className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: 'linear-gradient(135deg, #15803d, #16a34a)', boxShadow: '0 4px 12px rgba(22,163,74,0.3)' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
                </svg>
                {uploadingMinutes ? 'Đang upload...' : 'Upload biên bản'}
              </button>
            </div>
          </div>

          {/* Minutes list */}
          <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
            {fetchingMinutes ? (
              <div className="space-y-3">
                {[1, 2].map(i => (
                  <div key={i} className="rounded-2xl h-20 animate-pulse" style={{ background: '#162847', opacity: 1 - i * 0.2 }} />
                ))}
              </div>
            ) : minutes.length === 0 ? (
              <div className="rounded-2xl p-12 text-center" style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
                <svg className="w-16 h-16 mx-auto mb-4" style={{ color: '#1e3a5f' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-white font-semibold mb-2">Chưa có biên bản họp</p>
                <p className="text-sm" style={{ color: '#475569' }}>Upload biên bản họp IHC để lưu trữ và theo dõi</p>
              </div>
            ) : (
              minutes.map((m, i) => (
                <div key={m.id} className="rounded-xl p-4 transition-colors doc-card-hover"
                  style={{ background: 'linear-gradient(135deg, #162847, #0f2236)', border: '1px solid #1e3a5f' }}>
                  <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                    {/* File icon */}
                    <div className="w-10 h-10 rounded-xl grid place-items-center"
                      style={{
                        background: m.mime_type.includes('pdf') ? 'rgba(239,68,68,0.12)' : 'rgba(37,99,235,0.12)',
                        border: `1px solid ${m.mime_type.includes('pdf') ? 'rgba(239,68,68,0.25)' : 'rgba(37,99,235,0.25)'}`,
                      }}>
                      <span className="text-xs font-bold" style={{
                        color: m.mime_type.includes('pdf') ? '#f87171' : '#60a5fa',
                      }}>
                        {m.original_filename.split('.').pop()?.toUpperCase() || 'FILE'}
                      </span>
                    </div>

                    {/* Info */}
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate" title={m.original_filename}>
                        {m.original_filename}
                      </p>
                      <p className="text-sm mt-0.5" style={{ color: '#475569' }}>
                        {formatSize(m.file_size)} · {new Date(m.uploaded_at).toLocaleString('vi-VN', {
                          day: '2-digit', month: '2-digit', year: 'numeric',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => viewMinutes(m.id)} title="Xem"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)' }}>
                        <svg className="w-4 h-4" style={{ color: '#60a5fa' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      <button onClick={() => deleteMinutes(m.id)} title="Xoá"
                        disabled={deletingMinuteId === m.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                        <svg className="w-4 h-4" style={{ color: '#64748b' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
