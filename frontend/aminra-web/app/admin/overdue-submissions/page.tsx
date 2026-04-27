'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { readAdminToken } from '@/lib/adminAuth';

type OverdueItem = {
  submission_id: string;
  company_name: string | null;
  status: string;
  submitted_at: string | null;
  deadline: string;
  provider_email: string | null;
  provider_name: string | null;
  days_overdue: number;
};

const STATUS_LABEL: Record<string, string> = {
  pending: 'Đang chờ',
  reviewing: 'Đang đánh giá',
  revision_required: 'Cần sửa',
  assigned: 'Đã giao auditor',
};

export default function OverdueSubmissionsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<OverdueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setToken(readAdminToken());
  }, []);

  useEffect(() => {
    if (!token) { setLoading(false); return; }
    (async () => {
      try {
        const res = await fetch('/api/auth/admin/overdue-submissions', {
          headers: { Authorization: `Bearer ${token}` },
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
        setItems(body.items ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Lỗi tải queue');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const urgencyColor = (days: number) =>
    days >= 14 ? '#dc2626' : days >= 7 ? '#ea580c' : '#f59e0b';

  return (
    <div className="max-w-7xl mx-auto px-4 py-8" data-page>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: '#0F5132' }}>
            Hồ sơ quá hạn (escalation)
          </h1>
          <p className="text-sm mt-1" style={{ color: '#6B7280' }}>
            {items.length > 0
              ? `${items.length} hồ sơ đã quá deadline mà chưa được duyệt`
              : 'Không có hồ sơ nào quá hạn'}
          </p>
        </div>
        <Link href="/admin" className="text-sm font-medium" style={{ color: '#0F5132' }}>
          ← Quay lại Admin
        </Link>
      </div>

      {!token && !loading && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm" style={{ color: '#7c2d12' }}>
          Cần đăng nhập admin. <Link href="/provider/login" className="underline font-medium">Đăng nhập</Link>
        </div>
      )}

      {error && (
        <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm mb-4"
          style={{ color: '#991b1b' }}>
          {error}
        </div>
      )}

      {loading && <p className="text-sm" style={{ color: '#94A3B8' }}>Đang tải...</p>}

      {!loading && items.length === 0 && token && !error && (
        <div className="bg-[#E8F5EF] border border-[#E8F5EF] rounded-2xl p-8 text-center"
          style={{ color: '#0A3622' }}>
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#E8F5EF] grid place-items-center">
            <span className="text-xl">✓</span>
          </div>
          <p className="font-semibold">Không có hồ sơ nào quá hạn</p>
          <p className="text-xs mt-1" style={{ color: '#198754' }}>
            Tất cả tổ chức cấp đang xử lý hồ sơ đúng SLA.
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="bg-white rounded-2xl overflow-x-auto" style={{ border: '1px solid #E2E8F0' }}>
          <table className="w-full text-sm">
            <thead style={{ background: '#FFFFFF' }}>
              <tr>
                <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Doanh nghiệp</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Tổ chức cấp</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Trạng thái</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Deadline</th>
                <th className="text-right px-4 py-3 font-medium" style={{ color: '#6B7280' }}>Quá hạn</th>
              </tr>
            </thead>
            <tbody>
              {items.map(it => (
                <tr key={it.submission_id} className="border-t" style={{ borderColor: '#F1F5F9' }}>
                  <td className="px-4 py-3">
                    <div className="font-medium" style={{ color: '#0F5132' }}>
                      {it.company_name || <span className="italic" style={{ color: '#94A3B8' }}>Chưa rõ</span>}
                    </div>
                    <div className="font-mono text-[10px] mt-0.5" style={{ color: '#94A3B8' }}>
                      {it.submission_id.slice(0, 8)}…
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-xs" style={{ color: '#0F5132' }}>
                      {it.provider_name || <span className="italic" style={{ color: '#94A3B8' }}>Chưa rõ</span>}
                    </div>
                    {it.provider_email && (
                      <a href={`mailto:${it.provider_email}`} className="text-[11px] underline" style={{ color: '#0F5132' }}>
                        {it.provider_email}
                      </a>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold"
                      style={{ background: 'rgba(14,165,233,0.12)', color: '#0EA5E9' }}>
                      {STATUS_LABEL[it.status] || it.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: '#6B7280' }}>
                    {new Date(it.deadline).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' })}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="font-mono font-semibold text-sm"
                      style={{ color: urgencyColor(it.days_overdue) }}>
                      {it.days_overdue.toFixed(1)} ngày
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
