"""Exact J1/J2 acceptance denominator, backed by required cases, DB tests and runtime proof."""
import csv,json,html,xml.etree.ElementTree as ET
from pathlib import Path

DB='test_'
MANIFEST=[
 ('J1-A01','Readiness legacy/UNKNOWN/optional-only/missing required',['J1-READINESS-unpublished','J1-READINESS-legacy','J1-READINESS-optional','J1-READINESS-missing'],['legacy_dossier_remains_unknown_under_current_published_profile']),
 ('J1-A02','Exact-version attach/reuse/tenant isolation',['J1-REUSE','J1-DELEGATED-UPLOAD','JOURNEY-01'],['j1_a02_reuses_exact_document_version_and_denies_wrong_tenant']),
 ('J1-A03','Pinned slots, exact dossier review context; AI alone insufficient',['PINNED-01','J1-AI-NOT-APPROVAL'],['reused_document_does_not_borrow_another_dossier_review_context','bound_resubmit_without_document_ids_revalidates_current_packet']),
 ('J1-A04','Owner-selected CB and dossier handoff',['JOURNEY-01','NAV-01'],['submit_routes_owner_selected_cb_to_canonical_org_tenant']),
 ('J1-A05','Initial submission retry/concurrency/conflict/atomicity',['JOURNEY-01'],['submit_retry_same_key_returns_same_submission_receipt','submit_route_concurrent_same_key_commits_one_submission','submit_failure_rolls_back_receipt_and_submission','submit_replay_rechecks_current_provider_eligibility']),
 ('J1-A06','Selected-CB packet/preview and wrong-CB denial',['J1-PACKET-PREVIEW'],['historical_round_document_file_serves_exact_bytes_and_scopes_provider']),
 ('J1-A07','Download immutable historical bytes',['JOURNEY-01','RECOVERY-01'],['historical_round_document_file_serves_exact_bytes_and_scopes_provider']),
 ('J1-A08','Dashboard loading/UNKNOWN/account switch/stale result',['J1-DASHBOARD-RACE','J1-READINESS-unpublished'],['g1_dashboard_uses_canonical_tenant_predicate_under_app_role']),
 ('J2-A01','Correction authority and exact assignment',['JOURNEY-01','J2-AUTHORITY'],['request_revision_replay_rechecks_current_assignment']),
 ('J2-A02','Business/member/CB/reviewer history scope and snapshots',['J2-AUTHORITY','J2-MEMBER-HISTORY'],['revision_history_scope_snapshot_and_uuid_values']),
 ('J2-A03','Pinned replacement/resubmit and omitted IDs',['JOURNEY-01'],['bound_browser_replacement_attaches_before_pointer_change','bound_resubmit_without_document_ids_revalidates_current_packet','resubmit_rejects_document_type_outside_pinned_requirements']),
 ('J2-A04','Two rounds, retained response and old/new diff',['JOURNEY-01'],['j2_round_resubmit_diff_and_old_snapshot_immutability','replacement_preserves_open_revision_until_explicit_resubmit_retry']),
 ('J2-A05','Three command receipts, concurrency/conflict/rollback',['JOURNEY-01','RECOVERY-01'],['request_revision_retry_same_key_replays_original_request','request_revision_route_serializes_concurrent_same_key','request_revision_route_concurrent_different_keys_has_one_winner','request_revision_database_failure_rolls_back_submission','resubmit_route_concurrent_different_keys_has_one_winner','resubmit_same_key_different_payload_conflicts_without_mutation','resubmit_receipt_and_mutation_rollback_together_on_side_effect_failure']),
 ('J2-A06','Historical-file scope after reassignment/revocation',['J2-FILE-REASSIGN'],['historical_round_document_file_serves_exact_bytes_and_scopes_provider']),
 ('X-A01','Actual delivery lifecycle and byte identity across restart',['RECOVERY-01'],['historical_round_document_file_serves_exact_bytes_and_scopes_provider']),
 ('X-A02','Legacy compatibility, guarded downgrade, forward recovery',['J1-READINESS-legacy','RECOVERY-01'],['legacy_dossier_remains_unknown_under_current_published_profile']),
 ('X-A03','Rendered two-round J1/J2 on exact build',['JOURNEY-01','RECOVERY-01'],[]),
 ('X-A04','Publication authority, immutable snapshots and lineage',['X-PUBLICATION-GUARDS'],['requirements_publication_authority_snapshot_immutability_and_rollback']),
]

def generate(report,output):
 output=Path(output);db=[]
 if (output/'database.xml').exists():
  for node in ET.parse(output/'database.xml').iter('testcase'):
   db.append({'name':node.attrib['name'],'status':'FAIL' if node.find('failure') is not None or node.find('error') is not None else 'BLOCKED' if node.find('skipped') is not None else 'PASS'})
 runtime=json.loads((output/'runtime-checks.json').read_text()) if (output/'runtime-checks.json').exists() else {}
 rows=[]
 for ident,scope,required,tests in MANIFEST:
  evidence=[]
  for key in required:
   found=[c for c in report['cases'] if c['name'].removeprefix('[API] ').startswith(key+' ') or c['name'].removeprefix('[API] ')==key]
   evidence.append({'requirement':'browser/API case '+key,'status':('FAIL' if any(c['status'] in ('FAIL','FLAKY') for c in found) else 'PASS' if found and all(c['status']=='PASS' for c in found) else 'BLOCKED'),'references':[c['name'] for c in found]})
  for key in tests:
   found=[c for c in db if c['name']==DB+key or c['name'].startswith(DB+key+'[')]
   if key=='reused_document_does_not_borrow_another_dossier_review_context' and {c['name'] for c in found}!={DB+key+'[True]',DB+key+'[False]'}:found=[]
   evidence.append({'requirement':'real DB '+key,'status':'FAIL' if any(c['status']=='FAIL' for c in found) else 'PASS' if found and all(c['status']=='PASS' for c in found) else 'BLOCKED','references':[c['name'] for c in found]})
  if ident=='X-A02':
   for key in ['guard_055','guard_057','schema_head_preserved','app_role_least_privilege']:evidence.append({'requirement':key,'status':'PASS' if runtime.get(key) is True else 'FAIL' if key in runtime else 'BLOCKED'})
  provenance=report['run'].get('images') and report['run'].get('schema_head') and report['run'].get('suite_manifest')
  if runtime.get('images_match_source_revision') is not True:evidence.append({'requirement':'image source revision matches tested source','status':'FAIL' if 'images_match_source_revision' in runtime else 'BLOCKED'})
  if report['run'].get('test_source_unchanged') is False:evidence.append({'requirement':'test source frozen for this run','status':'BLOCKED'})
  if not provenance:evidence.append({'requirement':'exact build/schema/test source','status':'BLOCKED'})
  status='FAIL' if any(e['status']=='FAIL' for e in evidence) else 'PASS' if all(e['status']=='PASS' for e in evidence) and report['run'].get('cleanup') and not report['run'].get('error') else 'BLOCKED'
  rows.append({'id':ident,'scope':scope,'status':status,'required_evidence':evidence})
 result={'scope':'18 technical J1/J2 criteria; not full UAT/pilot approval','run_id':report['run']['run_id'],'build':report['run'].get('images'),'schema':report['run'].get('schema_head'),'criteria':rows,'passed':sum(x['status']=='PASS' for x in rows),'total':18,'gate':'FAIL' if any(x['status']=='FAIL' for x in rows) else 'PASS' if all(x['status']=='PASS' for x in rows) else 'BLOCKED','database_cases':db}
 if any(c['status'] in ('FAIL','FLAKY') for c in report['cases']) or any(c['status']=='FAIL' for c in db):result['gate']='FAIL'
 if report['run'].get('error') or any(c['status']=='BLOCKED' for c in db):result['gate']='BLOCKED' if result['gate']!='FAIL' else 'FAIL'
 (output/'j1j2-acceptance.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
 with (output/'j1j2-acceptance.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['id','scope','status','required_count']);w.writeheader();w.writerows({**{k:r[k] for k in ('id','scope','status')},'required_count':len(r['required_evidence'])} for r in rows)
 body=''.join('<tr><td>'+r['id']+'</td><td>'+html.escape(r['scope'])+'</td><td>'+r['status']+'</td><td>'+''.join('<p>'+e['status']+' '+html.escape(e['requirement'])+'</p>' for e in r['required_evidence'])+'</td></tr>' for r in rows)
 (output/'j1j2-acceptance.html').write_text('<!doctype html><meta charset="utf-8"><title>J1/J2 acceptance</title><style>body{font:16px system-ui;margin:32px}td,th{border:1px solid #ccc;padding:10px;vertical-align:top}table{border-collapse:collapse}p{margin:3px}</style><h1>J1/J2: '+str(result['passed'])+'/18 '+result['gate']+'</h1><p>Technical scoped acceptance; no independent business/pilot sign-off.</p><a href="report.html">Full baseline report</a><table><tr><th>ID</th><th>Scope</th><th>Status</th><th>Required evidence</th></tr>'+body+'</table>')
 return result
