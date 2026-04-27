'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { readAdminToken } from '@/lib/adminAuth';

type AuditLog = {
  id: string;
  user_id: string | null;
  user_email: string | null;
  user_role: string | null;
  tenant_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  changes: Record<string, [unknown, unknown]> | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

type Filters = {
  user_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  from_date: string;
  to_date: string;
};

const EMPTY_FILTERS: Filters = {
  user_id: '',
  action: '',
  entity_type: '',
  entity_id: '',
  from_date: '',
  to_date: '',
};

const PAGE_SIZE = 25;

export default function AuditLogsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Restore token on mount
  useEffect(() => {
    setToken(readAdminToken());
  }, []);

  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
    params.set('page', String(page));
    params.set('limit', String(PAGE_SIZE));
    return params.toString();
  }, [filters, page]);

  const fetchLogs = async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/api/auth/admin/audit-logs?${queryString}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Lỗi ${res.status}`);
      }
      setLogs(data.logs ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi không xác định');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, page]);

  const onApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLogs();
  };

  const onResetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-7xl mx-auto px-4 py-8" data-page>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#0F5132' }}>Nhật ký kiểm toán</h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            Append-only audit trail. Hiển thị {logs.length} / {total} bản ghi.
          </p>
        </div>
        <Link
          href="/admin"
          className="text-sm font-medium"
          style={{ color: '#0F5132' }}
        >
          ← Quay lại Admin
        </Link>
      </div>

      {/* Filters */}
      <form
        onSubmit={onApplyFilters}
        className="bg-white rounded-2xl p-4 mb-6 grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-3"
        style={{ border: '1px solid #E2E8F0' }}
      >
        <FilterInput label="Action"      value={filters.action}      onChange={v => setFilters({ ...filters, action: v })} placeholder="login.success" />
        <FilterInput label="Entity"      value={filters.entity_type} onChange={v => setFilters({ ...filters, entity_type: v })} placeholder="user" />
        <FilterInput label="User ID"     value={filters.user_id}     onChange={v => setFilters({ ...filters, user_id: v })} placeholder="UUID" />
        <FilterInput label="Entity ID"   value={filters.entity_id}   onChange={v => setFilters({ ...filters, entity_id: v })} placeholder="UUID" />
        <FilterInput label="Từ ngày"     value={filters.from_date}   onChange={v => setFilters({ ...filters, from_date: v })} type="datetime-local" />
        <FilterInput label="Đến ngày"    value={filters.to_date}     onChange={v => setFilters({ ...filters, to_date: v })} type="datetime-local" />

        <div className="md:col-span-3 lg:col-span-6 flex gap-2 justify-end">
          <button
            type="button" onClick={onResetFilters}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{ background: '#F1F5F9', color: '#0F5132' }}
          >
            Reset
          </button>
          <button
            type="submit" disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium"
            style={{
              background: loading ? '#94A3B8' : '#0F5132',
              color: 'white',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Đang tải...' : 'Áp dụng filter'}
          </button>
        </div>
      </form>

      {!token && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm" style={{ color: '#7c2d12' }}>
          Bạn cần đăng nhập với tài khoản admin để xem audit logs.{' '}
          <Link href="/provider/login" className="font-medium underline">Đăng nhập</Link>
        </div>
      )}

      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm mb-4" style={{ color: '#991b1b' }}>
          {error}
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-2xl overflow-x-auto" style={{ border: '1px solid #E2E8F0' }}>
        <table className="w-full text-sm">
          <thead style={{ background: '#FFFFFF' }}>
            <tr>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Thời gian</th>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>User</th>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Action</th>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Entity</th>
              <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Changes / Metadata</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 && !loading && token && (
              <tr>
                <td colSpan={5} className="text-center py-12 text-sm" style={{ color: '#94A3B8' }}>
                  Không có bản ghi nào khớp filter.
                </td>
              </tr>
            )}
            {logs.map(log => (
              <tr key={log.id} className="border-t" style={{ borderColor: '#F1F5F9' }}>
                <td className="px-4 py-3 align-top text-xs" style={{ color: '#6B7280' }}>
                  {new Date(log.created_at).toLocaleString('vi-VN', { hour12: false })}
                </td>
                <td className="px-4 py-3 align-top">
                  {log.user_email ? (
                    <>
                      <div className="font-medium" style={{ color: '#0F5132' }}>{log.user_email}</div>
                      {log.user_role && (
                        <div className="text-xs" style={{ color: '#94A3B8' }}>{log.user_role}</div>
                      )}
                    </>
                  ) : (
                    <span className="text-xs italic" style={{ color: '#94A3B8' }}>anonymous</span>
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  <code className="px-2 py-1 rounded text-xs" style={{ background: '#FFFFFF', color: '#0F5132' }}>
                    {log.action}
                  </code>
                </td>
                <td className="px-4 py-3 align-top text-xs" style={{ color: '#6B7280' }}>
                  <div>{log.entity_type}</div>
                  {log.entity_id && (
                    <div className="font-mono text-[10px]" style={{ color: '#94A3B8' }}>
                      {log.entity_id.slice(0, 8)}…
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  {log.changes && Object.keys(log.changes).length > 0 && (
                    <div className="space-y-1 mb-2">
                      {Object.entries(log.changes).map(([key, [before, after]]) => (
                        <div key={key} className="text-xs">
                          <span className="font-medium" style={{ color: '#0F5132' }}>{key}:</span>{' '}
                          <span style={{ color: '#dc2626' }}>{String(before ?? '∅')}</span>
                          {' → '}
                          <span style={{ color: '#198754' }}>{String(after ?? '∅')}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {Object.keys(log.metadata ?? {}).length > 0 && (
                    <details>
                      <summary className="text-xs cursor-pointer" style={{ color: '#6B7280' }}>metadata</summary>
                      <pre className="text-[11px] mt-1 p-2 rounded" style={{ background: '#FFFFFF', color: '#6B7280' }}>
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm" style={{ color: '#6B7280' }}>
            Trang {page} / {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{
                background: page <= 1 ? '#F1F5F9' : 'white',
                border: '1px solid #E2E8F0',
                color: page <= 1 ? '#94A3B8' : '#0F5132',
                cursor: page <= 1 ? 'not-allowed' : 'pointer',
              }}
            >
              ← Trước
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="px-4 py-2 rounded-lg text-sm font-medium"
              style={{
                background: page >= totalPages ? '#F1F5F9' : 'white',
                border: '1px solid #E2E8F0',
                color: page >= totalPages ? '#94A3B8' : '#0F5132',
                cursor: page >= totalPages ? 'not-allowed' : 'pointer',
              }}
            >
              Sau →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterInput(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium block mb-1" style={{ color: '#6B7280' }}>{props.label}</span>
      <input
        type={props.type ?? 'text'}
        value={props.value}
        onChange={e => props.onChange(e.target.value)}
        placeholder={props.placeholder}
        className="w-full px-3 py-2 rounded-lg text-sm outline-none"
        style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132' }}
      />
    </label>
  );
}
