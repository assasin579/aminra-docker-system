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

  // Permissions
  const [permModal, setPermModal] = useState<string | null>(null); // member id
  const [permData, setPermData] = useState<Record<string, boolean>>({});
  const [permSaving, setPermSaving] = useState(false);

  // Invite link
  const [showInviteLink, setShowInviteLink] = useState(false);
  const [inviteLink, setInviteLink] = useState({ email: '', ihc_role: '', department: '' });
  const [invitingLink, setInvitingLink] = useState(false);
  const [generatedLink, setGeneratedLink] = useState('');

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
      <div className="flex items-center gap-1">
        <div className="animate-pulse-dot" /><div className="animate-pulse-dot" /><div className="animate-pulse-dot" />
      </div>
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
    <div data-page className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden">
      {/* Header */}
      <div className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
        <div className="grid items-center" style={{ gridTemplateColumns: '1fr auto' }}>
          <div className="grid grid-flow-col items-center gap-3 justify-start">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}>
              <svg className="w-5 h-5" style={{ color: '#818cf8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: '#1A2332' }}>Internal Halal Committee</h1>
              <p className="text-sm" style={{ color: '#5F6F80' }}>
                {members.length}/{MAX} thành viên · {user.company_name}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleExportIHC} disabled={exporting || members.length === 0}
              className="grid items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all hover:scale-105 disabled:opacity-40"
              style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(100,116,139,0.1)', color: '#64748b', border: '1px solid rgba(100,116,139,0.25)' }}>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {exporting ? 'Đang xuất...' : 'Xuất tài liệu IHC'}
            </button>
            {members.length < MAX && (
              <button onClick={() => setShowInvite(true)}
                className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: '#087653', boxShadow: '0 4px 12px rgba(8,118,83,0.3)' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
                </svg>
                Mời thành viên
              </button>
            )}
            {members.length < MAX && (
              <button onClick={() => { setShowInviteLink(true); setGeneratedLink(''); setInviteLink({ email: '', ihc_role: '', department: '' }); }}
                className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: '#F5F3FF', color: '#7C3AED', border: '1px solid #DDD6FE' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Mời qua link
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-2 gap-1 mb-5 p-1 rounded-xl animate-section" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
        {([
          { id: 'members' as const, label: 'Thành viên', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
          { id: 'minutes' as const, label: 'Biên bản họp', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
        ]).map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className="flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: activeTab === tab.id ? '#087653' : 'transparent',
              color: activeTab === tab.id ? '#FFFFFF' : '#6B7280',
              boxShadow: activeTab === tab.id ? '0 2px 8px rgba(8,118,83,0.25)' : 'none',
            }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={tab.icon} />
            </svg>
            {tab.label}
            {tab.id === 'minutes' && minutes.length > 0 && (
              <span className="px-1.5 py-0.5 rounded text-xs animate-chip"
                style={{ background: activeTab === tab.id ? 'rgba(255,255,255,0.2)' : 'rgba(8,118,83,0.15)', color: activeTab === tab.id ? '#fff' : '#087653' }}>
                {minutes.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab: Members ── */}
      {activeTab === 'members' && (<div key="members" className="animate-tab-content">

      {/* Owner card */}
      <div className="rounded-xl p-4 mb-4 doc-card-hover animate-section"
        style={{ background: '#FFFFFF', border: '1px solid rgba(8,118,83,0.3)' }}>
        <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
          <div className="w-10 h-10 rounded-full grid place-items-center text-sm font-bold"
            style={{ background: 'rgba(8,118,83,0.15)', color: '#087653', border: '1px solid rgba(8,118,83,0.3)' }}>
            {user.company_name?.[0]?.toUpperCase() || 'O'}
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: '#1A2332' }}>{user.email}</p>
            <p className="text-sm" style={{ color: '#5F6F80' }}>Chủ tài khoản</p>
          </div>
          <span className="px-3 py-1 rounded-lg text-xs font-bold"
            style={{ background: 'rgba(8,118,83,0.12)', color: '#087653', border: '1px solid rgba(8,118,83,0.25)' }}>
            Owner
          </span>
        </div>
      </div>

      {/* Member list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="rounded-2xl h-20 shimmer" style={{ background: '#F0F7F4', opacity: 1 - i * 0.2 }} />
            ))}
          </div>
        ) : members.length === 0 ? (
          <div className="rounded-2xl p-12 text-center animate-scale-in" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
            <svg className="w-16 h-16 mx-auto mb-4 animate-empty-icon" style={{ color: '#E2E8F0' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <p className="font-semibold mb-2" style={{ color: '#1A2332' }}>Chưa có thành viên IHC</p>
            <p className="text-sm mb-4" style={{ color: '#5B6B7D' }}>Mời thành viên và phân vai trò trong Internal Halal Committee</p>
          </div>
        ) : (
          members.map((m, i) => {
            const isEditing = editId === m.id;
            return (
              <div key={m.id} className={`rounded-xl p-4 transition-colors doc-card-hover animate-list-item stagger-${Math.min(i + 1, 12)}`}
                style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                {isEditing ? (
                  /* Edit mode */
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#5B6B7D' }}>Họ tên</label>
                        <input value={editData.display_name} onChange={e => setEditData(d => ({ ...d, display_name: e.target.value }))}
                          className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                      </div>
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#5B6B7D' }}>Vai trò IHC</label>
                        <input value={editData.ihc_role} onChange={e => setEditData(d => ({ ...d, ihc_role: e.target.value }))}
                          list="ihc-roles" placeholder="Chọn hoặc nhập..."
                          className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                        <datalist id="ihc-roles">
                          {DEFAULT_ROLES.map(r => <option key={r} value={r} />)}
                        </datalist>
                      </div>
                      <div>
                        <label className="text-xs font-medium mb-1 block" style={{ color: '#5B6B7D' }}>Bộ phận</label>
                        <input value={editData.department} onChange={e => setEditData(d => ({ ...d, department: e.target.value }))}
                          placeholder="VD: Sản xuất, QA/QC..."
                          className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={handleSave} disabled={saving}
                        className="px-4 py-1.5 rounded-lg text-xs font-medium text-white"
                        style={{ background: '#087653' }}>
                        {saving ? 'Đang lưu...' : 'Lưu'}
                      </button>
                      <button onClick={() => setEditId(null)}
                        className="px-4 py-1.5 rounded-lg text-xs" style={{ color: '#5F6F80', border: '1px solid #E2E8F0' }}>
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
                        <p className="text-sm font-semibold" style={{ color: '#1A2332' }}>{m.display_name}</p>
                        {m.ihc_role && (
                          <span className="px-2.5 py-0.5 rounded-lg text-xs font-bold"
                            style={{
                              background: m.ihc_role.toLowerCase().includes('chairman') ? 'rgba(245,158,11,0.12)' :
                                m.ihc_role.toLowerCase().includes('executive') ? 'rgba(99,102,241,0.12)' : 'rgba(148,163,184,0.1)',
                              color: m.ihc_role.toLowerCase().includes('chairman') ? '#F59E0B' :
                                m.ihc_role.toLowerCase().includes('executive') ? '#a5b4fc' : '#94a3b8',
                              border: `1px solid ${m.ihc_role.toLowerCase().includes('chairman') ? 'rgba(245,158,11,0.25)' :
                                m.ihc_role.toLowerCase().includes('executive') ? 'rgba(99,102,241,0.25)' : 'rgba(148,163,184,0.2)'}`,
                            }}>
                            {m.ihc_role}
                          </span>
                        )}
                      </div>
                      <p className="text-sm mt-0.5" style={{ color: '#5B6B7D' }}>
                        {m.email}
                        {m.department && <span> · {m.department}</span>}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => startEdit(m)} title="Sửa"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(100,116,139,0.08)', border: '1px solid rgba(100,116,139,0.2)' }}>
                        <svg className="w-4 h-4" style={{ color: '#64748b' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button onClick={async () => {
                          setPermModal(m.id);
                          const res = await fetch(`/api/auth/business/members/${m.id}/permissions`, { headers: { Authorization: `Bearer ${token}` } });
                          if (res.ok) { const d = await res.json(); setPermData(d.permissions); }
                        }} title="Phân quyền"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: '#F5F3FF', border: '1px solid #DDD6FE' }}>
                        <svg className="w-4 h-4" style={{ color: '#7C3AED' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                      </button>
                      <button onClick={() => handleRemove(m.id)} title="Xoá"
                        disabled={removeId === m.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                        <svg className="w-4 h-4" style={{ color: '#5F6F80' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 25px 60px rgba(0,0,0,0.15)' }}>
            <div className="grid items-center mb-5" style={{ gridTemplateColumns: '1fr auto' }}>
              <h3 className="text-base font-bold" style={{ color: '#1A2332' }}>Mời thành viên IHC</h3>
              <button onClick={() => setShowInvite(false)}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: 'rgba(0,0,0,0.05)' }}>
                <span className="hover:text-gray-700">✕</span>
              </button>
            </div>
            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Họ tên *</label>
                <input type="text" required value={invite.display_name}
                  onChange={e => setInvite(i => ({ ...i, display_name: e.target.value }))}
                  placeholder="Nguyễn Văn A"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Vai trò IHC</label>
                  <input value={invite.ihc_role}
                    onChange={e => setInvite(i => ({ ...i, ihc_role: e.target.value }))}
                    list="invite-roles" placeholder="Chairman, Executive..."
                    className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                    style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                  <datalist id="invite-roles">
                    {DEFAULT_ROLES.map(r => <option key={r} value={r} />)}
                  </datalist>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Bộ phận</label>
                  <input value={invite.department}
                    onChange={e => setInvite(i => ({ ...i, department: e.target.value }))}
                    placeholder="Sản xuất, QA/QC..."
                    className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                    style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Email *</label>
                <input type="email" required value={invite.email}
                  onChange={e => setInvite(i => ({ ...i, email: e.target.value }))}
                  placeholder="email@company.vn"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: '#5F6F80' }}>Mật khẩu *</label>
                <input type="password" required value={invite.password}
                  onChange={e => setInvite(i => ({ ...i, password: e.target.value }))}
                  placeholder="Tối thiểu 8 ký tự"
                  className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                  style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
              </div>
              {inviteError && <p className="text-xs text-red-400">{inviteError}</p>}
              <button type="submit" disabled={inviting}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                style={{ background: inviting ? '#E2E8F0' : '#087653', color: inviting ? '#5B6B7D' : 'white' }}>
                {inviting ? 'Đang gửi lời mời...' : 'Mời thành viên'}
              </button>
              <p className="text-xs text-center" style={{ color: '#94A3B8' }}>
                Thành viên đăng nhập bằng email + mật khẩu trên. Chỉ có quyền xem, không thể chỉnh sửa.
              </p>
            </form>
          </div>
        </div>
      )}

      </div>)}

      {/* ── Tab: Meeting Minutes ── */}
      {activeTab === 'minutes' && (
        <div key="minutes" className="flex-1 lg:min-h-0 flex flex-col animate-tab-content">
          {/* Upload bar */}
          <div className="grid items-center gap-3 mb-4 animate-section" style={{ gridTemplateColumns: '1fr auto' }}>
            <p className="text-sm" style={{ color: '#5F6F80' }}>{minutes.length} biên bản họp</p>
            <div>
              <input ref={minutesInputRef} type="file" className="hidden"
                accept=".pdf,.docx,.doc,.pptx,.txt,.md"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUploadMinutes(f); }} />
              <button onClick={() => minutesInputRef.current?.click()} disabled={uploadingMinutes}
                className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105"
                style={{ gridTemplateColumns: 'auto 1fr', background: '#087653', boxShadow: '0 4px 12px rgba(8,118,83,0.3)' }}>
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
                  <div key={i} className="rounded-2xl h-20 shimmer" style={{ background: '#F0F7F4', opacity: 1 - i * 0.2 }} />
                ))}
              </div>
            ) : minutes.length === 0 ? (
              <div className="rounded-2xl p-12 text-center animate-scale-in" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
                <svg className="w-16 h-16 mx-auto mb-4 animate-empty-icon" style={{ color: '#E2E8F0' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="font-semibold mb-2" style={{ color: '#1A2332' }}>Chưa có biên bản họp</p>
                <p className="text-sm" style={{ color: '#5B6B7D' }}>Upload biên bản họp IHC để lưu trữ và theo dõi</p>
              </div>
            ) : (
              minutes.map((m, i) => (
                <div key={m.id} className={`rounded-xl p-4 transition-colors doc-card-hover animate-list-item stagger-${Math.min(i + 1, 12)}`}
                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                  <div className="grid items-center gap-3" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                    {/* File icon */}
                    <div className="w-10 h-10 rounded-xl grid place-items-center"
                      style={{
                        background: m.mime_type.includes('pdf') ? 'rgba(239,68,68,0.12)' : 'rgba(100,116,139,0.1)',
                        border: `1px solid ${m.mime_type.includes('pdf') ? 'rgba(239,68,68,0.25)' : 'rgba(100,116,139,0.2)'}`,
                      }}>
                      <span className="text-xs font-bold" style={{
                        color: m.mime_type.includes('pdf') ? '#f87171' : '#64748b',
                      }}>
                        {m.original_filename.split('.').pop()?.toUpperCase() || 'FILE'}
                      </span>
                    </div>

                    {/* Info */}
                    <div className="min-w-0">
                      <p className="text-sm font-semibold truncate" style={{ color: '#1A2332' }} title={m.original_filename}>
                        {m.original_filename}
                      </p>
                      <p className="text-sm mt-0.5" style={{ color: '#5B6B7D' }}>
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
                        style={{ background: 'rgba(100,116,139,0.08)', border: '1px solid rgba(100,116,139,0.2)' }}>
                        <svg className="w-4 h-4" style={{ color: '#64748b' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                      <button onClick={() => deleteMinutes(m.id)} title="Xoá"
                        disabled={deletingMinuteId === m.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                        style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)' }}>
                        <svg className="w-4 h-4" style={{ color: '#5F6F80' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

      {/* Permissions Modal */}
      {permModal && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }}
          onClick={() => setPermModal(null)}>
          <div className="w-full max-w-sm rounded-2xl p-6 animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-base font-bold" style={{ color: '#1A2332' }}>Phân quyền thành viên</h3>
              <button onClick={() => setPermModal(null)} style={{ color: '#6B7280' }}>✕</button>
            </div>
            <p className="text-xs mb-4" style={{ color: '#6B7280' }}>
              {members.find(m => m.id === permModal)?.display_name || 'Thành viên'}
            </p>
            <div className="space-y-3">
              {[
                { key: 'can_edit', label: 'Chỉnh sửa dữ liệu', desc: 'Sửa tài liệu, nguyên liệu, NCC, quy trình' },
                { key: 'can_delete', label: 'Xóa dữ liệu', desc: 'Xóa tài liệu, nguyên liệu, NCC' },
                { key: 'can_approve', label: 'Xác nhận / Phê duyệt', desc: 'Xác nhận bước sản xuất, seal lô hàng' },
                { key: 'can_upload', label: 'Upload tài liệu', desc: 'Upload tài liệu mới, ảnh minh chứng' },
              ].map(p => (
                <div key={p.key} className="flex items-center justify-between gap-3 px-4 py-3 rounded-xl"
                  style={{ background: '#FAFCF9', border: '1px solid #E2E8F0' }}>
                  <div>
                    <p className="text-sm font-medium" style={{ color: '#1A2332' }}>{p.label}</p>
                    <p className="text-xs mt-0.5" style={{ color: '#9CA3AF' }}>{p.desc}</p>
                  </div>
                  <button onClick={() => setPermData(d => ({ ...d, [p.key]: !d[p.key] }))}
                    className="w-11 h-6 rounded-full transition-colors duration-200 relative flex-shrink-0"
                    style={{ background: permData[p.key] ? '#087653' : '#E2E8F0' }}>
                    <div className="absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200"
                      style={{ transform: permData[p.key] ? 'translateX(22px)' : 'translateX(2px)' }} />
                  </button>
                </div>
              ))}
            </div>
            <button onClick={async () => {
                setPermSaving(true);
                try {
                  await fetch(`/api/auth/business/members/${permModal}/permissions`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                    body: JSON.stringify(permData),
                  });
                  setPermModal(null);
                  alert('Đã cập nhật quyền');
                } finally { setPermSaving(false); }
              }}
              disabled={permSaving}
              className="w-full mt-4 py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ background: '#087653' }}>
              {permSaving ? 'Đang lưu...' : 'Lưu phân quyền'}
            </button>
          </div>
        </div>
      )}

      {/* Invite Link Modal */}
      {showInviteLink && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }}
          onClick={() => setShowInviteLink(false)}>
          <div className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-base font-bold" style={{ color: '#1A2332' }}>Mời thành viên qua link</h3>
              <button onClick={() => setShowInviteLink(false)} style={{ color: '#6B7280' }}>✕</button>
            </div>

            {generatedLink ? (
              <div className="space-y-4">
                <div className="rounded-lg p-4" style={{ background: '#ECFDF5', border: '1px solid #A7F3D0' }}>
                  <p className="text-sm font-medium mb-2" style={{ color: '#059669' }}>Link mời đã tạo!</p>
                  <div className="flex items-center gap-2">
                    <input type="text" readOnly value={generatedLink}
                      className="flex-1 px-3 py-2 rounded-lg text-xs outline-none"
                      style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#374151' }} />
                    <button onClick={() => { navigator.clipboard.writeText(generatedLink); alert('Đã copy!'); }}
                      className="px-3 py-2 rounded-lg text-xs font-medium text-white flex-shrink-0" style={{ background: '#087653' }}>
                      Copy
                    </button>
                  </div>
                  <p className="text-xs mt-2" style={{ color: '#6B7280' }}>Gửi link này cho thành viên. Họ sẽ tự tạo mật khẩu khi tham gia.</p>
                </div>
                <button onClick={() => setShowInviteLink(false)}
                  className="w-full py-2.5 rounded-xl text-sm font-medium" style={{ color: '#6B7280', border: '1px solid #E2E8F0' }}>
                  Đóng
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Email thành viên *</label>
                  <input type="email" value={inviteLink.email} onChange={e => setInviteLink(f => ({ ...f, email: e.target.value }))}
                    placeholder="member@company.vn"
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Vai trò IHC</label>
                    <input value={inviteLink.ihc_role} onChange={e => setInviteLink(f => ({ ...f, ihc_role: e.target.value }))}
                      placeholder="VD: Halal Executive"
                      className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                      style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Phòng ban</label>
                    <input value={inviteLink.department} onChange={e => setInviteLink(f => ({ ...f, department: e.target.value }))}
                      placeholder="VD: QC"
                      className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                      style={{ background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' }} />
                  </div>
                </div>
                <button onClick={async () => {
                    if (!inviteLink.email) return;
                    setInvitingLink(true);
                    try {
                      const res = await fetch('/api/auth/business/invite-link', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                        body: JSON.stringify(inviteLink),
                      });
                      if (!res.ok) { const e = await res.json().catch(() => ({})); alert(e.detail || 'Lỗi'); return; }
                      const d = await res.json();
                      setGeneratedLink(`${window.location.origin}${d.portal_url}`);
                    } finally { setInvitingLink(false); }
                  }}
                  disabled={invitingLink || !inviteLink.email}
                  className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
                  style={{ background: !inviteLink.email ? '#E2E8F0' : '#7C3AED', color: !inviteLink.email ? '#9CA3AF' : '#fff' }}>
                  {invitingLink ? 'Đang tạo...' : 'Tạo link mời'}
                </button>
                <p className="text-xs text-center" style={{ color: '#9CA3AF' }}>
                  Link hết hạn sau 7 ngày. Thành viên tự tạo mật khẩu khi tham gia.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
