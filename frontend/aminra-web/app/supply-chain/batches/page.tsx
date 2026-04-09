'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';

interface Batch {
  id: string; batch_code: string; product_name: string;
  process_template_id: string | null; process_name: string | null;
  status: string; started_at: string | null; completed_at: string | null;
  compliance_score: number | null; qr_code_url: string | null; notes: string | null;
  step_count: number; step_completed: number; material_count: number; created_at: string;
}

interface ProcessOption { id: string; name: string; }
interface MaterialOption { id: string; name: string; unit: string | null; }

const STATUS = {
  draft:       { label: 'Nháp',       bg: '#F3F4F6', color: '#6B7280' },
  in_progress: { label: 'Đang SX',    bg: '#FFFBEB', color: '#B45309' },
  completed:   { label: 'Hoàn thành', bg: '#ECFDF5', color: '#059669' },
  rejected:    { label: 'Từ chối',    bg: '#FEF2F2', color: '#DC2626' },
};

export default function BatchesPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading: authLoading } = useUserAuth();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPeriod, setFilterPeriod] = useState('');

  // Create
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ batch_code: '', product_name: '', process_template_id: '', notes: '' });
  const [creating, setCreating] = useState(false);
  const [processes, setProcesses] = useState<ProcessOption[]>([]);
  const [materials, setMaterials] = useState<MaterialOption[]>([]);
  const [selectedMats, setSelectedMats] = useState<Record<string, string>>({}); // material_id -> quantity

  // Detail
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Members for assignment
  const [members, setMembers] = useState<Array<{ id: string; name: string; email: string; role: string }>>([]);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || user?.role !== 'business'))
      router.replace('/business/login');
  }, [authLoading, isAuthenticated, user, router]);

  const fetchBatches = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterPeriod) params.set('period', filterPeriod);
      const res = await fetch(`/api/api/supply-chain/batches?${params}`, { headers });
      if (res.ok) { const d = await res.json(); setBatches(d.batches || []); }
    } finally { setLoading(false); }
  }, [token, filterStatus, filterPeriod, headers]);

  useEffect(() => { if (isAuthenticated) fetchBatches(); }, [isAuthenticated, fetchBatches]);

  // Fetch options for create form
  const fetchOptions = async () => {
    const [pRes, mRes] = await Promise.all([
      fetch('/api/api/supply-chain/processes', { headers }),
      fetch('/api/api/supply-chain/materials', { headers }),
    ]);
    if (pRes.ok) { const d = await pRes.json(); setProcesses(d.processes?.map((p: any) => ({ id: p.id, name: p.name })) || []); }
    if (mRes.ok) { const d = await mRes.json(); setMaterials(d.materials?.map((m: any) => ({ id: m.id, name: m.name, unit: m.unit })) || []); }
  };

  const openCreate = async () => {
    await fetchOptions();
    setCreateForm({ batch_code: '', product_name: '', process_template_id: '', notes: '' });
    setSelectedMats({});
    setShowCreate(true);
  };

  const handleCreate = async () => {
    if (!createForm.product_name) return;
    setCreating(true);
    try {
      const mats = Object.entries(selectedMats).filter(([, q]) => q).map(([id, q]) => ({ material_id: id, quantity: parseFloat(q) || 0 }));
      const res = await fetch('/api/api/supply-chain/batches', {
        method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...createForm, process_template_id: createForm.process_template_id || null, materials: mats.length > 0 ? mats : null }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); alert(e.detail || 'Lỗi'); return; }
      setShowCreate(false);
      fetchBatches();
    } finally { setCreating(false); }
  };

  const openDetail = async (bid: string) => {
    setDetailLoading(true); setDetail(null);
    try {
      const [bRes, mRes] = await Promise.all([
        fetch(`/api/api/supply-chain/batches/${bid}`, { headers }),
        fetch('/api/api/supply-chain/batches/members', { headers }),
      ]);
      if (bRes.ok) setDetail(await bRes.json());
      if (mRes.ok) { const d = await mRes.json(); setMembers(d.members || []); }
    } finally { setDetailLoading(false); }
  };

  const assignMember = async (bid: string, memberId: string) => {
    setAssigning(true);
    try {
      const res = await fetch(`/api/api/supply-chain/batches/${bid}/assign-member`, {
        method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ member_id: memberId }),
      });
      if (res.ok) {
        const d = await res.json();
        alert(`Đã ủy quyền cho ${d.assigned_name}`);
        openDetail(bid);
      } else {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || 'Lỗi');
      }
    } finally { setAssigning(false); }
  };

  const updateStep = async (bid: string, stepId: string, data: any) => {
    await fetch(`/api/api/supply-chain/batches/${bid}/steps/${stepId}`, {
      method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    openDetail(bid);
    fetchBatches();
  };

  const updateBatchStatus = async (bid: string, status: string) => {
    await fetch(`/api/api/supply-chain/batches/${bid}`, {
      method: 'PUT', headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    openDetail(bid);
    fetchBatches();
  };

  const downloadQR = async (bid: string) => {
    const res = await fetch(`/api/api/supply-chain/batches/${bid}/qr`, { headers });
    if (!res.ok) { alert('Không thể tạo QR'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `QR_${batches.find(b => b.id === bid)?.batch_code || 'batch'}.png`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportPDF = async (bid: string) => {
    const res = await fetch(`/api/api/supply-chain/batches/${bid}/export-pdf`, { method: 'POST', headers });
    if (!res.ok) { alert('Xuất PDF thất bại'); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${batches.find(b => b.id === bid)?.batch_code || 'batch'}_report.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const deleteBatch = async (bid: string) => {
    if (!confirm('Xác nhận xoá lô hàng?')) return;
    await fetch(`/api/api/supply-chain/batches/${bid}`, { method: 'DELETE', headers });
    if (detail?.batch?.id === bid) setDetail(null);
    fetchBatches();
  };

  if (authLoading || !user) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const inputStyle = { background: '#FAFCF9', border: '1px solid #E2E8F0', color: '#1A2332' };
  const cardStyle = { background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' };

  return (
    <div data-page className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden">

      {/* Header */}
      <div className="rounded-2xl p-5 mb-4 animate-section" style={{ background: '#F0F7F4', border: '1px solid #E2E8F0' }}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl grid place-items-center"
              style={{ background: '#F0F9FF', border: '1px solid #BAE6FD' }}>
              <svg className="w-5 h-5" style={{ color: '#0369A1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold" style={{ color: '#1A2332' }}>Lô hàng</h1>
              <p className="text-xs" style={{ color: '#6B7280' }}>{batches.length} lô hàng</p>
            </div>
          </div>
          <button onClick={openCreate} className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white" style={{ background: '#087653' }}>
            + Tạo lô hàng
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap mb-4 animate-section">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="px-4 py-2.5 rounded-xl text-sm outline-none" style={inputStyle}>
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select value={filterPeriod} onChange={e => setFilterPeriod(e.target.value)}
          className="px-4 py-2.5 rounded-xl text-sm outline-none" style={inputStyle}>
          <option value="">Mọi thời gian</option>
          <option value="today">Hôm nay</option>
          <option value="week">Tuần này</option>
          <option value="month">Tháng này</option>
        </select>
      </div>

      {/* Batch list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {loading ? (
          <div className="py-12 flex items-center justify-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" />
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" style={{ animationDelay: '0.15s' }} />
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse-dot" style={{ animationDelay: '0.3s' }} />
          </div>
        ) : batches.length === 0 ? (
          <div className="rounded-2xl p-12 text-center animate-scale-in" style={cardStyle}>
            <p className="font-semibold" style={{ color: '#1A2332' }}>Chưa có lô hàng nào</p>
            <p className="text-sm mt-1" style={{ color: '#6B7280' }}>Tạo quy trình trước, sau đó tạo lô hàng</p>
          </div>
        ) : (
          batches.map((b, idx) => {
            const st = STATUS[b.status as keyof typeof STATUS] || STATUS.draft;
            const progress = b.step_count > 0 ? Math.round((b.step_completed / b.step_count) * 100) : 0;
            return (
              <div key={b.id} className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)} cursor-pointer`} style={cardStyle}
                onClick={() => openDetail(b.id)}>
                <div className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-sm font-bold" style={{ color: '#1A2332' }}>{b.batch_code}</span>
                      <span className="text-xs px-2 py-0.5 rounded animate-chip" style={{ background: st.bg, color: st.color }}>{st.label}</span>
                      {b.compliance_score != null && (
                        <span className="text-xs font-bold" style={{ color: b.compliance_score >= 75 ? '#059669' : b.compliance_score >= 50 ? '#B45309' : '#DC2626' }}>
                          {b.compliance_score}%
                        </span>
                      )}
                    </div>
                    <p className="text-sm" style={{ color: '#374151' }}>{b.product_name}</p>
                    <p className="text-xs mt-1" style={{ color: '#9CA3AF' }}>
                      {b.process_name && `${b.process_name} · `}{b.material_count} NL · {new Date(b.created_at).toLocaleDateString('vi-VN')}
                    </p>
                    {/* Progress bar */}
                    {b.step_count > 0 && (
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full" style={{ background: '#E2E8F0' }}>
                          <div className="h-full rounded-full transition-all animate-progress"
                            style={{ width: `${progress}%`, background: progress >= 100 ? '#059669' : '#087653' }} />
                        </div>
                        <span className="text-xs flex-shrink-0" style={{ color: '#9CA3AF' }}>{b.step_completed}/{b.step_count}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={e => { e.stopPropagation(); exportPDF(b.id); }} title="Xuất PDF"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
                      <svg className="w-4 h-4" style={{ color: '#B45309' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </button>
                    <button onClick={e => { e.stopPropagation(); downloadQR(b.id); }} title="Tải QR"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: '#F0F9FF', border: '1px solid #BAE6FD' }}>
                      <svg className="w-4 h-4" style={{ color: '#0369A1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                      </svg>
                    </button>
                    <button onClick={e => { e.stopPropagation(); deleteBatch(b.id); }} title="Xoá"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all hover:scale-110"
                      style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                      <svg className="w-4 h-4" style={{ color: '#DC2626' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── Create Modal ── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }} onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-lg rounded-2xl p-6 animate-modal-content overflow-y-auto"
            style={{ ...cardStyle, maxHeight: 'calc(100vh - 4rem)' }} onClick={e => e.stopPropagation()}>
            <h3 className="text-base font-bold mb-4" style={{ color: '#1A2332' }}>Tạo lô hàng mới</h3>
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Mã lô (tự động nếu trống)</label>
                  <input value={createForm.batch_code} onChange={e => setCreateForm(f => ({ ...f, batch_code: e.target.value }))}
                    placeholder="VD: LOT-20260409-001" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Sản phẩm *</label>
                  <input value={createForm.product_name} onChange={e => setCreateForm(f => ({ ...f, product_name: e.target.value }))}
                    placeholder="VD: Bánh mì Halal" className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Quy trình áp dụng</label>
                <select value={createForm.process_template_id} onChange={e => setCreateForm(f => ({ ...f, process_template_id: e.target.value }))}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none" style={inputStyle}>
                  <option value="">Không chọn quy trình</option>
                  {processes.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              {materials.length > 0 && (
                <div>
                  <label className="block text-xs font-medium mb-2" style={{ color: '#6B7280' }}>Nguyên liệu sử dụng</label>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {materials.map(m => (
                      <div key={m.id} className="flex items-center gap-2">
                        <input type="checkbox" checked={!!selectedMats[m.id]}
                          onChange={e => setSelectedMats(s => e.target.checked ? { ...s, [m.id]: '' } : Object.fromEntries(Object.entries(s).filter(([k]) => k !== m.id)))}
                          className="w-4 h-4 rounded" />
                        <span className="text-sm flex-1" style={{ color: '#374151' }}>{m.name}</span>
                        {selectedMats[m.id] !== undefined && (
                          <input type="number" value={selectedMats[m.id]} onChange={e => setSelectedMats(s => ({ ...s, [m.id]: e.target.value }))}
                            placeholder="SL" className="w-20 px-2 py-1 rounded text-xs outline-none" style={inputStyle} />
                        )}
                        {m.unit && selectedMats[m.id] !== undefined && (
                          <span className="text-xs" style={{ color: '#9CA3AF' }}>{m.unit}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: '#6B7280' }}>Ghi chú</label>
                <textarea value={createForm.notes} onChange={e => setCreateForm(f => ({ ...f, notes: e.target.value }))}
                  rows={2} className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-none" style={inputStyle} />
              </div>
              <button onClick={handleCreate} disabled={creating || !createForm.product_name}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{ background: !createForm.product_name ? '#E2E8F0' : '#087653', color: !createForm.product_name ? '#9CA3AF' : '#fff' }}>
                {creating ? 'Đang tạo...' : 'Tạo lô hàng'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Detail Modal ── */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-modal-overlay"
          style={{ background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)' }} onClick={() => setDetail(null)}>
          <div className="w-full max-w-2xl rounded-2xl animate-modal-content overflow-hidden"
            style={{ ...cardStyle, maxHeight: 'calc(100vh - 4rem)' }} onClick={e => e.stopPropagation()}>
            {detailLoading ? (
              <div className="py-16 text-center"><div className="w-8 h-8 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto" /></div>
            ) : detail && (
              <>
                {/* Header */}
                <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid #E2E8F0', background: '#F0F7F4' }}>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold" style={{ color: '#1A2332' }}>{detail.batch.batch_code}</h3>
                      {(() => { const st = STATUS[detail.batch.status as keyof typeof STATUS]; return st ? <span className="text-xs px-2 py-0.5 rounded animate-chip" style={{ background: st.bg, color: st.color }}>{st.label}</span> : null; })()}
                    </div>
                    <p className="text-sm mt-0.5" style={{ color: '#6B7280' }}>{detail.batch.product_name}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {detail.batch.status === 'draft' && (
                      <button onClick={() => updateBatchStatus(detail.batch.id, 'in_progress')}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: '#B45309' }}>
                        Bắt đầu SX
                      </button>
                    )}
                    {detail.batch.status === 'in_progress' && (
                      <button onClick={() => updateBatchStatus(detail.batch.id, 'completed')}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: '#059669' }}>
                        Hoàn thành
                      </button>
                    )}
                    {detail.batch.status === 'completed' && !detail.batch.integrity_hash && (
                      <button onClick={async () => {
                          const res = await fetch(`/api/api/supply-chain/batches/${detail.batch.id}/approve`, { method: 'POST', headers });
                          if (res.ok) {
                            const d = await res.json();
                            alert(`Lô hàng đã sealed!\n\nHash: ${d.integrity_hash}\n\nDữ liệu không thể thay đổi sau bước này.`);
                          } else {
                            const e = await res.json().catch(() => ({}));
                            alert(e.detail || 'Lỗi');
                          }
                          openDetail(detail.batch.id);
                          fetchBatches();
                        }}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: '#087653' }}>
                        Seal & Xác nhận
                      </button>
                    )}
                    {detail.batch.integrity_hash && (
                      <button onClick={async () => {
                          const res = await fetch(`/api/api/supply-chain/batches/${detail.batch.id}/verify`, { headers });
                          if (res.ok) {
                            const d = await res.json();
                            alert(d.verified
                              ? `Toàn vẹn: ${d.message}\n\nHash: ${d.stored_hash}`
                              : `CẢNH BÁO: ${d.message}\n\nHash lưu: ${d.stored_hash}\nHash tính: ${d.computed_hash}`);
                          }
                        }}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium"
                        style={{ background: '#ECFDF5', color: '#059669', border: '1px solid #A7F3D0' }}>
                        Xác minh toàn vẹn
                      </button>
                    )}
                    <button onClick={() => setDetail(null)} style={{ color: '#6B7280' }}>✕</button>
                  </div>
                </div>

                {/* Steps */}
                <div className="px-6 py-4 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 16rem)' }}>
                  {/* Batch timeline */}
                  <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: '#6B7280' }}>
                    {detail.batch.started_at && <span>Bắt đầu: <strong style={{ color: '#374151' }}>{new Date(detail.batch.started_at).toLocaleString('vi-VN')}</strong></span>}
                    {detail.batch.completed_at && <span>Hoàn thành: <strong style={{ color: '#374151' }}>{new Date(detail.batch.completed_at).toLocaleString('vi-VN')}</strong></span>}
                    {detail.batch.approved_by && (
                      <span style={{ color: '#059669' }}>
                        Xác nhận bởi: <strong>{detail.batch.approved_by}</strong> · {new Date(detail.batch.approved_at).toLocaleString('vi-VN')}
                      </span>
                    )}
                    {detail.batch.compliance_score != null && (
                      <span>Tiến độ: <strong style={{ color: detail.batch.compliance_score >= 100 ? '#059669' : '#B45309' }}>{detail.batch.compliance_score}%</strong></span>
                    )}
                    {detail.batch.integrity_hash && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium animate-chip" style={{ background: '#ECFDF5', color: '#059669', border: '1px solid #A7F3D0' }}>
                        SEALED · {detail.batch.integrity_hash.substring(0, 12)}...
                      </span>
                    )}
                  </div>

                  {/* Assignment */}
                  {!detail.batch.integrity_hash && user?.is_owner && (
                    <div className="mb-4 p-3 rounded-lg" style={{ background: '#F5F3FF', border: '1px solid #DDD6FE' }}>
                      <div className="flex items-center gap-3">
                        <div className="flex-1">
                          <p className="text-xs font-medium mb-1" style={{ color: '#7C3AED' }}>Ủy quyền xác nhận</p>
                          <select
                            value={detail.batch.assigned_to || ''}
                            onChange={e => { if (e.target.value) assignMember(detail.batch.id, e.target.value); }}
                            disabled={assigning}
                            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                            style={{ background: '#FFFFFF', border: '1px solid #DDD6FE', color: '#1A2332' }}>
                            <option value="">Chọn thành viên...</option>
                            {members.map(m => (
                              <option key={m.id} value={m.id}>{m.name} — {m.role}</option>
                            ))}
                          </select>
                        </div>
                        {detail.batch.assigned_name && (
                          <div className="text-right flex-shrink-0">
                            <p className="text-xs" style={{ color: '#9CA3AF' }}>Đang ủy quyền cho</p>
                            <p className="text-sm font-medium" style={{ color: '#7C3AED' }}>{detail.batch.assigned_name}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {detail.batch.assigned_name && detail.batch.integrity_hash && (
                    <div className="mb-4 text-xs" style={{ color: '#7C3AED' }}>
                      Ủy quyền: <strong>{detail.batch.assigned_name}</strong>
                    </div>
                  )}

                  {detail.steps?.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-bold mb-3" style={{ color: '#1A2332' }}>
                        Các bước ({detail.steps.filter((s: any) => s.status === 'completed').length}/{detail.steps.length})
                      </h4>
                      <div className="space-y-2">
                        {detail.steps.map((step: any, i: number) => (
                          <div key={step.id} className={`rounded-lg p-3 animate-list-item stagger-${Math.min(i + 1, 12)}`}
                            style={{
                              background: step.approved_by ? '#F0FDF4' : step.status === 'completed' ? '#ECFDF5' : '#FAFCF9',
                              border: `1px solid ${step.approved_by ? '#86EFAC' : '#E2E8F0'}`,
                            }}>
                            {/* Row 1: Step name + status */}
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-xs font-bold px-2 py-0.5 rounded"
                                style={{ background: step.status === 'completed' ? '#059669' : '#E2E8F0', color: step.status === 'completed' ? '#fff' : '#6B7280' }}>
                                #{i + 1}
                              </span>
                              <span className="text-sm font-medium" style={{ color: '#1A2332' }}>{step.step_name}</span>
                              {step.approved_by && (
                                <svg className="w-4 h-4 ml-auto" style={{ color: '#059669' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                              )}
                            </div>

                            {/* Row 2: Performer input + photo upload (editable when not approved) */}
                            {!step.approved_by && (
                              <div className="flex items-center gap-2 mb-2">
                                <input
                                  type="text"
                                  defaultValue={step.performed_by || ''}
                                  placeholder="Tên nhân viên thực hiện..."
                                  onBlur={e => {
                                    if (e.target.value !== (step.performed_by || '')) {
                                      updateStep(detail.batch.id, step.id, { performed_by: e.target.value });
                                    }
                                  }}
                                  className="flex-1 px-3 py-1.5 rounded-lg text-xs outline-none"
                                  style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#1A2332' }}
                                />
                                <label className="px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-all hover:scale-105"
                                  style={{ background: '#F0F9FF', color: '#0369A1', border: '1px solid #BAE6FD' }}>
                                  <input type="file" className="hidden" accept="image/*"
                                    onChange={async e => {
                                      const f = e.target.files?.[0];
                                      if (!f) return;
                                      const fd = new FormData(); fd.append('file', f);
                                      await fetch(`/api/api/supply-chain/batches/${detail.batch.id}/steps/${step.id}/photo`, {
                                        method: 'POST', headers, body: fd,
                                      });
                                      openDetail(detail.batch.id);
                                    }} />
                                  {step.photo_path ? 'Đổi ảnh' : 'Upload ảnh'}
                                </label>
                              </div>
                            )}

                            {/* Row 3: Info line */}
                            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs" style={{ color: '#9CA3AF' }}>
                              {step.performed_by && step.approved_by && (
                                <span>Thực hiện: <strong style={{ color: '#374151' }}>{step.performed_by}</strong></span>
                              )}
                              {step.started_at && <span>BĐ: {new Date(step.started_at).toLocaleString('vi-VN')}</span>}
                              {step.completed_at && <span>KT: {new Date(step.completed_at).toLocaleString('vi-VN')}</span>}
                              {step.photo_path && (
                                <button onClick={() => window.open(`/api/api/supply-chain/batches/${detail.batch.id}/steps/${step.id}/photo/view?token=${encodeURIComponent(token || '')}`, '_blank')}
                                  className="flex items-center gap-1 px-2 py-0.5 rounded transition-all hover:scale-105"
                                  style={{ background: '#F0F9FF', color: '#0369A1', border: '1px solid #BAE6FD' }}>
                                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                  </svg>
                                  Xem ảnh
                                </button>
                              )}
                            </div>

                            {/* Row 4: Approval */}
                            {step.approved_by ? (
                              <div className="flex items-center gap-1 mt-2 text-xs" style={{ color: '#059669' }}>
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                                Xác nhận bởi {step.approved_by} · {new Date(step.approved_at).toLocaleString('vi-VN')}
                              </div>
                            ) : (
                              <div className="flex items-center gap-2 mt-2">
                                {step.status !== 'completed' ? (
                                  <button onClick={() => updateStep(detail.batch.id, step.id, { status: 'completed' })}
                                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: '#087653' }}>
                                    Hoàn thành bước
                                  </button>
                                ) : (
                                  <>
                                    <button onClick={async () => {
                                        await fetch(`/api/api/supply-chain/batches/${detail.batch.id}/steps/${step.id}/approve`, { method: 'POST', headers });
                                        openDetail(detail.batch.id);
                                      }}
                                      className="px-3 py-1.5 rounded-lg text-xs font-medium"
                                      style={{ background: '#FFFBEB', color: '#B45309', border: '1px solid #FDE68A' }}>
                                      Xác nhận
                                    </button>
                                    <button onClick={() => updateStep(detail.batch.id, step.id, { status: 'pending' })}
                                      className="px-3 py-1.5 rounded-lg text-xs" style={{ color: '#9CA3AF', border: '1px solid #E2E8F0' }}>
                                      Hoàn tác
                                    </button>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Materials used */}
                  {detail.materials?.length > 0 && (
                    <div>
                      <h4 className="text-sm font-bold mb-2" style={{ color: '#1A2332' }}>Nguyên liệu ({detail.materials.length})</h4>
                      <div className="space-y-1">
                        {detail.materials.map((m: any) => (
                          <div key={m.material_id} className="flex items-center justify-between text-sm px-3 py-2 rounded-lg" style={{ background: '#FAFCF9' }}>
                            <span style={{ color: '#374151' }}>{m.material_name} {m.sku && `(${m.sku})`}</span>
                            <span style={{ color: '#9CA3AF' }}>{m.quantity} {m.unit} · {m.supplier_name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
