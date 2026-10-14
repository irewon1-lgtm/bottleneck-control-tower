"""Actual ledger requery/restart/backup/restore and preserved-source proof; no network."""
import json,pathlib,sqlite3,gzip,hashlib,subprocess,os,collections
from datetime import datetime
from bct.v4.store import Ledger,sha,now
R=pathlib.Path('docs/v4/cross-industry');V=pathlib.Path('var/v4/cross-industry')


def tables(path):
 c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);out={}
 assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 for table in ['metadata','blobs','documents','captures','readings','runs','firsts','events']:
  h=hashlib.sha256();rows=c.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()
  for row in rows:
   for x in row:
    b=x if isinstance(x,bytes)else json.dumps(x,ensure_ascii=False).encode();h.update(len(b).to_bytes(8,'big'));h.update(b)
  out[table]={'rows':len(rows),'sha256':h.hexdigest()}
 c.close();return out


def main():
 l=Ledger(V/'ledger');common=json.loads((R/'common-evidence.json').read_text())
 stored={json.loads(t)['event_id']:json.loads(t)for t, in l.db.execute("SELECT payload FROM events WHERE kind IN ('CROSS_COMMON_EVIDENCE','CROSS_COMMON_EVIDENCE_REVISION') ORDER BY seq")}
 assert len(stored)==len(common)and all(stored[x['event_id']]==x for x in common)
 assert all(len(x['target'])==5 for x in common)
 assert all(x['s_stage']=='UNKNOWN'for x in common if x['origin_kind']in ('CPU_DISCOVERY_UNVERIFIED','REUSED_EIA_REPORTED_CHANGE'))
 sources=[json.loads(t)for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_SOURCE_RESULT'")];articles=[json.loads(t)for t, in l.db.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_RESULT'")]
 for phase in ['SOURCE','ARTICLE']:
  urls=[json.loads(t)['url']for t, in l.db.execute("SELECT payload FROM events WHERE kind=?",('CROSS_'+phase+'_ATTEMPT',))];assert max(collections.Counter(urls).values())==1,'Unexpected real duplicate fetch'
 lookup={r['document_id']:json.loads(t)for t, in l.db.execute('SELECT payload FROM documents')for r in [json.loads(t)]};fresh=[lookup[x['document_id']]for x in articles if x['status']=='CAPTURED']
 for d in fresh:
  raw=l.db.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone()[0];assert sha(raw)==d['raw_sha256']and sha(d['body'].encode())==d['body_sha256']
 tag=sha([l.db.execute('SELECT MAX(seq) FROM events').fetchone()[0],l.db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],l.db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]])[:16]
 backup=V/'release-backups'/tag/'v4.sqlite3'
 if not backup.exists():l.backup(backup)
 l.close();assert tables(backup)==tables(V/'ledger/v4.sqlite3')
 packed=R/'research-snapshot.sqlite3.gz';packed.write_bytes(gzip.compress(backup.read_bytes(),mtime=0))
 restored=V/'release-restored'/tag/'v4.sqlite3';restored.parent.mkdir(parents=True,exist_ok=True);restored.write_bytes(gzip.decompress(packed.read_bytes()))
 reopened=Ledger(restored.parent);reopened.close();assert tables(restored)==tables(backup)
 # Entire previous API ledger equals its prior-task backup. No API events added.
 assert tables(pathlib.Path('var/v4/sequential/api-ledger/v4.sqlite3'))==tables(pathlib.Path('var/v4/path-comparison/shared-API-backup/v4.sqlite3'))
 oldpaths=subprocess.check_output(['git','ls-tree','-r','--name-only','0e9cdb1e899c836dfdac68ef76e61a45cc86b269','docs/v4'],text=True).splitlines();unchanged=0
 for p in oldpaths:
  if p in ('docs/v4/EXECUTION_PLAN.md','docs/v4/PROGRESS.json'):continue
  assert pathlib.Path(p).read_bytes()==subprocess.check_output(['git','show','0e9cdb1e899c836dfdac68ef76e61a45cc86b269:'+p]),p;unchanged+=1
 source_counters=collections.defaultdict(collections.Counter)
 for r in sources:source_counters[r['source']['industry_hint']]['source_parsed'if r['status']=='PARSED'else'source_failed']+=1
 for r in articles:
  c=source_counters[r['industry_hint']];c['article_attempted']+=1
  if r['status']=='CAPTURED':
   d=lookup[r['document_id']];c['native_captured']+=1;c[d['body_status']]+=1;c['nonempty_body']+=bool(d['body'])
  else:c['article_failed']+=1
 from v4_cross_industry_analyze import load_inputs
 all_docs,_=load_inputs();all_docs={k:v['doc']for k,v in all_docs.items()};all_docs.update(lookup)
 a=json.loads((R/'analysis.json').read_text());CPU=[json.loads(p.read_text())for p in (V/'cpu').glob('*.json')]
 cpudocs={r['document_id']for r in CPU};reused={r['document_id']for r in a['documents']if r['CPU_execution']=='REUSED_UNCHANGED'}
 discovery_unique={x['surface'].casefold()for x in a['new_literal_discoveries']if x['kind']=='product'}
 imported=[x for x in common if x['origin_kind']=='REUSED_SOURCE_ONLY_AI_REVIEW_NOT_NEW_DISCOVERY'];signals=[x for x in imported if x['s_stage']=='S1']
 d5={tuple(x['target'][k]for k in ('product','specification','region','customer_group','supply_pool'))for x in signals if all(x['target'].values())}
 all_urls={json.loads(t)['url']for t, in sqlite3.connect(backup).execute("SELECT payload FROM events WHERE kind='CROSS_DISCOVERED'")}
 failures=collections.Counter(r['error']['category']for r in sources+articles if r.get('error'))
 proof={'at':now(),'base_sha':'0e9cdb1e899c836dfdac68ef76e61a45cc86b269','source_sections_not_verified_industry_facts':{k:dict(v)for k,v in source_counters.items()},
  'endpoint_attempts':{'sources':len(sources),'articles':len(articles),'retries':0,'redirect_subrequests':'NOT_SEPARATELY_INSTRUMENTED'},
  'RSS_active_reused':125,'official_indexes_reused':3,'disabled_feeds_untouched':21,'source_parse_pass':sum(r['status']=='PARSED'for r in sources),'source_failures':sum(r['status']!='PARSED'for r in sources),
  'discovered_distinct_URLs':len(all_urls),'fresh_native_captures':len(fresh),'nonempty_bodies':sum(bool(d['body'])for d in fresh),'unique_nonempty_body_hashes':len({d['body_sha256']for d in fresh if d['body']}),'fresh_body_status':dict(collections.Counter(d['body_status']for d in fresh)),
  'explicit_access_marked_body_views_quarantined':6,'failure_categories':dict(failures),'HTTP403_origin':'Site versus intermediary UNKNOWN; no bypass/retry','initial_parser_failure_native_retention':'8 initial malformed-feed payloads were not retained by first helper version; diagnostics category preserved; fixed for future inputs without re-requesting failures',
  'CPU_cached_for_current_analysis':a['CPU_reused_documents'],'CPU_new_used_for_current_analysis':a['CPU_new_documents'],'CPU_access_marked_view_receipts_excluded':6,'CPU_local_execution_receipts':len(CPU),'CPU_local_status':dict(collections.Counter(r['CPU']['status']for r in CPU)),
  'CPU_additional_preserved_document_other_window_diagnostics_not_used':len(cpudocs&reused),'CPU_note':'A shared-ledger selection initially included69 archived documents for new first-paragraph scopes. Receipts kept; canonical analysis reuses their old outputs. Runner now selects collection IDs only and checks exact old ranges. No installation or API.',
  'CPU_inference_seconds':sum(r['CPU'].get('cpu_seconds',0)for r in CPU),'CPU_inference_wall_seconds':sum(r['CPU'].get('wall_seconds',0)for r in CPU),'CPU_model_loading_not_in_timers':True,
  'available_document_versions':len(all_docs),'available_unique_URLs':len({d['origin_url']for d in all_docs.values()}),'available_body_characters':sum(len(d['body'])for d in all_docs.values()),'actually_read_documents':a['reading_documents'],'actually_read_characters':sum(r['read_characters']for r in a['documents']),'corresponding_body_characters':sum(r['body_characters']for r in a['documents']),'outside_read_ranges':'UNREAD_NOT_NO_BOTTLENECK_NOT_MODEL_FN',
  'novel_CPU_product_surface_forms':len(discovery_unique),'novelty_scope':'Compared with preserved CPU labels, not all past TARGETs; source-literal exploration, meaning UNKNOWN. Lock/padlock from old NIST banners retained as input-selection limitation, not valid products.',
  'source_reviewed_narrative_events_reused':len(imported),'reused_S1_literal_keys':len(signals),'reused_S1_records_with_all_five_fields':len(d5),'these_are_not_new_or_verified_future_forecasts':True,'new_adopted_narrative_events':0,'new_verified_independent_pairs':0,'new_12_36_month_S1_S2_S3':[0,0,0],
  'common_evidence_saved_requeried':len(common),'common_origins':dict(collections.Counter(x['origin_kind']for x in common)),'backup_restore_restart_full_tables':'PASS','SQLite_tables':tables(backup),'snapshot_file_sha256':sha(packed.read_bytes()),'previous_evidence_files_unchanged':unchanged,'previous_API_ledger_all_tables_unchanged':True,
  'actual_Groq_requests':0,'API_tokens':0,'API_cost_KRW':0,'Codex_platform_cost':'UNKNOWN_SEPARATE','automatic_collection':'Two manual bounded passes, no hosted/timer scheduling activated; daily refresh/version functionality fixture-tested only','AI_automatic_reading':'DISABLED','operating_changes':0,'lead_performance':'NOT_RUN'}
 (R/'cpu-executions.json').write_text(json.dumps({'scope':'All local execution receipts, including69 supplemental archived scopes and6 access-marked views excluded downstream; these do not replace historical CPU outputs','documents':CPU},ensure_ascii=False,indent=2)+'\n')
 (R/'verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:proof[k]for k in ['source_parse_pass','fresh_native_captures','nonempty_bodies','fresh_body_status','actually_read_documents','actually_read_characters','common_evidence_saved_requeried','reused_S1_records_with_all_five_fields','previous_evidence_files_unchanged']}))

if __name__=='__main__':main()
