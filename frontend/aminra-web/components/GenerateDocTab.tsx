'use client';

import { useState, useRef, useMemo, useCallback } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface EvalReport {
  filename: string;
  doc_type: string;
  doc_type_label: string;
  issues: Array<{ section: string; severity: string; issue: string; recommendation: string }>;
  recommendations: string[];
  gap_analysis: { critical_gaps: string[]; major_gaps: string[]; minor_gaps: string[] } | null;
  compliance_score: number;
  extracted_text?: string;
}

export type GeneratePhase = 'idle' | 'generating' | 'done';

export interface GenerateState {
  phase: GeneratePhase;
  genText: string;
  editContent: string;
  genError: string;
}

export const INITIAL_GENERATE_STATE: GenerateState = {
  phase: 'idle', genText: '', editContent: '', genError: '',
};

interface Props {
  report: EvalReport;
  extractedText: string;
  token: string | null;
  persisted: GenerateState;
  onStateChange: (s: GenerateState) => void;
}

// ─── Diff: exact paragraph matching ──────────────────────────────────────────
//
// Simple and reliable:
//   - Normalize each paragraph (trim, collapse whitespace)
//   - If new paragraph exists EXACTLY in original → "same" (gray)
//   - If new paragraph does NOT exist in original → "new" (green)
//   - Original paragraphs not found in new → "removed" (red, shown at top)

type DiffSegment =
  | { type: 'same'; text: string }
  | { type: 'del';  text: string }
  | { type: 'add';  text: string };

function normalize(text: string): string {
  return text.trim().replace(/\s+/g, ' ').toLowerCase();
}

function computeUnifiedDiff(oldText: string, newText: string): DiffSegment[] {
  if (!oldText.trim()) return [{ type: 'add', text: newText }];
  if (!newText.trim()) return [{ type: 'del', text: oldText }];

  // Build a set of normalized original paragraphs
  const oldParas = oldText.split('\n');
  const newParas = newText.split('\n');

  const oldNormSet = new Set(oldParas.map(normalize).filter(Boolean));
  const newNormSet = new Set(newParas.map(normalize).filter(Boolean));

  const result: DiffSegment[] = [];

  // Show removed paragraphs first (exist in old but not in new)
  const removedParas = oldParas.filter(p => {
    const n = normalize(p);
    return n && !newNormSet.has(n);
  });
  if (removedParas.length > 0) {
    result.push({ type: 'del', text: removedParas.join('\n') + '\n' });
  }

  // Show new document with highlights
  for (const p of newParas) {
    const n = normalize(p);
    if (!n) {
      // Empty line — keep as-is
      result.push({ type: 'same', text: '\n' });
    } else if (oldNormSet.has(n)) {
      // Exact match — unchanged
      result.push({ type: 'same', text: p + '\n' });
    } else {
      // New or modified — highlight green
      result.push({ type: 'add', text: p + '\n' });
    }
  }

  return result;
}

// ─── Diff stats ──────────────────────────────────────────────────────────────

function diffStats(segments: DiffSegment[]) {
  let addedLines = 0, deletedLines = 0, sameLines = 0;
  for (const s of segments) {
    const lines = s.text.split('\n').filter(l => l.trim()).length;
    if (s.type === 'same') sameLines += lines;
    else if (s.type === 'add') addedLines += lines;
    else if (s.type === 'del') deletedLines += lines;
  }
  return { addedLines, deletedLines, sameLines };
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function GenerateDocTab({ report, extractedText, token, persisted, onStateChange }: Props) {
  const { phase, genText, editContent, genError } = persisted;

  const update = useCallback((patch: Partial<GenerateState>) => {
    onStateChange({ ...persisted, ...patch });
  }, [persisted, onStateChange]);

  const [view, setView]             = useState<'diff' | 'edit'>('diff');
  const [onlyChanges, setOnlyChanges] = useState(false);
  const [exporting, setExporting]   = useState<'docx' | 'pdf' | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const oldText = extractedText || report.extracted_text || '';

  const diffSegments = useMemo(
    () => computeUnifiedDiff(oldText, editContent || genText),
    [oldText, editContent, genText]
  );

  const stats = useMemo(() => diffStats(diffSegments), [diffSegments]);

  const handleGenerate = useCallback(async () => {
    update({ phase: 'generating', genError: '', genText: '' });
    abortRef.current = new AbortController();

    try {
      const res = await fetch('/api/generate-document', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          doc_type:       report.doc_type,
          doc_type_label: report.doc_type_label,
          extracted_text: extractedText || '',
          issues:         report.issues || [],
          recommendations: report.recommendations || [],
          gap_analysis:   report.gap_analysis,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.error || `HTTP ${res.status}`);
      }

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = dec.decode(value, { stream: true });
        full += chunk;
        onStateChange({ phase: 'generating', genText: full, editContent: '', genError: '' });
      }
      onStateChange({ phase: 'done', genText: full, editContent: full, genError: '' });
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        update({ genError: e.message || 'Lỗi tạo tài liệu', phase: 'idle' });
      }
    }
  }, [report, extractedText, token, update, onStateChange]);

  const handleExportDocx = async () => {
    setExporting('docx');
    try {
      const res = await fetch('/api/generate-document/export-docx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: editContent,
          filename: report.filename,
          title: report.doc_type_label,
          doc_type: report.doc_type,
        }),
      });
      if (!res.ok) throw new Error('Export thất bại');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const cd = res.headers.get('Content-Disposition') || '';
      const fn = cd.match(/filename="([^"]+)"/)?.[1] || 'document_improved.docx';
      a.href = url; a.download = fn; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setExporting(null);
    }
  };

  const handleExportPdf = () => {
    setExporting('pdf');
    const w = window.open('', '_blank')!;
    w.document.write(`<!DOCTYPE html><html><head>
      <meta charset="utf-8"><title>${report.doc_type_label}</title>
      <style>
        body{font-family:Arial,sans-serif;font-size:13px;line-height:1.7;max-width:800px;margin:40px auto;padding:0 20px;color:#111}
        h1{font-size:20px;margin:24px 0 8px}h2{font-size:16px;margin:20px 0 6px}h3{font-size:14px;margin:16px 0 4px}
        p{margin:6px 0}li{margin:4px 0}
        @media print{@page{margin:2cm}}
      </style>
    </head><body>
      <pre style="white-space:pre-wrap;font-family:inherit">${editContent.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>
    </body></html>`);
    w.document.close();
    setTimeout(() => { w.print(); setExporting(null); }, 500);
  };

  // ── Idle state ──────────────────────────────────────────────────────────────
  if (phase === 'idle') {
    return (
      <div className="space-y-5">
        <div className="rounded-2xl p-6" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)' }}>
          <div className="grid grid-flow-col items-center gap-3 mb-3 justify-start">
            <div className="w-9 h-9 rounded-xl grid place-items-center flex-shrink-0"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}>
              <svg className="w-5 h-5" style={{ color: '#818cf8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8"
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-bold" style={{ color: '#0F5132' }}>Tạo tài liệu cải tiến bằng AI</h3>
              <p className="text-xs mt-0.5" style={{ color: '#6366f1' }}>Tự động khắc phục 100% các tiêu chí chưa đạt</p>
            </div>
          </div>
          <p className="text-xs leading-relaxed" style={{ color: '#6B7280' }}>
            AI sẽ phân tích tài liệu gốc <strong style={{ color: '#0F5132' }}>{report.filename}</strong>,
            đối chiếu với <strong style={{ color: '#0F5132' }}>{report.doc_type_label}</strong> template,
            sau đó tạo ra phiên bản mới đáp ứng đầy đủ tiêu chuẩn Halal JAKIM/HDC.
          </p>

          <div className="grid grid-cols-3 gap-3 mt-4">
            {[
              { label: 'Vấn đề cần sửa', value: report.issues.length, color: '#f87171' },
              { label: 'Điểm hiện tại', value: `${report.compliance_score}%`, color: '#fbbf24' },
              { label: 'Mục tiêu', value: '100%', color: '#0F5132' },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-3 text-center" style={{ background: '#F7F1E6', border: '1px solid #E2E8F0' }}>
                <div className="text-lg font-bold" style={{ color: s.color }}>{s.value}</div>
                <div className="text-xs mt-0.5" style={{ color: '#6B7280' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {genError && (
          <div className="grid items-center gap-2 px-4 py-3 rounded-xl text-sm"
            style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#f87171' }}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {genError}
          </div>
        )}

        <button onClick={handleGenerate}
          className="grid items-center gap-2 w-full py-3.5 rounded-2xl font-semibold text-base transition-all duration-200 hover:scale-[1.01] active:scale-[0.99]"
          style={{ gridTemplateColumns: 'auto 1fr', justifyItems: 'center', background: 'linear-gradient(135deg, #4f46e5, #6366f1)', color: 'white', boxShadow: '0 4px 20px rgba(99,102,241,0.35)' }}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Tạo tài liệu cải tiến
        </button>
      </div>
    );
  }

  // ── Generating state ─────────────────────────────────────────────────────────
  if (phase === 'generating') {
    const wordCount = genText.split(/\s+/).filter(Boolean).length;
    return (
      <div className="space-y-4">
        <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
          <div>
            <div className="grid grid-flow-col items-center gap-2 justify-start">
              <div className="w-2.5 h-2.5 rounded-full bg-indigo-400" style={{ animation: 'pulse 1.2s ease-in-out infinite' }} />
              <span className="text-sm font-semibold" style={{ color: '#0F5132' }}>AI đang soạn thảo tài liệu...</span>
            </div>
            <p className="text-xs mt-1" style={{ color: '#6B7280' }}>{wordCount} từ đã tạo</p>
          </div>
          <button onClick={() => { abortRef.current?.abort(); update({ phase: 'idle' }); }}
            className="text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={{ border: '1px solid #E2E8F0', color: '#6B7280' }}>
            Huỷ
          </button>
        </div>
        <div className="rounded-xl p-4 overflow-y-auto font-mono text-xs leading-relaxed"
          style={{ maxHeight: '60vh', background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#374151', whiteSpace: 'pre-wrap' }}>
          {genText}
          <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 align-middle"
            style={{ animation: 'blink 0.8s ease-in-out infinite' }} />
        </div>
        <style>{`@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}`}</style>
      </div>
    );
  }

  // ── Done state ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
        <div className="grid grid-flow-col gap-1 justify-start">
          {([
            { id: 'diff', label: 'So sánh', icon: '⇄' },
            { id: 'edit', label: 'Chỉnh sửa', icon: '✎' },
          ] as const).map(v => (
            <button key={v.id} onClick={() => setView(v.id)}
              className="px-3 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{
                background: view === v.id ? 'rgba(99,102,241,0.15)' : 'transparent',
                color: view === v.id ? '#818cf8' : '#6B7280',
                border: view === v.id ? '1px solid rgba(99,102,241,0.3)' : '1px solid #E2E8F0',
              }}>
              <span className="mr-1">{v.icon}</span>{v.label}
            </button>
          ))}
        </div>

        <div className="grid grid-flow-col gap-2">
          <button onClick={handleExportDocx} disabled={!!exporting}
            className="grid items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
            style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(15,81,50,0.08)', color: '#0F5132', border: '1px solid rgba(15,81,50,0.2)', opacity: exporting ? 0.5 : 1 }}>
            {exporting === 'docx'
              ? <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg>
              : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>}
            DOCX
          </button>
          <button onClick={handleExportPdf} disabled={!!exporting}
            className="grid items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all hover:scale-105"
            style={{ gridTemplateColumns: 'auto 1fr', background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)', opacity: exporting ? 0.5 : 1 }}>
            {exporting === 'pdf'
              ? <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/></svg>
              : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17H17.01M17 3H5a2 2 0 00-2 2v4a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2zM3 7h18M3 13h18"/></svg>}
            PDF
          </button>
          <button onClick={() => { onStateChange(INITIAL_GENERATE_STATE); }}
            className="px-3 py-1.5 rounded-lg text-xs transition-colors"
            style={{ border: '1px solid #E2E8F0', color: '#6B7280' }}>
            Tạo lại
          </button>
        </div>
      </div>

      {/* Diff view — unified inline (like Word Track Changes) */}
      {view === 'diff' && (
        <div className="space-y-3">
          {/* Legend + stats */}
          <div className="grid items-center gap-3" style={{ gridTemplateColumns: '1fr auto' }}>
            <div className="grid grid-flow-col items-center gap-3 justify-start text-xs">
              <span className="px-2.5 py-1 rounded" style={{ background: 'rgba(15,81,50,0.12)', color: '#0F5132' }}>
                Nội dung mới / sửa đổi
              </span>
              {stats.deletedLines > 0 && (
                <span className="px-2.5 py-1 rounded" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', textDecoration: 'line-through' }}>
                  Đã xoá
                </span>
              )}
              <span style={{ color: '#6B7280' }}>
                {stats.addedLines} dòng mới · {stats.sameLines} dòng giữ nguyên
                {stats.deletedLines > 0 && ` · ${stats.deletedLines} dòng xoá`}
              </span>
            </div>
            <label className="grid grid-flow-col items-center gap-1.5 text-xs cursor-pointer" style={{ color: '#6B7280' }}>
              <input type="checkbox" checked={onlyChanges} onChange={e => setOnlyChanges(e.target.checked)}
                className="rounded" />
              Chỉ hiện thay đổi
            </label>
          </div>

          {!oldText && (
            <div className="rounded-lg px-4 py-3 text-xs" style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)', color: '#f59e0b' }}>
              Không có nội dung tài liệu gốc để so sánh.
            </div>
          )}

          {/* Diff content */}
          <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #E2E8F0' }}>
            <div className="px-5 py-3 text-xs"
              style={{ background: '#F7F1E6', borderBottom: '1px solid #E2E8F0', color: '#6B7280' }}>
              <strong style={{ color: '#0F5132' }}>{report.filename}</strong> → <strong style={{ color: '#0F5132' }}>{report.doc_type_label}</strong> (cải tiến)
            </div>

            <div className="overflow-y-auto text-sm leading-[1.8]"
              style={{ maxHeight: 'calc(100vh - 340px)', background: '#FFFFFF' }}>
              {diffSegments.map((seg, i) => {
                // ── Unchanged ──
                if (seg.type === 'same') {
                  if (onlyChanges && seg.text.trim()) return null;
                  return (
                    <div key={i} className="px-5 py-0.5" style={{ whiteSpace: 'pre-wrap', color: '#6B7280' }}>
                      {seg.text}
                    </div>
                  );
                }

                // ── Removed from original ──
                if (seg.type === 'del') {
                  return (
                    <div key={i} className="px-5 py-2 my-1 rounded-lg mx-3"
                      style={{ background: 'rgba(239,68,68,0.06)', borderLeft: '3px solid #ef4444' }}>
                      <div className="text-xs font-medium mb-1" style={{ color: '#f87171' }}>Đã xoá khỏi tài liệu gốc:</div>
                      <div style={{
                        color: '#ef4444', textDecoration: 'line-through',
                        textDecorationColor: 'rgba(239,68,68,0.4)', whiteSpace: 'pre-wrap', opacity: 0.7,
                      }}>
                        {seg.text}
                      </div>
                    </div>
                  );
                }

                // ── New / modified content ──
                return (
                  <div key={i} className="px-5 py-0.5"
                    style={{ background: 'rgba(15,81,50,0.06)', borderLeft: '3px solid #0F5132', whiteSpace: 'pre-wrap', color: '#0F5132' }}>
                    {seg.text}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Edit view */}
      {view === 'edit' && (
        <div className="space-y-3">
          <p className="text-xs" style={{ color: '#6B7280' }}>
            Chỉnh sửa trực tiếp tài liệu bên dưới. Chuyển sang tab "So sánh" để xem thay đổi.
          </p>
          <textarea
            value={editContent}
            onChange={e => update({ editContent: e.target.value })}
            className="w-full rounded-xl p-4 text-sm leading-relaxed outline-none resize-none font-mono"
            style={{
              background: '#FFFFFF', border: '1px solid #E2E8F0', color: '#0F5132',
              minHeight: '60vh',
            }}
            spellCheck={false}
          />
          <p className="text-xs" style={{ color: '#94A3B8' }}>
            {editContent.split(/\s+/).filter(Boolean).length} từ · {editContent.split('\n').length} dòng
          </p>
        </div>
      )}
    </div>
  );
}
