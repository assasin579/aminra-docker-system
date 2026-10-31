import type { EvaluationReport, AuditorReview } from "./evaluation-types";

function escapeValues<T>(value: T): T {
  if (typeof value === "string") return value.replace(/[&<>"']/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[character]!)) as T;
  if (Array.isArray(value)) return value.map(item => escapeValues(item)) as T;
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, escapeValues(item)])) as T;
  return value;
}

export function generateReportHTML(
  report: EvaluationReport,
  review: AuditorReview | null,
): string {
  // Filenames, AI excerpts and review text are untrusted document content.
  report = escapeValues(report);
  review = escapeValues(review);
  const st =
    report.overall_status === "compliant"
      ? "#0A1F44"
      : report.overall_status === "needs_review"
        ? "#f59e0b"
        : "#ef4444";
  const stLabel =
    report.overall_status === "compliant"
      ? "Tuân thủ"
      : report.overall_status === "needs_review"
        ? "Cần xem xét"
        : "Không tuân thủ";
  return `<!DOCTYPE html><html lang="vi"><head>
<meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>Báo cáo Halal — ${report.filename}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; color: #111; line-height: 1.6; }
  h1 { color: #166534; border-bottom: 2px solid #166534; padding-bottom: 8px; }
  h2 { color: #0A1F44; margin-top: 28px; font-size: 16px; }
  .score { font-size: 48px; font-weight: bold; color: ${st}; }
  .status { display: inline-block; padding: 4px 12px; border-radius: 20px; background: ${st}22; color: ${st}; font-weight: bold; margin-left: 12px; font-size: 14px; }
  .issue { border-left: 3px solid #dc2626; padding: 10px 16px; margin: 8px 0; background: #fef2f2; border-radius: 4px; }
  .citation { border-left: 3px solid #0A1F44; padding: 10px 16px; margin: 8px 0; background: #eff6ff; border-radius: 4px; }
  .risk { border-left: 3px solid #d97706; padding: 10px 16px; margin: 8px 0; background: #fffbeb; border-radius: 4px; }
  blockquote { font-style: italic; color: #374151; margin: 0; }
  .meta { color: #6b7280; font-size: 13px; }
  @media print { body { margin: 20px; } }
</style></head><body>
<h1>Báo cáo Đánh giá Halal Compliance</h1>
<p class="meta">Tài liệu: <strong>${report.filename}</strong> · ${report.doc_type_label} · ${report.word_count.toLocaleString()} từ</p>
<p class="meta">Ngày: ${new Date().toLocaleDateString("vi-VN", { year: "numeric", month: "long", day: "numeric" })}</p>
<p><span class="score">${report.compliance_score}</span><span>/100</span><span class="status">${stLabel}</span></p>
<p>${report.summary}</p>
${report.strengths.length ? `<h2>Điểm mạnh</h2><ul>${report.strengths.map((s) => `<li>${s}</li>`).join("")}</ul>` : ""}
${report.issues.length ? `<h2>Vấn đề phát hiện (${report.issues.length})</h2>${report.issues.map((i) => `<div class="issue"><strong>[${i.severity.toUpperCase()}] ${i.section}</strong><br>${i.issue}<br><em>→ ${i.recommendation}</em><br><small>§ ${i.reference}</small></div>`).join("")}` : ""}
${
  report.gap_analysis
    ? `<h2>Gap Analysis</h2>
${report.gap_analysis.critical_gaps.length ? `<h3 style="color:#dc2626">Nghiêm trọng</h3><ul>${report.gap_analysis.critical_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}
${report.gap_analysis.major_gaps.length ? `<h3 style="color:#d97706">Lớn</h3><ul>${report.gap_analysis.major_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}
${report.gap_analysis.minor_gaps.length ? `<h3 style="color:#0A1F44">Nhỏ</h3><ul>${report.gap_analysis.minor_gaps.map((g) => `<li>${g}</li>`).join("")}</ul>` : ""}`
    : ""
}
${report.risk_flags.length ? `<h2>Rủi ro Inline (${report.risk_flags.length})</h2>${report.risk_flags.map((r) => `<div class="risk"><span style="color:#d97706;font-weight:bold">[${r.severity.toUpperCase()}] ${r.risk_type}</span><br><blockquote>"${r.text_snippet}"</blockquote><br>${r.explanation}</div>`).join("")}` : ""}
${report.citations.length ? `<h2>Trích dẫn Tiêu chuẩn (${report.citations.length})</h2>${report.citations.map((c) => `<div class="citation"><strong>${c.standard} — Điều ${c.clause}</strong><br><blockquote>"${c.text}"</blockquote><br><small>${c.relevance}</small></div>`).join("")}` : ""}
${review ? `<h2>Review của Kiểm toán viên</h2><p>Reviewer: <strong>${review.reviewer}</strong> · Trạng thái: <strong>${review.status}</strong></p><p>${review.notes}</p>` : ""}
<hr style="margin-top:40px"><p class="meta" style="text-align:center">Được tạo bởi AMINRA — Halal Certification AI · ${new Date().toISOString()}</p>
</body></html>`;
}
