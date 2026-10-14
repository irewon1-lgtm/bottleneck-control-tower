"""Bounded opt-in step-2 receipts. Never fetches sources or runs automation."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sqlite3
import time
from datetime import datetime

from bct.v4.reading_quality import plan_pages, validate_packet, save_result, SYSTEM, RUN_ID
from bct.v4.research_reading import decode, generate, JSONAdapter
from bct.v4.evidence_path import accept
from bct.v4.comparison_evaluation import score_products, score_events
from bct.v4.event_evaluation import metrics
from bct.v4.free_ai import Router, APIError
from bct.v4.store import Ledger, sha, now

R = Path('docs/v4/reading-quality')
OLD = Path('docs/v4/path-comparison/final')
OWN = Path('var/v4/reading-quality/ledger')
API = Path('var/v4/sequential/api-ledger')
SOURCE = Path('var/v4/cross-industry/ledger/v4.sqlite3')


def dump(name, value):
    with (R/name).open('x') as f: json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def config():
    c = json.loads((OLD/'config.json').read_text())
    assert c['max_calls_per_run'] == 1 and c['max_reserved_tokens_per_run'] == 6400
    assert c['max_output_tokens'] == 2048 and c['quota_fraction'] == .8
    return c


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)


def original_files():
    paths = []
    for root in ('docs/v4/post-ui', 'docs/v4/stage4-corpus', 'docs/v4/path-comparison',
                 '.github/workflows', 'src/bct/v4/dashboard_web'):
        paths += [p for p in Path(root).rglob('*') if p.is_file()]
    paths += [Path(p) for p in ('docs/index.html','docs/app.js','docs/style.css','src/bct/v4/dashboard.py') if Path(p).exists()]
    return {str(p): sha(p.read_bytes()) for p in paths}


def prepare():
    if (R/'preflight.json').exists(): return
    c = readonly(SOURCE)
    docs = {did: json.loads(p) for did,p in c.execute('SELECT id,payload FROM documents')}
    pending = json.loads(Path('docs/v4/post-ui/next-inputs.json').read_text())['documents']
    api = readonly(API/'v4.sqlite3')
    attempts = [json.loads(x[0]) for x in api.execute("SELECT payload FROM events WHERE kind='API_ATTEMPT'")]
    history = {a.get('document_id') for a in attempts}
    audit = []
    for x in pending:
        d = docs[x['document_id']]
        reasons = []
        if d.get('provenance') != 'PASS': reasons.append('SOURCE_PROVENANCE_NOT_PASS')
        if not d.get('published_at') or d['published_at'] == 'UNKNOWN': reasons.append('PUBLICATION_UNKNOWN')
        if x.get('usage') == 'Development preparation, not frozen independent holdout': reasons.append('DEVELOPMENT_PREPARATION_HISTORY_NOT_UNUSED_HOLDOUT')
        if d['document_id'] in history: reasons.append('PREVIOUS_API_ATTEMPT')
        audit.append({**x, 'independent_eligibility': 'BLOCKED' if reasons else 'UNVERIFIED_HISTORY', 'reasons': reasons})
    # No new source selection based on AI outputs. This is explicitly a
    # development planned-investment counterexample, not new holdout evidence.
    d = next(d for d in docs.values() if 'gsk-pledges-800m' in d['origin_url'])
    assert d['document_id'] not in history
    import os
    plan = plan_pages(d, config(), os.environ)
    source = plan['pages'][0]
    prompt = 'SOURCE CONTEXTS (separate original spans, not continuous):\n'+'\n\n'.join('[context '+str(i)+']\n'+w['text'] for i,w in enumerate(source['windows']))
    router = Router(Ledger(API), config(), run_id=RUN_ID)
    payload = JSONAdapter(router.env, system=SYSTEM).request('groq', {'prompt': prompt}, cmax:=config()['max_output_tokens'])[2]
    reserve = len(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode())+cmax
    reason = router.available('groq') or router.budget('groq', reserve)
    states = {'provider': router.state('groq'), 'availability_or_budget': reason, 'reserved_tokens': reserve,
              'run_limit': 1, 'task_run_id': RUN_ID, 'remaining_calls_this_task_before_first_attempt': 1,
              'rolling_24h_attempts': len(attempts), 'model': payload['model'], 'output_mode': payload['response_format'],
              'secret_value_recorded': False, 'new_auth_probe': False}
    router.ledger.close()
    dump('source-use-audit.json', {'at': now(), 'documents': audit, 'count': len(audit),
         'publication_unknown': sum(x['publication_hold'] for x in pending),
         'provenance_blocked': sum(x['provenance']!='PASS' for x in pending),
         'independent_eligible_verified': 0, 'required_independent_documents': 20,
         'verdict': 'BLOCKED_NO_VERIFIED_UNUSED_COHORT_OR_INDEPENDENT_SOURCE_REVIEW',
         'note': 'Prepared development does not prove unused. No body recrawl or fabricated gold; no source holds released.'})
    dump('development-input.json', {'document': d, 'source_plan': plan, 'selected_page': 0, 'prompt': prompt,
         'selection': 'DEVELOPMENT_PLANNED_INVESTMENT_COUNTEREXAMPLE_NOT_INDEPENDENT',
         'source_only_draft_before_target': {'reviewer': 'Same Codex session AI, NOT independent or human',
             'facts': ['Plans for facilities are not available qualified supply.', '$800 million is investment, not physical quantity.',
                       '300 jobs is employment, not product volume.', 'No buyer or delivered quantity in selected first page.'],
             'accuracy_scoring': 'NOT_ELIGIBLE_FOR_INDEPENDENT_METRICS'}})
    rows = api.execute('SELECT seq,at,kind,payload FROM events ORDER BY seq').fetchall()
    dump('preflight.json', {'at': now(), 'start_sha': '548a9382a2fbc497fc866989d77d1cd135cc2e4d', 'API': states,
         'protected_files': original_files(), 'source_DB_sha256': sha(SOURCE.read_bytes()),
         'API_original_events': len(rows), 'API_original_prefix_sha256': sha(rows),
         'frozen_for_live': {p: sha(Path(p).read_bytes()) for p in ('src/bct/v4/reading_quality.py','src/bct/v4/research_reading.py','docs/v4/reading-quality/development-input.json')},
         'final_independent_evaluation': 'BLOCKED_NOT_STARTED', 'new_API_calls_at_freeze': 0})
    api.close();c.close()
    print(json.dumps(states))


def total(rows):
    c = Counter()
    for r in rows:
        for k in ('TP','FP','FN'): c[k] += r[k]
    return metrics(c)


def replay():
    if (R/'development-replay.json').exists(): return
    gold = {d['document_id']: d for d in json.loads((OLD/'event-gold.json').read_text())['documents']}
    result = []
    for row in json.loads((OLD/'inputs.json').read_text())['documents']:
        did = row['document_id'];d = row['doc'];w = row['source']['windows']
        old = json.loads((OLD/'responses'/(did+'.json')).read_text());text = old['receipt']['response']['text']
        cpu = json.loads((OLD/'cpu'/(did+'.json')).read_text())
        # Preserve frozen historical scores. Replay all six as consumed
        # development, including packet failure, with missing-vs-failure apart.
        original = old.get('alternative', {}).get('records', [])
        t = time.monotonic();new = validate_packet(text,d,w)
        l = Ledger(OWN)
        with l.worker(): stored = save_result(l,d,text,w,raw=gzip.decompress(Path(row['raw_path']).read_bytes()))
        l.close()
        raw_products = []
        for x in json.loads(text)['extractions']:
            a=x.get('event_attributes',{});name=a.get('product')
            if isinstance(name,str): raw_products.append({'product':{'surface':name}})
        result.append({'document_id':did, 'source_sha256':d['body_sha256'], 'input_windows':w,
            'old_packet_error':old.get('packet_error'), 'CPU_products':score_products([{'product':{'surface':s['text']}}for s in cpu.get('spans',[])if s['label']=='product'],gold[did]),
            'AI_raw_products':score_products(raw_products,gold[did]),
            'before_products':score_products(original,gold[did]),'after_products':score_products(new['records'],gold[did]),
            'before_events':score_events(original,gold[did]),'after_events':score_events(new['records'],gold[did]),
            'new_validation':new, 'seconds':time.monotonic()-t,
            'stored_records':len(stored['records']), 'CPU_event_support':'UNSUPPORTED_NO_COMPARATIVE_EVENT_METRIC'})
    summary = {k:total(x[k] for x in result) for k in ('CPU_products','AI_raw_products','before_products','after_products','before_events','after_events')}
    dump('development-replay.json', {'at':now(),'scope':'Consumed six-document partial-input development diagnostic. NOT independent; historical gold and scores unchanged.',
         'documents':result,'metrics':summary,'new_API_calls':0,'S1_S2_S3':[0,0,0],
         'missing_scope':'Unread/HTTP/unprocessed paths not counted as model FN; before packet failure is end-to-end unprocessed, not model omission.',
         'CPU_role_quantity_time':'UNSUPPORTED_NOT_ZERO_ACCURACY',
         'scored_source_fields':'Product and product/role/actuality events only; buyer/quantity/time need independent relation gold.',
         'adoption':'HOLD_PENDING_NEW_INDEPENDENT20_AND_NO_FN_INCREASE'})
    print(json.dumps(summary))


def live():
    if (R/'live.json').exists(): print('EXISTING_RECEIPT_NO_RETRY');return
    pre=json.loads((R/'preflight.json').read_text())
    for p,h in pre['frozen_for_live'].items(): assert sha(Path(p).read_bytes())==h,'FROZEN_CODE_OR_INPUT_CHANGED'
    row=json.loads((R/'development-input.json').read_text());d=row['document'];source=row['source_plan']['pages'][0]
    # Re-run policy at the final boundary; this neither fetches nor marks read.
    import os
    assert plan_pages(d,config(),os.environ)==row['source_plan']
    l=Ledger(API)
    try:
        with l.worker():
            receipt=generate(l,config(),row['prompt'],d,source['windows'],phase='reading-quality-step2',system=SYSTEM,run_id=RUN_ID)
    finally:l.close()
    output={'at':now(),'document_id':d['document_id'],'source':source,'receipt':receipt,'same_input_CPU':'NOT_RUN_YET',
            'not_independent':True,'S1_S2_S3':[0,0,0]}
    if receipt['status']=='RECEIVED':
        l=Ledger(OWN)
        try:
            with l.worker():output['validation']=save_result(l,d,receipt['response']['text'],source['windows'],raw=source_raw(d))
        finally:l.close()
    dump('live.json',output)
    print(json.dumps({'status':receipt['status'],'usage':receipt.get('response',{}).get('usage'),
          'records':len(output.get('validation',{}).get('records',[])), 'held':output.get('validation',{}).get('held')}))


def source_raw(d):
    c=readonly(SOURCE)
    row=c.execute('SELECT data FROM blobs WHERE id=?',(d['raw_sha256'],)).fetchone();c.close()
    assert row and sha(row[0])==d['raw_sha256'];return row[0]


def finalize():
    """Offline final-code replay and complete storage proof; never new HTTP."""
    if (R/'RESULTS.json').exists(): return
    from bct.v4.quote_diagnostics import diagnose
    previous = json.loads(Path('docs/v4/stage4-corpus/round3/old13-diagnosis.json').read_text())
    oldroot = Path('docs/v4/stage4-corpus/round2')
    inputs = {r['document_id']: r for r in json.loads((oldroot/'inputs.json').read_text())['documents']}
    old13 = []
    receipts = [(p,json.loads(p.read_text())) for p in sorted((oldroot/'auth-resume/documents').glob('*.json'))]
    receipts += [(oldroot/'groq-responses.json',x) for x in json.loads((oldroot/'groq-responses.json').read_text())['documents']]
    for p,x in receipts:
        if not x.get('response'): continue
        did=x['document_id'];r=inputs[did];source=r.get('source') or x['reading']['coverage']
        detail=diagnose(x['response']['text'],r['doc'],source)
        old13.append({'document_id':did,'response_file':str(p),'response_file_sha256':sha(p.read_bytes()),
                      'body_sha256':r['doc']['body_sha256'], 'diagnosis':detail,
                      'read_characters':sum(w['end']-w['start'] for w in source['windows'])})
    assert len(old13)==13
    dump('historical13-readonly.json',{'documents':old13,'source': 'Stored actual responses, exact original source windows; no response repair or historical rescoring',
         'historical_causes_reused':previous['counts'],'historical_gold_or_scores_modified':False})
    dev=json.loads((R/'development-replay.json').read_text());final=[]
    rows={r['document_id']:r for r in json.loads((OLD/'inputs.json').read_text())['documents']}
    gold={g['document_id']:g for g in json.loads((OLD/'event-gold.json').read_text())['documents']}
    for x in dev['documents']:
        d=rows[x['document_id']]['doc'];windows=x['input_windows'];text=x['new_validation']['original_response']
        l=Ledger(OWN)
        try:
            with l.worker():validation=save_result(l,d,text,windows)
        finally:l.close()
        final.append({'document_id':d['document_id'],'products':score_products(validation['records'],gold[d['document_id']]),
                      'events':score_events(validation['records'],gold[d['document_id']]),'validation':validation})
    live=json.loads((R/'live.json').read_text());row=json.loads((R/'development-input.json').read_text());d=row['document']
    l=Ledger(OWN)
    try:
        with l.worker():final_live=save_result(l,d,live['receipt']['response']['text'],live['source']['windows'])
        l.backup(R/'research-snapshot.sqlite3')
    finally:l.close()
    # Reopen and compare every table, including raw bytes, responses and holds.
    def tables(path):
        c=readonly(path);out={}
        for table in ('metadata','blobs','documents','captures','readings','runs','firsts','events'):
            data=c.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
            out[table]={'rows':len(data),'sha256':sha([[v.hex() if isinstance(v,bytes) else v for v in row] for row in data])}
        c.close();return out
    assert tables(OWN/'v4.sqlite3')==tables(R/'research-snapshot.sqlite3')
    with (R/'research-snapshot.sqlite3').open('rb') as f:
        with gzip.GzipFile(filename=str(R/'research-snapshot.sqlite3.gz'),mode='wb',mtime=0) as z:z.write(f.read())
    (R/'research-snapshot.sqlite3').unlink()
    pre=json.loads((R/'preflight.json').read_text())
    assert all(sha(Path(p).read_bytes())==h for p,h in pre['protected_files'].items())
    assert sha(SOURCE.read_bytes())==pre['source_DB_sha256']
    a=readonly(API/'v4.sqlite3');prefix=a.execute('SELECT seq,at,kind,payload FROM events WHERE seq<=? ORDER BY seq',(pre['API_original_events'],)).fetchall()
    assert sha(prefix)==pre['API_original_prefix_sha256']
    added=[json.loads(x[0]) for x in a.execute("SELECT payload FROM events WHERE kind='API_ATTEMPT' AND seq>?",(pre['API_original_events'],))]
    assert len(added)==1 and added[0]['run_id']==RUN_ID
    attempt=added[0];response=next(json.loads(p) for p, in a.execute("SELECT payload FROM events WHERE kind='API_RECEIVED'") if json.loads(p).get('attempt_id')==attempt['attempt_id'])
    latency=(datetime.fromisoformat(response['at'])-datetime.fromisoformat(attempt['at'])).total_seconds();a.close()
    audit=json.loads((R/'source-use-audit.json').read_text())
    ready=[];blocked=[];c=readonly(SOURCE)
    import os
    for x in audit['documents']:
        d=json.loads(c.execute('SELECT payload FROM documents WHERE id=?',(x['document_id'],)).fetchone()[0])
        try:
            p=plan_pages(d,config(),os.environ)
            ready.append({'document_id':d['document_id'],'pages':len(p['pages']),'prepared_characters':p['prepared']['read_characters'],
                          'body_characters':len(d['body']),'withheld_context_count':p['pages'][0]['withheld_context_count'],
                          'actually_read':live['source']['selected_characters'] if d['document_id']==row['document']['document_id'] else 0})
        except (ValueError,APIError) as e:blocked.append({'document_id':d['document_id'],'reason':str(e)})
    c.close()
    dump('input-coverage-audit.json',{'prepared':ready,'blocked':blocked,'prepared_documents':len(ready),
         'blocked_documents':len(blocked),'blocked_reasons':dict(Counter(x['reason']for x in blocked)),
         'all_prepared_pages_are_not_calls_or_AI_read':True,'source_reviews_or_holds_changed':False})
    proof={'at':now(),'tables':tables(OWN/'v4.sqlite3'),'backup_restore':'PASS_ALL_8_TABLE_DIGESTS',
           'protected_old_files':len(pre['protected_files']),'protected_old_files_unchanged':True,'source_DB_unchanged':True,
           'old_API_event_prefix_unchanged':True,'new_API_attempts':len(added),'fixed_task_limit':1,
           'archive_sha256':sha((R/'research-snapshot.sqlite3.gz').read_bytes()),'canonical_research_UI_DB_modified':False}
    dump('storage-proof.json',proof)
    report={'at':now(),'start_sha':pre['start_sha'],'historical13':{'responses_read':13,'originals_or_scores_changed':False,'new_calls':0},
         'same_input_development':{'documents':6,'CPU_products':dev['metrics']['CPU_products'],
            'AI_raw_products':dev['metrics']['AI_raw_products'],
            'before_strict_packet_products':dev['metrics']['before_products'],
            'prior_existing_packet_isolation_diagnostic_products':{'TP':7,'FP':2,'FN':18,'source':'docs/v4/path-comparison/final/packet-isolation-diagnostic.json'},
            'final_products':total(x['products']for x in final),'final_events':total(x['events']for x in final),
            'scope':'Consumed development partial windows, not new independent performance; packet recovery mechanism already had a prior diagnostic.',
            'documents_detail':final},
         'new_AI':{'documents':1,'characters':live['source']['selected_characters'],'body_characters':len(row['document']['body']),
            'unread_characters':len(row['document']['body'])-live['source']['selected_characters'],
            'raw_extractions':len(json.loads(live['receipt']['response']['text'])['extractions']),
            'final_validation':final_live,'transport_seconds_from_ledger':latency,
            'source':'BioSpace original report, primary government/company announcement NOT independently verified',
            'manual_source_check':'Same-session Codex AI source inspection only; not independent truth; no P/R assigned.',
            'CPU_same_input':'live-cpu.json; original pinned model, no reinstall; no verified product gold hence unscored'},
         'independent_evaluation':{'required':20,'verified_unused_documents':0,'scored_documents':0,
            'verdict':'BLOCKED_DEVELOPMENT_HISTORY_AND_NO_INDEPENDENT_REVIEWER','old_holdouts_reused_as_new':False},
         'quality_adoption':'FAIL_DEVELOPMENT_RECALL_BELOW_CPU_AND_EVENT_EXTRACTION_UNRESOLVED; INDEPENDENT_GATE_BLOCKED',
         'S1_S2_S3_change':[0,0,0],'pairing':'NOT_RUN_CURRENT_STEP2_ONLY','forecast':'NOT_RUN',
         'usage':{'POST':1,'auth_GET':0,'reported_tokens':live['receipt']['response']['usage'],'Free_API_cost_KRW':0,
                  'CPU_new_documents':1,'platform_usage_cost':'UNKNOWN_SEPARATE','additional_API_calls_allowed_this_task':0},
         'next_step3_verified_inputs':{'source_located_product_discoveries':len(final_live['records']),
                  'verified_actual_demand_or_supply_events':0,'independent_pairs':0,
                  'hold':'Facility plans only. Need independent semantic review and actual order/qualified supply/need-period evidence.'}}
    dump('RESULTS.json',report)
    print(json.dumps({k:report[k]for k in ('independent_evaluation','quality_adoption','usage','next_step3_verified_inputs')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','replay','live','finalize']);a=p.parse_args()
    {'prepare':prepare,'replay':replay,'live':live,'finalize':finalize}[a.action]()
