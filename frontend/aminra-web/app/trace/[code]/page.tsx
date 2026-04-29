'use client';

import { useState, useEffect, use } from 'react';

interface TraceData {
  batch: {
    batch_code: string;
    product_name: string;
    status: string;
    company_name: string;
    process_name: string | null;
    process_description: string | null;
    started_at: string | null;
    completed_at: string | null;
    compliance_score: number | null;
    created_at: string;
  };
  integrity: {
    sealed: boolean;
    verified: boolean;
    hash: string;
    sealed_at: string;
    sealed_by: string;
  } | null;
  progress: { total: number; completed: number; percent: number };
  steps: Array<{
    name: string;
    performed_by: string | null;
    started_at: string | null;
    completed_at: string | null;
    status: string;
    approved_by: string | null;
  }>;
  materials: Array<{
    name: string;
    sku: string | null;
    category: string | null;
    halal_risk: string;
    supplier_name: string | null;
    supplier_verified: boolean;
    quantity: string | null;
    unit: string | null;
  }>;
  certificates: Array<{
    supplier_name: string;
    cert_type: string;
    cert_number: string;
    issuing_body: string;
    issued_date: string | null;
    expiry_date: string | null;
  }>;
}

const STATUS_MAP: Record<string, { label: string; bg: string; color: string; icon: string }> = {
  draft:       { label: 'Nháp',        bg: '#F3F4F6', color: '#6B7280', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' },
  in_progress: { label: 'Đang sản xuất', bg: '#FFFBEB', color: '#B45309', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  completed:   { label: 'Hoàn thành',  bg: '#DCE3F0', color: '#102A5C', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  rejected:    { label: 'Từ chối',     bg: '#FEF2F2', color: '#DC2626', icon: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' },
};

const RISK_MAP: Record<string, { label: string; bg: string; color: string }> = {
  safe:          { label: 'An toàn',     bg: '#DCE3F0', color: '#102A5C' },
  requires_cert: { label: 'Cần chứng nhận', bg: '#FFFBEB', color: '#B45309' },
  prohibited:    { label: 'Cấm',        bg: '#FEF2F2', color: '#DC2626' },
  unknown:       { label: 'Chưa xác định', bg: '#F3F4F6', color: '#6B7280' },
};

function formatDate(iso: string | null) {
  if (!iso || iso === 'None') return null;
  try {
    return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

export default function TracePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const [data, setData] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    fetch(`/api/api/supply-chain/batches/trace/${encodeURIComponent(code)}`)
      .then(r => {
        if (r.status === 404) throw new Error('not_found');
        if (!r.ok) throw new Error('error');
        return r.json();
      })
      .then(d => setData(d))
      .catch(e => setError(e.message === 'not_found' ? 'not_found' : 'error'))
      .finally(() => setLoading(false));
  }, [code]);

  // Loading
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#F5F1E8' }}>
        <div className="text-center animate-scale-in">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl grid place-items-center" style={{ background: '#0A1F44' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-10 h-10" />
          </div>
          <div className="flex items-center justify-center gap-2 mt-4">
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          </div>
          <p className="text-sm mt-3" style={{ color: '#6B7280' }}>Đang tải thông tin truy xuất...</p>
        </div>
      </div>
    );
  }

  // Error
  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#F5F1E8' }}>
        <div className="text-center animate-scale-in max-w-md px-6">
          <div className="w-20 h-20 mx-auto mb-5 rounded-full grid place-items-center animate-empty-icon"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <svg className="w-10 h-10" style={{ color: '#EF4444' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ color: '#0A1F44' }}>
            {error === 'not_found' ? 'Không tìm thấy lô hàng' : 'Đã xảy ra lỗi'}
          </h1>
          <p className="text-sm" style={{ color: '#6B7280' }}>
            {error === 'not_found'
              ? 'Mã lô hàng không tồn tại hoặc chưa sẵn sàng để truy xuất công khai.'
              : 'Không thể tải thông tin truy xuất. Vui lòng thử lại.'}
          </p>
          <div className="mt-6 pt-4" style={{ borderTop: '1px solid #E2E8F0' }}>
            <p className="text-xs" style={{ color: '#94A3B8' }}>Powered by AMINRA · Halal Supply Chain Integrity</p>
          </div>
        </div>
      </div>
    );
  }

  const { batch, integrity, progress, steps, materials, certificates } = data;
  const st = STATUS_MAP[batch.status] || STATUS_MAP.draft;

  return (
    <div className="min-h-screen" style={{ background: '#F5F1E8' }} data-page>

      {/* ── Hero header ── */}
      <div style={{ background: 'linear-gradient(135deg, #0A1F44 0%, #0A1F44 50%, #0A9B6C 100%)' }}>
        <div className="max-w-2xl mx-auto px-5 py-8 md:py-12">
          <div className="flex items-center gap-3 mb-6 animate-section">
            <div className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
              style={{ background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-7 h-7" />
            </div>
            <div>
              <p className="text-white/60 text-xs font-medium tracking-wider uppercase">AMINRA Truy xuất nguồn gốc</p>
            </div>
          </div>

          <div className="animate-section">
            <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">{batch.product_name}</h1>
            <div className="flex flex-wrap items-center gap-3 mt-3">
              <span className="px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide"
                style={{ background: 'rgba(255,255,255,0.15)', color: 'white', backdropFilter: 'blur(4px)' }}>
                {batch.batch_code}
              </span>
              <span className="px-3 py-1 rounded-full text-xs font-semibold" style={{ background: st.bg, color: st.color }}>
                {st.label}
              </span>
              {integrity?.verified && (
                <span className="px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5"
                  style={{ background: 'rgba(16,185,129,0.2)', color: '#D9B96E' }}>
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Đã xác minh toàn vẹn
                </span>
              )}
            </div>
          </div>

          {/* Company */}
          <div className="mt-5 animate-section">
            <p className="text-white/70 text-sm">
              <span className="text-white/40">Sản xuất bởi:</span>{' '}
              <strong className="text-white">{batch.company_name}</strong>
            </p>
            {batch.process_name && (
              <p className="text-white/70 text-sm mt-1">
                <span className="text-white/40">Quy trình:</span>{' '}
                <strong className="text-white">{batch.process_name}</strong>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="max-w-2xl mx-auto px-5 -mt-4 pb-12 space-y-4">

        {/* Progress + Score card */}
        <div className="rounded-2xl p-5 animate-section"
          style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', boxShadow: '0 4px 20px rgba(0,0,0,0.04)' }}>
          <div className="grid grid-cols-2 gap-4">
            {/* Progress */}
            <div>
              <p className="text-xs font-medium mb-2" style={{ color: '#6B7280' }}>Tiến độ sản xuất</p>
              <div className="flex items-end gap-2 mb-2">
                <span className="text-2xl font-bold" style={{ color: '#0A1F44' }}>{progress.percent}%</span>
                <span className="text-xs pb-1" style={{ color: '#94A3B8' }}>{progress.completed}/{progress.total} bước</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: '#E2E8F0' }}>
                <div className="h-full rounded-full animate-progress"
                  style={{ width: `${progress.percent}%`, background: progress.percent === 100 ? '#0A1F44' : '#F59E0B' }} />
              </div>
            </div>
            {/* Compliance score */}
            <div className="text-right">
              <p className="text-xs font-medium mb-2" style={{ color: '#6B7280' }}>Điểm tuân thủ</p>
              {batch.compliance_score !== null ? (
                <div className="inline-flex items-center gap-2">
                  <div className="relative w-14 h-14">
                    <svg viewBox="0 0 40 40" className="w-full h-full -rotate-90">
                      <circle cx="20" cy="20" r="16" fill="none" stroke="#E2E8F0" strokeWidth="3" />
                      <circle cx="20" cy="20" r="16" fill="none"
                        className="animate-score-fill"
                        stroke={batch.compliance_score >= 75 ? '#0A1F44' : batch.compliance_score >= 50 ? '#F59E0B' : '#EF4444'}
                        strokeWidth="3" strokeLinecap="round"
                        strokeDasharray={`${batch.compliance_score * 1.005} 100.5`} />
                    </svg>
                    <span className="absolute inset-0 grid place-items-center text-sm font-bold"
                      style={{ color: batch.compliance_score >= 75 ? '#0A1F44' : batch.compliance_score >= 50 ? '#F59E0B' : '#EF4444' }}>
                      {batch.compliance_score}
                    </span>
                  </div>
                </div>
              ) : (
                <span className="text-sm" style={{ color: '#94A3B8' }}>N/A</span>
              )}
            </div>
          </div>

          {/* Timeline */}
          <div className="grid grid-cols-2 gap-3 mt-4 pt-4" style={{ borderTop: '1px solid #F0F0F0' }}>
            <div>
              <p className="text-xs" style={{ color: '#94A3B8' }}>Bắt đầu</p>
              <p className="text-xs font-medium" style={{ color: '#0A1F44' }}>{formatDate(batch.started_at) || 'Chưa bắt đầu'}</p>
            </div>
            <div>
              <p className="text-xs" style={{ color: '#94A3B8' }}>Hoàn thành</p>
              <p className="text-xs font-medium" style={{ color: '#0A1F44' }}>{formatDate(batch.completed_at) || 'Chưa hoàn thành'}</p>
            </div>
          </div>
        </div>

        {/* Integrity seal card */}
        {integrity && (
          <div className={`rounded-2xl p-5 animate-section ${integrity.verified ? '' : ''}`}
            style={{
              background: integrity.verified ? 'linear-gradient(135deg, #DCE3F0, #D9B96E)' : '#FEF2F2',
              border: `1px solid ${integrity.verified ? 'rgba(10,31,68,0.2)' : 'rgba(239,68,68,0.2)'}`,
            }}>
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
                style={{ background: integrity.verified ? 'rgba(10,31,68,0.15)' : 'rgba(239,68,68,0.15)' }}>
                {integrity.verified ? (
                  <svg className="w-5 h-5" style={{ color: '#0A1F44' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" style={{ color: '#EF4444' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold" style={{ color: integrity.verified ? '#0A1F44' : '#DC2626' }}>
                  {integrity.verified ? 'Dữ liệu toàn vẹn — Đã xác minh' : 'Cảnh báo: Dữ liệu có thể bị thay đổi'}
                </h3>
                <p className="text-xs mt-1" style={{ color: integrity.verified ? '#047857' : '#B91C1C' }}>
                  {integrity.verified
                    ? `Sealed bởi ${integrity.sealed_by} · ${formatDate(integrity.sealed_at) || ''}`
                    : 'Hash không khớp — dữ liệu có thể đã bị chỉnh sửa sau khi seal'}
                </p>
                <p className="text-xs mt-2 font-mono truncate" style={{ color: '#94A3B8' }} title={integrity.hash}>
                  SHA-256: {integrity.hash}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Steps */}
        {steps.length > 0 && (
          <div className="rounded-2xl overflow-hidden animate-section"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <div className="px-5 py-4" style={{ borderBottom: '1px solid #E2E8F0' }}>
              <h2 className="text-sm font-bold" style={{ color: '#0A1F44' }}>
                Các bước sản xuất
                <span className="ml-2 text-xs font-normal" style={{ color: '#94A3B8' }}>
                  {progress.completed}/{progress.total}
                </span>
              </h2>
            </div>
            <div className="divide-y" style={{ borderColor: '#F0F0F0' }}>
              {steps.map((step, i) => {
                const done = step.status === 'completed';
                return (
                  <div key={i} className={`px-5 py-3.5 flex items-start gap-3 animate-list-item stagger-${Math.min(i + 1, 12)}`}>
                    {/* Step indicator */}
                    <div className={`w-7 h-7 rounded-full grid place-items-center flex-shrink-0 mt-0.5 ${done ? '' : ''}`}
                      style={{
                        background: done ? '#0A1F44' : '#E2E8F0',
                        transition: 'background 0.3s ease',
                      }}>
                      {done ? (
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <span className="text-xs font-bold" style={{ color: '#94A3B8' }}>{i + 1}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium" style={{ color: done ? '#0A1F44' : '#94A3B8' }}>{step.name}</p>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5">
                        {step.performed_by && (
                          <span className="text-xs" style={{ color: '#6B7280' }}>{step.performed_by}</span>
                        )}
                        {step.completed_at && (
                          <span className="text-xs" style={{ color: '#94A3B8' }}>{formatDate(step.completed_at)}</span>
                        )}
                        {step.approved_by && (
                          <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: '#DCE3F0', color: '#102A5C' }}>
                            Xác nhận: {step.approved_by}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Materials */}
        {materials.length > 0 && (
          <div className="rounded-2xl overflow-hidden animate-section"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <div className="px-5 py-4" style={{ borderBottom: '1px solid #E2E8F0' }}>
              <h2 className="text-sm font-bold" style={{ color: '#0A1F44' }}>Nguyên liệu sử dụng</h2>
            </div>
            <div className="divide-y" style={{ borderColor: '#F0F0F0' }}>
              {materials.map((mat, i) => {
                const risk = RISK_MAP[mat.halal_risk] || RISK_MAP.unknown;
                return (
                  <div key={i} className={`px-5 py-3.5 animate-list-item stagger-${Math.min(i + 1, 12)}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium" style={{ color: '#0A1F44' }}>{mat.name}</p>
                        <div className="flex items-center gap-2 mt-1 flex-wrap">
                          {mat.sku && <span className="text-xs" style={{ color: '#94A3B8' }}>SKU: {mat.sku}</span>}
                          {mat.supplier_name && (
                            <span className="text-xs flex items-center gap-1" style={{ color: '#6B7280' }}>
                              {mat.supplier_verified && (
                                <svg className="w-3 h-3" style={{ color: '#102A5C' }} fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                </svg>
                              )}
                              {mat.supplier_name}
                            </span>
                          )}
                          {mat.quantity && (
                            <span className="text-xs" style={{ color: '#94A3B8' }}>{mat.quantity} {mat.unit || ''}</span>
                          )}
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0"
                        style={{ background: risk.bg, color: risk.color }}>
                        {risk.label}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Certificates */}
        {certificates.length > 0 && (
          <div className="rounded-2xl overflow-hidden animate-section"
            style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
            <div className="px-5 py-4" style={{ borderBottom: '1px solid #E2E8F0' }}>
              <h2 className="text-sm font-bold" style={{ color: '#0A1F44' }}>Chứng chỉ nhà cung cấp</h2>
            </div>
            <div className="divide-y" style={{ borderColor: '#F0F0F0' }}>
              {certificates.map((cert, i) => {
                const expired = cert.expiry_date ? new Date(cert.expiry_date) < new Date() : false;
                return (
                  <div key={i} className={`px-5 py-3.5 animate-list-item stagger-${Math.min(i + 1, 12)}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium" style={{ color: '#0A1F44' }}>
                          {cert.cert_type || 'Chứng chỉ'}
                          {cert.cert_number && <span className="text-xs ml-1.5" style={{ color: '#94A3B8' }}>#{cert.cert_number}</span>}
                        </p>
                        <div className="flex items-center gap-2 mt-1 text-xs" style={{ color: '#6B7280' }}>
                          <span>{cert.supplier_name}</span>
                          {cert.issuing_body && <><span>·</span><span>{cert.issuing_body}</span></>}
                        </div>
                      </div>
                      {cert.expiry_date && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0"
                          style={{
                            background: expired ? '#FEF2F2' : '#DCE3F0',
                            color: expired ? '#DC2626' : '#102A5C',
                          }}>
                          {expired ? 'Hết hạn' : `HSD: ${new Date(cert.expiry_date).toLocaleDateString('vi-VN')}`}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="pt-6 pb-4 text-center animate-section">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-lg grid place-items-center" style={{ background: '#0A1F44' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold" style={{ color: '#0A1F44' }}>AMINRA</span>
          </div>
          <p className="text-xs" style={{ color: '#94A3B8' }}>
            Halal Supply Chain Integrity Platform
          </p>
          <p className="text-xs mt-1" style={{ color: '#CBD5E1' }}>
            Thông tin được cung cấp bởi doanh nghiệp sản xuất và xác minh bởi hệ thống AMINRA
          </p>
        </div>
      </div>
    </div>
  );
}
