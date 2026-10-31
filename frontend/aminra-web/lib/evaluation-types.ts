export interface EvalIssue {
  section: string;
  severity: "critical" | "major" | "minor";
  issue: string;
  recommendation: string;
  reference: string;
}

export interface GapAnalysis {
  critical_gaps: string[];
  major_gaps: string[];
  minor_gaps: string[];
}

export interface RiskFlag {
  text_snippet: string;
  risk_type: string;
  severity: "critical" | "high" | "medium" | "low";
  explanation: string;
}

export interface Citation {
  standard: string;
  clause: string;
  text: string;
  relevance: string;
}

export interface EvaluationReport {
  document_id?: string | null;
  document_save_status?: "saved" | "failed" | "not_applicable";
  document_save_error?: string | null;
  filename: string;
  doc_type: string;
  doc_type_label: string;
  word_count: number;
  standards_found: number;
  compliance_score: number;
  overall_status: "compliant" | "needs_review" | "non_compliant";
  summary: string;
  issues: EvalIssue[];
  strengths: string[];
  recommendations: string[];
  standards_checked: string[];
  gap_analysis: GapAnalysis | null;
  risk_flags: RiskFlag[];
  citations: Citation[];
  extracted_text?: string;
}

export interface FileVersionEntry {
  version: number;
  score: number;
  status: string;
  doc_type_label: string;
  timestamp: string;
  issues_count: number;
  strengths_count: number;
  summary: string;
}

export interface AuditorReview {
  reviewer: string;
  notes: string;
  confirmed_issues: string[];
  false_positives: string[];
  additional_findings: string[];
  issue_comments: Record<string, string>;
  final_score: number | null;
  status: "pending" | "approved" | "rejected";
  reviewed_at?: string;
  filename?: string;
}

