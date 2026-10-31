import { expect, it } from 'vitest';
import { generateReportHTML } from './evaluation-report-html';
import type { EvaluationReport, AuditorReview } from './evaluation-types';
it('renders filename, AI output and reviewer text as inert text in the exported document',()=>{
 const attack='</title><img src=x onerror="window.opener.localStorage.clear()"><script>bad()</script>';
 const report:EvaluationReport={filename:attack,doc_type:'general',doc_type_label:attack,word_count:1,standards_found:0,compliance_score:50,overall_status:'needs_review',summary:attack,issues:[{section:attack,severity:'major',issue:attack,recommendation:attack,reference:attack}],strengths:[attack],recommendations:[],standards_checked:[],gap_analysis:{critical_gaps:[attack],major_gaps:[attack],minor_gaps:[attack]},risk_flags:[{text_snippet:attack,risk_type:attack,severity:'high',explanation:attack}],citations:[{standard:attack,clause:attack,text:attack,relevance:attack}]};
 const review:AuditorReview={reviewer:attack,notes:attack,status:'pending',confirmed_issues:[],false_positives:[],additional_findings:[],issue_comments:{},final_score:null};
 const html=generateReportHTML(report,review);const parsed=new DOMParser().parseFromString(html,'text/html');
 expect(parsed.querySelectorAll('script,img,[onerror]')).toHaveLength(0);expect(parsed.body.textContent).toContain(attack);
 expect(report.filename).toBe(attack);
});
