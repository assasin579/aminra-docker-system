'use client';

import { useState, useEffect, useCallback } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || '';

interface User {
  id: string;
  email: string;
  role: 'business' | 'provider';
  company_name: string;
  company_code: string | null;
  status: 'active' | 'pending' | 'suspended';
  is_owner: boolean;
  tenant_id: string | null;
  created_at: string;
}

const STATUS_CFG = {
  active:    { label: 'Hoạt động',  bg: 'rgba(34,197,94,0.1)',   color: '#4ade80' },
  pending:   { label: 'Chờ duyệt',  bg: 'rgba(245,158,11,0.1)', color: '#fbbf24' },
  suspended: { label: 'Đình chỉ',   bg: 'rgba(239,68,68,0.1)',  color: '#f87171' },
};
const ROLE_CFG = {
  business: { label: 'Doanh nghiệp', color: '#4ade80' },
  provider: { label: 'Tổ chức',      color: '#60a5fa' },
};

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return 'Hôm nay';
  if (d === 1) return 'Hôm qua';
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

interface FormState {
  email: string; password: string; company_name: string;
  company_code: string; role: string; status: string;
}
const EMPTY_FORM: FormState = {
  email: '', password: '', company_name: '', company_code: '', role: 'business', status: 'active',
};

export default function AdminUserManager({ token }: { token: string }) {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [fetching, setFetching] = useState(false);

  const [filterRole, setFilterRole]     = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [search, setSearch]             = useState('');

  const [modal, setModal] = useState<'create' | 'edit' | null>(null);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const authHdr = { Authorization: `Bearer ${token}` };

  const fetchUsers = useCallback(async () => {
    setFetching(true);
    try {
      const params = new URLSearchParams();
      if (filterRole)   params.set('role', filterRole);
      if (filterStatus) params.set('status', filterStatus);
      if (search)       params.set('q', search);
      const res = await fetch(`${API}/admin/users?${params}`, { headers: authHdr });
      if (res.ok) {
        const d = await res.json();
        setUsers(d.users);
        setTotal(d.total);
      }
    } finally { setFetching(false); }
  }, [filterRole, filterStatus, search, token]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormError('');
    setEditTarget(null);
    setModal('create');
  };

  const openEdit = (u: User) => {
    setForm({
      email: u.email,
      password: '',
      company_name: u.company_name,
      company_code: u.company_code ?? '',
      role: u.role,
      status: u.status,
    });
    setFormError('');
    setEditTarget(u);
    setModal('edit');
  };

  const handleSave = async () => {
    setFormError('');
    setSaving(true);
    try {
      if (modal === 'create') {
        if (!form.email || !form.password || !form.company_name) {
          setFormError('Vui lòng điền đầy đủ thông tin bắt buộc'); return;
        }
        const res = await fetch(`${API}/admin/users`, {
          method: 'POST',
          headers: { ...authHdr, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: form.email, password: form.password,
            company_name: form.company_name,
            company_code: form.company_code || undefined,
            role: form.role, status: form.status,
          }),
        });
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          throw new Error(e.detail || 'Tạo thất bại');
        }
      } else if (modal === 'edit' && editTarget) {
        const body: Record<string, unknown> = {};
        if (form.company_name !== editTarget.company_name) body.company_name = form.company_name;
        if (form.company_code !== (editTarget.company_code ?? '')) body.company_code = form.company_code || null;
        if (form.status !== editTarget.status) body.status = form.status;
        if (form.role !== editTarget.role) body.role = form.role;
        if (form.password) body.password = form.password;
        const res = await fetch(`${API}/admin/users/${editTarget.id}`, {
          method: 'PUT',
          headers: { ...authHdr, 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          throw new Error(e.detail || 'Cập nhật thất bại');
        }
      }
      setModal(null);
      fetchUsers();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Lỗi');
    } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Xác nhận xoá user này? Toàn bộ dữ liệu liên quan sẽ bị xoá.')) return;
    setDeleteId(id);
    try {
      await fetch(`${API}/admin/users/${id}`, { method: 'DELETE', headers: authHdr });
      fetchUsers();
    } finally { setDeleteId(null); }
  };

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const inputCls = "w-full px-3 py-2.5 rounded-xl text-sm text-white outline-none";
  const inputStyle = { background: '#0f1e35', border: '1px solid #1e3a5f' };

  return (
    <div>
      {/* Toolbar */}
      <div className="grid items-center mb-5 gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(12rem, auto))' }}>
          <input
            type="text" placeholder="Tìm email, tên..."
            value={search} onChange={e => setSearch(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg text-slate-300 outline-none"
            style={{ background: '#162847', border: '1px solid #1e3a5f' }} />
          <select value={filterRole} onChange={e => setFilterRole(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg text-slate-300 outline-none"
            style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <option value="">Tất cả loại</option>
            <option value="business">Doanh nghiệp</option>
            <option value="provider">Tổ chức</option>
          </select>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg text-slate-300 outline-none"
            style={{ background: '#162847', border: '1px solid #1e3a5f' }}>
            <option value="">Tất cả trạng thái</option>
            <option value="active">Hoạt động</option>
            <option value="pending">Chờ duyệt</option>
            <option value="suspended">Đình chỉ</option>
          </select>
        </div>
        <button onClick={openCreate}
          className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white"
          style={{ gridTemplateColumns: 'auto 1fr', background: '#16a34a' }}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          Thêm user
        </button>
      </div>

      {/* Table */}
      <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #1e3a5f' }}>
        {fetching ? (
          <div className="p-10 text-center text-slate-400 text-sm">Đang tải...</div>
        ) : users.length === 0 ? (
          <div className="p-10 text-center text-slate-500 text-sm">Không có user nào</div>
        ) : (
          <table className="w-full text-sm">
            <thead style={{ background: '#0f1e35' }}>
              <tr>
                {['Email / Tên', 'Loại', 'Trạng thái', 'Ngày tạo', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-slate-400 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => {
                const st = STATUS_CFG[u.status] ?? STATUS_CFG.active;
                const rl = ROLE_CFG[u.role] ?? ROLE_CFG.business;
                return (
                  <tr key={u.id} style={{
                    background: i % 2 === 0 ? '#162847' : '#0f1e35',
                    borderTop: '1px solid #1e3a5f',
                  }}>
                    <td className="px-4 py-3">
                      <p className="text-white font-medium">{u.email}</p>
                      <p className="text-xs mt-0.5" style={{ color: '#475569' }}>{u.company_name}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-medium" style={{ color: rl.color }}>{rl.label}</span>
                      {u.role === 'business' && !u.is_owner && (
                        <span className="ml-1 text-xs" style={{ color: '#334155' }}>· thành viên</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full text-xs"
                        style={{ background: st.bg, color: st.color }}>
                        {st.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{timeAgo(u.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="grid grid-flow-col items-center gap-3 justify-end">
                        <button onClick={() => openEdit(u)}
                          className="text-xs text-slate-400 hover:text-white transition-colors">
                          Sửa
                        </button>
                        <button onClick={() => handleDelete(u.id)}
                          disabled={deleteId === u.id}
                          className="text-xs text-slate-500 hover:text-red-400 transition-colors">
                          {deleteId === u.id ? '...' : 'Xoá'}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-xs text-slate-600 mt-2">{total} user</p>

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4"
          style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}>
          <div className="w-full max-w-md rounded-2xl p-6" style={{ background: '#111725', border: '1px solid #1e3a5f' }}>
            <div className="grid items-center mb-5" style={{ gridTemplateColumns: '1fr auto' }}>
              <h3 className="text-base font-bold text-white">
                {modal === 'create' ? 'Thêm user mới' : `Sửa: ${editTarget?.email}`}
              </h3>
              <button onClick={() => setModal(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-3">
              {modal === 'create' && (
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-slate-400">Email *</label>
                  <input type="email" required value={form.email} onChange={set('email')}
                    placeholder="user@company.vn" className={inputCls} style={inputStyle} />
                </div>
              )}

              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">
                  {modal === 'create' ? 'Mật khẩu *' : 'Mật khẩu mới (để trống = giữ nguyên)'}
                </label>
                <input type="password" value={form.password} onChange={set('password')}
                  placeholder={modal === 'create' ? 'Tối thiểu 8 ký tự' : '••••••••'}
                  className={inputCls} style={inputStyle} />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Tên công ty / Tổ chức *</label>
                <input type="text" required value={form.company_name} onChange={set('company_name')}
                  placeholder="Công ty ABC" className={inputCls} style={inputStyle} />
              </div>

              <div>
                <label className="block text-xs font-medium mb-1.5 text-slate-400">Mã số thuế / Giấy phép</label>
                <input type="text" value={form.company_code} onChange={set('company_code')}
                  placeholder="Tuỳ chọn" className={inputCls} style={inputStyle} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-slate-400">Loại</label>
                  <select value={form.role} onChange={set('role')}
                    className={inputCls} style={inputStyle}>
                    <option value="business">Doanh nghiệp</option>
                    <option value="provider">Tổ chức</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5 text-slate-400">Trạng thái</label>
                  <select value={form.status} onChange={set('status')}
                    className={inputCls} style={inputStyle}>
                    <option value="active">Hoạt động</option>
                    <option value="pending">Chờ duyệt</option>
                    <option value="suspended">Đình chỉ</option>
                  </select>
                </div>
              </div>

              {formError && (
                <p className="text-xs px-3 py-2 rounded-lg"
                  style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
                  {formError}
                </p>
              )}

              <button onClick={handleSave} disabled={saving}
                className="w-full py-2.5 rounded-xl font-semibold text-sm text-white mt-1"
                style={{ background: saving ? '#1e3a5f' : '#16a34a' }}>
                {saving ? 'Đang lưu...' : modal === 'create' ? 'Tạo user' : 'Lưu thay đổi'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
