'use client';

import { useState, useEffect, useCallback, useRef, use } from 'react';
import { useRouter } from 'next/navigation';
import { useUserAuth } from '@/components/UserAuthContext';
import { openAuthed } from '@/lib/authedOpen';

/* ── Types ── */
interface Visit {
  id: string; business_tenant: string; business_name: string; auditor_name: string | null;
  visit_type: string; status: string; location: string | null; notes: string | null;
  scheduled_date: string | null; compliance_score: number | null;
  report_pdf_path: boolean; start_gps: { lat: number; lng: number } | null;
  end_gps: { lat: number; lng: number } | null;
  has_auditor_sig: boolean; has_business_sig: boolean; created_at: string;
}
interface ChecklistItem {
  id: string; code: string; category: string; criteria: string; clause: string;
  severity: string; result: string | null; note: string | null; photo_paths: string[];
  audit_method: string; documents: string; evidence: string; corrective_action: string;
  corrective_status: string | null;
}
interface NCR {
  id: string; description: string; severity: string; status: string;
  corrective_action: string | null; deadline: string | null;
  photo_paths: string[]; evidence_paths: string[]; created_at: string;
}

/* ── Constants ── */
const VISIT_TYPE: Record<string, { label: string; bg: string; color: string }> = {
  initial: { label: 'Lần đầu', bg: '#DBEAFE', color: '#2563EB' },
  renewal: { label: 'Gia hạn', bg: '#E8F5EF', color: '#0F5132' },
  surprise: { label: 'Đột xuất', bg: '#FEF3C7', color: '#D97706' },
  surveillance: { label: 'Giám sát', bg: '#F3E8FF', color: '#7C3AED' },
  special: { label: 'Đặc biệt', bg: '#FEF3C7', color: '#D97706' },
};
const STATUS: Record<string, { label: string; bg: string; color: string }> = {
  scheduled: { label: 'Lên lịch', bg: '#F3F4F6', color: '#6B7280' },
  in_progress: { label: 'Đang kiểm', bg: '#DBEAFE', color: '#2563EB' },
  completed: { label: 'Hoàn thành', bg: '#E8F5EF', color: '#0F5132' },
  report_submitted: { label: 'Đã gửi BC', bg: '#F3E8FF', color: '#7C3AED' },
};
const SEVERITY: Record<string, { label: string; bg: string; color: string }> = {
  critical: { label: 'Nghiêm trọng', bg: '#FEF2F2', color: '#DC2626' },
  major: { label: 'Lớn', bg: '#FFF7ED', color: '#D97706' },
  minor: { label: 'Nhỏ', bg: '#F3F4F6', color: '#6B7280' },
};
const NCR_STATUS: Record<string, { label: string; bg: string; color: string }> = {
  open: { label: 'Mở', bg: '#FEF2F2', color: '#DC2626' },
  in_review: { label: 'Đang xét', bg: '#DBEAFE', color: '#2563EB' },
  closed: { label: 'Đã đóng', bg: '#E8F5EF', color: '#0F5132' },
};
const RESULTS = [
  { value: 'conform', label: 'C (Đạt)', color: '#0F5132' },
  { value: 'minor_nc', label: 'Minor NC', color: '#D97706' },
  { value: 'major_nc', label: 'Major NC', color: '#DC2626' },
  { value: 'na', label: 'N/A', color: '#6B7280' },
  { value: 'observation', label: 'Quan sát', color: '#2563EB' },
];
const CORRECTIVE_STATUSES = [
  { value: 'pending', label: 'Chờ xử lý' },
  { value: 'in_progress', label: 'Đang xử lý' },
  { value: 'completed', label: 'Hoàn thành' },
];

const Badge = ({ map, value }: { map: Record<string, { label: string; bg: string; color: string }>; value: string }) => {
  const m = map[value] || { label: value, bg: '#F3F4F6', color: '#6B7280' };
  return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap" style={{ background: m.bg, color: m.color }}>{m.label}</span>;
};

const fmtDate = (iso: string | null) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return iso; }
};

type Tab = 'overview' | 'checklist' | 'ncr' | 'report';
const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Tổng quan' },
  { key: 'checklist', label: 'Checklist' },
  { key: 'ncr', label: 'Sai phạm' },
  { key: 'report', label: 'Báo cáo' },
];

/* ── Main Component ── */
export default function AuditVisitDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { user, token, isAuthenticated, loading: authLoading } = useUserAuth();

  const [visit, setVisit] = useState<Visit | null>(null);
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [ncrs, setNcrs] = useState<NCR[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>('overview');

  // Debounce refs for checklist field updates
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Add-item form
  const [showAddItem, setShowAddItem] = useState(false);
  const [newItem, setNewItem] = useState({ code: '', category: '', criteria: '', severity: 'minor', clause: '', audit_method: '', documents: '' });

  // Add-NCR form
  const [showAddNcr, setShowAddNcr] = useState(false);
  const [newNcr, setNewNcr] = useState({ description: '', severity: 'major', corrective_action: '', deadline: '' });

  // Decision
  const [decisionNotes, setDecisionNotes] = useState('');

  // Signature canvas refs
  const auditorCanvasRef = useRef<HTMLCanvasElement>(null);
  const businessCanvasRef = useRef<HTMLCanvasElement>(null);

  const headers = useCallback(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);
  const api = useCallback((path: string, opts?: RequestInit) =>
    fetch(`/api/api/audits/${id}${path}`, { ...opts, headers: { ...headers(), ...opts?.headers } }), [id, headers]);

  /* ── Fetch data ── */
  const fetchData = useCallback(async () => {
    try {
      const res = await api('');
      if (!res.ok) throw new Error('Không tải được dữ liệu');
      const data = await res.json();
      setVisit(data.visit);
      setItems(data.items || []);
      setNcrs(data.ncrs || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lỗi tải dữ liệu');
    } finally {
      setFetching(false);
    }
  }, [api]);

  useEffect(() => {
    if (!authLoading && isAuthenticated && token) fetchData();
  }, [authLoading, isAuthenticated, token, fetchData]);

  /* ── Auth guard ── */
  if (authLoading || fetching) return (
    <div className="grid place-items-center min-h-[60vh]">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
        <div className="w-2 h-2 rounded-full bg-[#0F5132] animate-pulse-dot" />
      </div>
    </div>
  );
  if (!isAuthenticated || !user || user.role !== 'provider') {
    return <div className="grid place-items-center min-h-[60vh] text-sm" style={{ color: '#6B7280' }}>Bạn không có quyền truy cập trang này.</div>;
  }
  if (error) return <div className="grid place-items-center min-h-[60vh] text-sm" style={{ color: '#DC2626' }}>{error}</div>;
  if (!visit) return <div className="grid place-items-center min-h-[60vh] text-sm" style={{ color: '#6B7280' }}>Không tìm thấy cuộc kiểm tra.</div>;

  /* ── Actions ── */
  const updateStatus = async (status: string) => {
    await api('/status', { method: 'PUT', body: JSON.stringify({ status }) });
    fetchData();
  };

  const captureGPS = async (type: 'start' | 'end') => {
    if (!navigator.geolocation) return alert('Trình duyệt không hỗ trợ GPS');
    navigator.geolocation.getCurrentPosition(async (pos) => {
      await api('/gps', { method: 'PUT', body: JSON.stringify({ type, lat: pos.coords.latitude, lng: pos.coords.longitude }) });
      fetchData();
    }, () => alert('Không lấy được vị trí GPS'));
  };

  const updateItemField = (itemId: string, field: string, value: string) => {
    // Optimistic update
    setItems(prev => prev.map(it => it.id === itemId ? { ...it, [field]: value } : it));
    const key = `${itemId}-${field}`;
    clearTimeout(debounceTimers.current[key]);
    debounceTimers.current[key] = setTimeout(async () => {
      await api(`/items/${itemId}`, { method: 'PUT', body: JSON.stringify({ [field]: value }) });
    }, 600);
  };

  const setItemResult = async (itemId: string, result: string) => {
    setItems(prev => prev.map(it => it.id === itemId ? { ...it, result } : it));
    await api(`/items/${itemId}`, { method: 'PUT', body: JSON.stringify({ result }) });
  };

  const deleteItem = async (itemId: string) => {
    if (!confirm('Xóa hạng mục này?')) return;
    await api(`/items/${itemId}`, { method: 'DELETE' });
    setItems(prev => prev.filter(it => it.id !== itemId));
  };

  const addItem = async () => {
    if (!newItem.code || !newItem.criteria) return alert('Cần nhập mã và tiêu chí');
    await api('/items', { method: 'POST', body: JSON.stringify(newItem) });
    setNewItem({ code: '', category: '', criteria: '', severity: 'minor', clause: '', audit_method: '', documents: '' });
    setShowAddItem(false);
    fetchData();
  };

  const populateChecklist = async () => {
    await api('/populate-checklist', { method: 'POST' });
    fetchData();
  };

  const addNcr = async () => {
    if (!newNcr.description) return alert('Cần nhập mô tả');
    await api('/ncr', { method: 'POST', body: JSON.stringify(newNcr) });
    setNewNcr({ description: '', severity: 'major', corrective_action: '', deadline: '' });
    setShowAddNcr(false);
    fetchData();
  };

  const uploadItemPhoto = async (itemId: string, file: File) => {
    const fd = new FormData(); fd.append('file', file);
    await fetch(`/api/api/audits/${id}/items/${itemId}/photo`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd });
    fetchData();
  };

  const uploadNcrPhoto = async (ncrId: string, file: File) => {
    const fd = new FormData(); fd.append('file', file);
    await fetch(`/api/api/audits/${id}/ncr/${ncrId}/photo`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd });
    fetchData();
  };

  const generateReport = async () => {
    await api('/generate-report', { method: 'POST' });
    fetchData();
  };

  const downloadReport = () => {
    openAuthed(`/api/api/audits/${id}/report-pdf`, token || '');
  };

  const submitDecision = async (decision: string) => {
    if (!confirm(`Xác nhận: ${decision}?`)) return;
    await api('/decision', { method: 'POST', body: JSON.stringify({ decision, notes: decisionNotes }) });
    fetchData();
  };

  const uploadSignature = async (type: 'auditor' | 'business', canvas: HTMLCanvasElement | null) => {
    if (!canvas) return;
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const fd = new FormData(); fd.append('file', blob, `${type}-signature.png`);
      await fetch(`/api/api/audits/${id}/signature?type=${type}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd });
      fetchData();
    });
  };

  /* ── Derived data ── */
  const grouped = items.reduce<Record<string, ChecklistItem[]>>((acc, it) => {
    (acc[it.category || 'Khác'] ||= []).push(it);
    return acc;
  }, {});
  const counts = { conform: 0, minor_nc: 0, major_nc: 0, na: 0, observation: 0 };
  items.forEach(it => { if (it.result && it.result in counts) counts[it.result as keyof typeof counts]++; });

  /* ── Style helpers (Tailwind class strings) ── */
  const card = "bg-white rounded-xl p-4 mb-3 border border-[#E2E8F0]";
  const btnPrimary = "w-full py-3.5 rounded-xl border-none bg-[#0F5132] text-white text-base font-bold cursor-pointer transition-all active:scale-[0.98]";
  const btnOutline = "px-4 py-2.5 rounded-lg border-[1.5px] border-[#E2E8F0] bg-white text-sm font-semibold cursor-pointer transition-all active:scale-[0.98] text-center";
  const inputCls = "w-full px-3 py-2.5 rounded-lg border border-[#E2E8F0] text-sm outline-none transition-all focus:border-[rgba(15,81,50,0.4)] focus:shadow-[0_0_0_3px_rgba(15,81,50,0.08)]";
  const labelCls = "text-xs font-semibold text-[#6B7280] mb-1 block";

  /* ── Canvas drawing helpers ── */
  const setupCanvas = (canvas: HTMLCanvasElement | null) => {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    let drawing = false;
    canvas.onpointerdown = (e) => { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); };
    canvas.onpointermove = (e) => { if (!drawing) return; ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); };
    canvas.onpointerup = () => { drawing = false; };
    canvas.onpointerleave = () => { drawing = false; };
  };

  /* ── Tab Content Renderers ── */

  const renderOverview = () => (
    <div className="animate-tab-content">
      {/* Visit Info */}
      <div className={card}>
        <h2 className="text-lg font-bold mb-2" style={{ color: '#0F5132' }}>{visit.business_name}</h2>
        <div className="flex flex-wrap gap-2 mb-3">
          <Badge map={VISIT_TYPE} value={visit.visit_type} />
          <Badge map={STATUS} value={visit.status} />
        </div>
        <div className="text-sm space-y-1" style={{ color: '#374151' }}>
          {visit.location && <div className="flex items-center gap-1.5">📍 {visit.location}</div>}
          <div className="flex items-center gap-1.5">📅 {fmtDate(visit.scheduled_date)}</div>
          {visit.auditor_name && <div className="flex items-center gap-1.5">👤 {visit.auditor_name}</div>}
          {visit.notes && <div className="text-xs mt-1" style={{ color: '#6B7280' }}>{visit.notes}</div>}
        </div>
      </div>

      {/* Action buttons */}
      {visit.status === 'scheduled' && (
        <button className={`${btnPrimary} mb-3`} onClick={() => updateStatus('in_progress')}>
          Bắt đầu kiểm tra
        </button>
      )}
      {visit.status === 'in_progress' && (
        <button className={`${btnPrimary} mb-3 !bg-[#2563EB]`} onClick={() => updateStatus('completed')}>
          Hoàn thành kiểm tra
        </button>
      )}

      {/* GPS */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <button className={`${btnOutline} ${visit.start_gps ? 'text-[#0F5132] border-[#0F5132]' : ''}`} onClick={() => captureGPS('start')}>
          {visit.start_gps ? '✓ GPS bắt đầu' : 'Ghi GPS bắt đầu'}
        </button>
        <button className={`${btnOutline} ${visit.end_gps ? 'text-[#0F5132] border-[#0F5132]' : ''}`} onClick={() => captureGPS('end')}>
          {visit.end_gps ? '✓ GPS kết thúc' : 'Ghi GPS kết thúc'}
        </button>
      </div>

      {/* Compliance score */}
      {visit.compliance_score != null && (
        <div className={`${card} text-center`}>
          <div className="w-24 h-24 rounded-full mx-auto mb-2 flex items-center justify-center text-2xl font-bold"
            style={{ border: `6px solid ${visit.compliance_score >= 80 ? '#0F5132' : visit.compliance_score >= 60 ? '#D97706' : '#DC2626'}`,
                     color: visit.compliance_score >= 80 ? '#0F5132' : visit.compliance_score >= 60 ? '#D97706' : '#DC2626' }}>
            {visit.compliance_score}%
          </div>
          <div className="text-sm" style={{ color: '#6B7280' }}>Điểm tuân thủ</div>
        </div>
      )}

      {/* Signatures */}
      {(visit.status === 'in_progress' || visit.status === 'completed') && (
        <div className={card}>
          <h3 className="text-base font-bold mb-3" style={{ color: '#0F5132' }}>Chữ ký</h3>
          {(['auditor', 'business'] as const).map(type => {
            const done = type === 'auditor' ? visit.has_auditor_sig : visit.has_business_sig;
            const ref = type === 'auditor' ? auditorCanvasRef : businessCanvasRef;
            return (
              <div key={type} className="mb-4">
                <label className={labelCls}>{type === 'auditor' ? 'Kiểm tra viên' : 'Doanh nghiệp'} {done && <span className="text-[#0F5132]">✓ Đã ký</span>}</label>
                {!done && (
                  <>
                    <canvas ref={(el) => { (ref as React.MutableRefObject<HTMLCanvasElement | null>).current = el; setupCanvas(el); }}
                      width={300} height={120} className="border border-[#E2E8F0] rounded-lg w-full max-w-[300px]" style={{ touchAction: 'none' }} />
                    <button className={`${btnOutline} mt-2`} onClick={() => uploadSignature(type, ref.current)}>Lưu chữ ký</button>
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderChecklist = () => (
    <div className="animate-tab-content">
      {/* Summary bar */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {RESULTS.map(r => (
          <span key={r.value} className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: `${r.color}15`, color: r.color }}>
            {r.label}: {counts[r.value as keyof typeof counts]}
          </span>
        ))}
        <span className="px-2.5 py-1 rounded-full text-xs font-semibold" style={{ background: '#F3F4F6', color: '#374151' }}>
          Tổng: {items.length}
        </span>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 mb-3">
        <button className={`${btnOutline} ${showAddItem ? '!text-red-500 !border-red-300' : '!text-[#0F5132] !border-[#0F5132]'}`}
          onClick={() => setShowAddItem(!showAddItem)}>{showAddItem ? 'Hủy' : '+ Thêm hạng mục'}</button>
        {items.length === 0 && <button className={`${btnOutline} !text-[#2563EB] !border-[#2563EB]`} onClick={populateChecklist}>Tạo từ template</button>}
      </div>

      {/* Add item form */}
      {showAddItem && (
        <div className="bg-[#F7F1E6] rounded-xl p-4 mb-3 border border-[#B7CBB8] space-y-3 animate-modal-content">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div><label className={labelCls}>Mã</label><input className={inputCls} placeholder="VD: HL-01" value={newItem.code} onChange={e => setNewItem({...newItem, code: e.target.value})} /></div>
            <div><label className={labelCls}>Danh mục</label><input className={inputCls} placeholder="VD: Vệ sinh" value={newItem.category} onChange={e => setNewItem({...newItem, category: e.target.value})} /></div>
          </div>
          <div><label className={labelCls}>Tiêu chí *</label><textarea className={`${inputCls} resize-none`} rows={2} placeholder="Mô tả tiêu chí kiểm tra" value={newItem.criteria} onChange={e => setNewItem({...newItem, criteria: e.target.value})} /></div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div><label className={labelCls}>Điều khoản</label><input className={inputCls} placeholder="VD: TCVN 4.1.1" value={newItem.clause} onChange={e => setNewItem({...newItem, clause: e.target.value})} /></div>
            <div><label className={labelCls}>Phương pháp</label><input className={inputCls} placeholder="Kiểm tra, phỏng vấn..." value={newItem.audit_method} onChange={e => setNewItem({...newItem, audit_method: e.target.value})} /></div>
            <div><label className={labelCls}>Mức độ</label><select className={inputCls} value={newItem.severity} onChange={e => setNewItem({...newItem, severity: e.target.value})}><option value="minor">Nhỏ</option><option value="major">Lớn</option><option value="critical">Nghiêm trọng</option></select></div>
          </div>
          <div><label className={labelCls}>Tài liệu tham chiếu</label><input className={inputCls} placeholder="VD: SOP vệ sinh, sổ nhật ký..." value={newItem.documents} onChange={e => setNewItem({...newItem, documents: e.target.value})} /></div>
          <div className="flex gap-2 pt-1">
            <button className={`${btnPrimary} !text-sm flex-1`} onClick={addItem}>Thêm hạng mục</button>
            <button className={`${btnOutline} text-center flex-1`} onClick={() => setShowAddItem(false)}>Hủy</button>
          </div>
        </div>
      )}

      {/* Items grouped by category */}
      {Object.entries(grouped).map(([cat, catItems]) => (
        <div key={cat} className="mb-4">
          <h3 className="text-sm font-bold py-2 mb-2 border-b-2 border-[#E2E8F0]" style={{ color: '#0F5132' }}>{cat}</h3>
          {catItems.map(item => {
            const sev = SEVERITY[item.severity] || SEVERITY.minor;
            return (
            <div key={item.id} className={`${card} doc-card-hover`}>
              {/* Top row */}
              <div className="flex items-start gap-2 mb-2">
                {item.code && <span className="px-2 py-0.5 rounded text-xs font-bold flex-shrink-0" style={{ background: '#DBEAFE', color: '#2563EB' }}>{item.code}</span>}
                <span className="flex-1 text-sm leading-snug" style={{ color: '#0F5132' }}>{item.criteria}</span>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0" style={{ background: sev.bg, color: sev.color }}>{sev.label}</span>
                <button onClick={() => deleteItem(item.id)} className="text-[#9CA3AF] hover:text-red-500 transition-colors text-lg leading-none px-1">×</button>
              </div>
              {item.clause && <p className="text-xs mb-2" style={{ color: '#94A3B8' }}>Điều khoản: {item.clause}</p>}
              {item.audit_method && <p className="text-xs mb-2"><span className="px-1.5 py-0.5 rounded" style={{ background: '#F3E8FF', color: '#7C3AED' }}>{item.audit_method}</span></p>}

              {/* Result pills */}
              <div className="grid grid-cols-5 gap-1 mb-2.5">
                {RESULTS.map(r => {
                  const active = item.result === r.value;
                  return (
                    <button key={r.value} onClick={() => setItemResult(item.id, r.value)}
                      className="py-2 rounded-full text-xs font-bold transition-all active:scale-95"
                      style={{ border: `1.5px solid ${r.color}`, background: active ? r.color : '#fff', color: active ? '#fff' : r.color }}>
                      {r.label}
                    </button>
                  );
                })}
              </div>

              {/* Evidence */}
              <textarea className={`${inputCls} resize-none mb-1`} rows={1} placeholder="Bằng chứng / quan sát..."
                value={item.evidence || ''} onChange={e => updateItemField(item.id, 'evidence', e.target.value)} />

              {/* Corrective action */}
              {(item.result === 'minor_nc' || item.result === 'major_nc') && (
                <div className="mt-1.5 p-2.5 rounded-lg" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                  <textarea className={`${inputCls} resize-none !border-red-200 mb-1.5`} rows={1} placeholder="Hành động khắc phục..."
                    value={item.corrective_action || ''} onChange={e => updateItemField(item.id, 'corrective_action', e.target.value)} />
                  <select className={`${inputCls} !border-red-200`}
                    value={item.corrective_status || 'pending'} onChange={e => updateItemField(item.id, 'corrective_status', e.target.value)}>
                    {CORRECTIVE_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
              )}

              {/* Note + Photo */}
              <div className="flex gap-2 mt-2 items-center">
                <input className={`${inputCls} flex-1`} placeholder="Ghi chú..."
                  value={item.note || ''} onChange={e => updateItemField(item.id, 'note', e.target.value)} />
                <label className={`${btnOutline} !px-3 !py-2 inline-flex items-center gap-1 flex-shrink-0 cursor-pointer`}>
                  📷 {item.photo_paths?.length || 0}
                  <input type="file" accept="image/*" capture="environment" className="hidden"
                    onChange={e => { const f = e.target.files?.[0]; if (f) uploadItemPhoto(item.id, f); e.target.value = ''; }} />
                </label>
              </div>
            </div>
          );})}
        </div>
      ))}
    </div>
  );

  const renderNcr = () => (
    <div className="animate-tab-content">
      <button className={`${btnOutline} w-full mb-3 text-center !text-red-500 !border-red-300`}
        onClick={() => setShowAddNcr(!showAddNcr)}>{showAddNcr ? 'Hủy' : '+ Thêm NCR'}</button>

      {showAddNcr && (
        <div className="bg-red-50 rounded-xl p-4 mb-3 border border-red-200 space-y-2 animate-modal-content">
          <div><label className={labelCls}>Mô tả *</label><textarea className={`${inputCls} resize-none`} rows={2} value={newNcr.description} onChange={e => setNewNcr({...newNcr, description: e.target.value})} /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className={labelCls}>Mức độ</label><select className={inputCls} value={newNcr.severity} onChange={e => setNewNcr({...newNcr, severity: e.target.value})}><option value="minor">Nhỏ</option><option value="major">Lớn</option><option value="critical">Nghiêm trọng</option></select></div>
            <div><label className={labelCls}>Hạn chót</label><input type="date" className={inputCls} value={newNcr.deadline} onChange={e => setNewNcr({...newNcr, deadline: e.target.value})} /></div>
          </div>
          <div><label className={labelCls}>Hành động khắc phục</label><textarea className={`${inputCls} resize-none`} rows={1} value={newNcr.corrective_action} onChange={e => setNewNcr({...newNcr, corrective_action: e.target.value})} /></div>
          <div className="grid grid-cols-2 gap-2">
            <button className={`${btnPrimary} !bg-red-600 !text-sm`} onClick={addNcr}>Thêm NCR</button>
            <button className={`${btnOutline} text-center`} onClick={() => setShowAddNcr(false)}>Hủy</button>
          </div>
        </div>
      )}

      {ncrs.length === 0 && !showAddNcr && (
        <div className="text-center py-8 text-sm" style={{ color: '#94A3B8' }}>Chưa có sai phạm nào</div>
      )}

      {ncrs.map(ncr => (
        <div key={ncr.id} className={`${card} doc-card-hover`}>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge map={SEVERITY} value={ncr.severity} />
            <Badge map={NCR_STATUS} value={ncr.status} />
            {ncr.deadline && <span className="text-xs ml-auto" style={{ color: '#6B7280' }}>Hạn: {fmtDate(ncr.deadline)}</span>}
          </div>
          <p className="text-sm mb-2 leading-relaxed" style={{ color: '#0F5132' }}>{ncr.description}</p>
          {ncr.corrective_action && <p className="text-xs" style={{ color: '#374151' }}><strong>Khắc phục:</strong> {ncr.corrective_action}</p>}
          {ncr.photo_paths?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {ncr.photo_paths.map((p, i) => <img key={i} src={p} alt="" className="w-16 h-16 object-cover rounded-lg" />)}
            </div>
          )}
          <label className={`${btnOutline} mt-2 inline-flex items-center gap-1 text-xs cursor-pointer`}>
            📷 Thêm ảnh
            <input type="file" accept="image/*" capture="environment" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) uploadNcrPhoto(ncr.id, f); e.target.value = ''; }} />
          </label>
        </div>
      ))}
    </div>
  );

  const renderReport = () => (
    <div className="animate-tab-content">
      <div className={card}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#0F5132' }}>Báo cáo PDF</h3>
        <button className={`${btnPrimary} mb-2`} onClick={generateReport}>Xuất báo cáo PDF</button>
        {visit.report_pdf_path && (
          <button className={`${btnOutline} w-full text-center !text-[#0EA5E9] !border-[#0EA5E9]`} onClick={downloadReport}>📥 Tải báo cáo PDF</button>
        )}
      </div>

      {user?.is_owner && (
        <div className={card}>
          <h3 className="text-base font-bold mb-3" style={{ color: '#0F5132' }}>Quyết định chứng nhận</h3>
          <textarea className={`${inputCls} resize-none mb-3`} rows={2} placeholder="Ghi chú quyết định..."
            value={decisionNotes} onChange={e => setDecisionNotes(e.target.value)} />
          <div className="grid grid-cols-3 gap-2">
            <button className={`${btnPrimary} !text-sm`} onClick={() => submitDecision('renew')}>Gia hạn</button>
            <button className={`${btnPrimary} !text-sm !bg-[#D97706]`} onClick={() => submitDecision('suspend')}>Tạm đình chỉ</button>
            <button className={`${btnPrimary} !text-sm !bg-[#DC2626]`} onClick={() => submitDecision('revoke')}>Thu hồi</button>
          </div>
        </div>
      )}
    </div>
  );

  /* ── Render ── */
  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* Header */}
      <div className="flex items-center gap-3 py-4">
        <button onClick={() => router.push('/audits')}
          className="w-9 h-9 rounded-xl grid place-items-center flex-shrink-0 transition-all hover:bg-black/5"
          style={{ border: '1px solid #E2E8F0' }}>
          <svg className="w-5 h-5" style={{ color: '#6B7280' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h1 className="text-lg font-bold" style={{ color: '#0F5132' }}>Chi tiết kiểm tra</h1>
      </div>

      {/* Tabs */}
      <div className="grid grid-cols-4 gap-1 mb-4 p-1 rounded-xl" style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className="py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: tab === t.key ? '#0F5132' : 'transparent',
              color: tab === t.key ? '#FFFFFF' : '#6B7280',
              boxShadow: tab === t.key ? '0 2px 8px rgba(15,81,50,0.25)' : 'none',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && renderOverview()}
      {tab === 'checklist' && renderChecklist()}
      {tab === 'ncr' && renderNcr()}
      {tab === 'report' && renderReport()}
    </div>
  );
}
