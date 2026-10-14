"""Bounded post-UI research task. Existing intake/store/parsers; zero AI API.

Initial URL/review scope is immutable. UI assets and old evidence are never edited.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import urlsplit

from bct.v4.adapters import SourceClient
from bct.v4.cross_industry import collect
from bct.v4.store import Ledger, now, sha

R=Path('docs/v4/post-ui');V=Path('var/v4/cross-industry');DB=V/'ledger/v4.sqlite3'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def readonly():
    return sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True)


def freeze():
    target=R/'initial-scope.json'
    if target.exists():return json.loads(target.read_text())
    with readonly()as c:
        leads={json.loads(t)['url']:json.loads(t)for t, in c.execute("SELECT payload FROM events WHERE kind='CROSS_DISCOVERED' ORDER BY seq")}
        attempted={json.loads(t)['url']for t, in c.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_ATTEMPT'")}
        known={u for u, in c.execute('SELECT url FROM documents')}
        known.update(r['doc']['origin_url']for r in json.loads((V/'existing-documents.json').read_text()))
        for f in ['docs/v4/stage4-corpus/round2/inputs.json','docs/v4/stage4-corpus/round3/inputs.json','docs/v4/path-comparison/final/inputs.json']:
            known.update((r.get('doc')or r.get('document')or{})['origin_url']for r in json.loads(Path(f).read_text())['documents'])
        pending=[{'id':sha(u),'url':u,**r}for u,r in leads.items()if u not in attempted|known]
        counts={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]for t in ['metadata','blobs','documents','captures','readings','runs','firsts','events']}
    analysis=json.loads(Path('docs/v4/cross-industry/analysis.json').read_text())
    mentions=[r for r in analysis['new_literal_discoveries']if r['kind']=='product']
    products={}
    for x in mentions:
        key=x['surface'].casefold();products.setdefault(key,{'id':sha(['initial-product',key]),'surface':x['surface'],'mentions':[]})['mentions'].append(x)
    protected={}
    tracked=subprocess.check_output(['git','ls-files','docs/v4','docs/index.html','docs/app.js','docs/style.css','docs/view-model.js','src/bct/v4/dashboard_web','.github/workflows'],text=True).splitlines()
    for name in tracked:
        if name not in ('docs/v4/PROGRESS.json','docs/v4/EXECUTION_PLAN.md'):
            protected[name]=hashlib.sha256(Path(name).read_bytes()).hexdigest()
    result={'at':now(),'start_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'URLs':pending,'product_groups':list(products.values()),'event_review_queue':analysis['research_review_queue'],'baseline_tables':counts,'baseline_database_sha256':sha(DB.read_bytes()),'protected_files':protected,'scope_policy':'Frozen initial URL and consumed review records only; later discoveries separate; no AI API/model/prompt/automation/UI asset changes','completion_criteria':['Every initial URL has a terminal source/body/setting outcome or explicit unattempted remainder','Every initial product/event has source-located review or specific hold reason','Append-only storage, restart/no-duplicate, preserved UI and read-only data match, backup/restore','Development push and exact-SHA CI; no predictive-performance claim']}
    write(target,result);return result


ACCESS=re.compile(r'class=[\"\'][^\"\']*\bgsd-paywall\b|[\"\']isAccessibleForFree[\"\']\s*:\s*false|<title[^>]*>\s*(?:Just a moment|Access Denied|Attention Required|Robot Check)',re.I)
SUBSCRIPTION=re.compile(r"you(?:'|’)ve reached your limit of free weekly articles|for uninterrupted access, sign in, subscribe or upgrade",re.I)


class PublicClient(SourceClient):
    """Precheck actual raw response; preserve blocked original, never read its body."""
    def __init__(self):
        super().__init__();self.saved={}

    def fetch(self,url):
        if url not in self.saved:self.saved[url]=super().fetch(url)
        return self.saved[url]

    def document(self,url):
        raw,final,status,kind=self.fetch(url)
        if ACCESS.search(raw.decode('utf-8',errors='replace')):
            at=now();doc={'document_id':'v4doc-'+sha([url,sha(raw)]),'origin_url':final,'requested_url':url,'body':'','body_sha256':sha(b''),'raw_sha256':sha(raw),'body_status':'UNAVAILABLE','origin_id':'UNKNOWN','origin_publisher':'UNKNOWN','published_at':None,'acquired_at':at,'available_at':at,'provenance':'BLOCKED','provenance_verified':False,'provenance_blockers':['EXPLICIT_ACCESS_RESTRICTION_MARKER'],'access_review':'RESTRICTED_NO_BODY_PROCESSING'}
            return doc,raw,{}
        return super().document(url)


def batch():
    scope=freeze();urls={r['url']for r in scope['URLs']}
    # No discovery/refetch outside the freeze, even after a day boundary.
    with readonly()as c:
        old={json.loads(t)['url']for t, in c.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_ATTEMPT'")}
    if not urls-old:return {'remaining':0,'network_requests':0,'no_op':True}
    result=collect(V/'ledger',[],article_limit=24,workers=6,allowed_urls=urls,refresh_existing=False,client=PublicClient())
    write(R/'batches'/(result['run_id']+'.json'),result)
    return {'run_id':result['run_id'],'captured':len(result['captured']),'remaining':result['pending_unattempted'],'source_attempts':result['sources_executed']}


def packet():
    if (R/'product-review-packet.json').exists():
        rows=json.loads((R/'product-review-packet.json').read_text())['products']
        return {'products':len(rows),'mentions':sum(len(x['references'])for x in rows),'reused':True}
    scope=freeze()
    with readonly()as c:docs={i:json.loads(t)for i,t in c.execute('SELECT id,payload FROM documents')}
    rows=[]
    for group in scope['product_groups']:
        refs=[]
        for m in group['mentions']:
            d=docs.get(m['document_id']);a,b=m['reference']['start'],m['reference']['end']
            valid=bool(d and sha(d['body'].encode())==m['body_sha256'] and d['body'][a:b]==m['surface'])
            refs.append({**m,'verified':valid,'url':d['origin_url']if d else None,'published_at':d.get('published_at')if d else None,'context_start':max(0,a-300),'context_end':min(len(d['body']),b+500)if d else None,'context':d['body'][max(0,a-300):b+500]if valid else None})
        rows.append({**group,'references':refs})
    write(R/'product-review-packet.json',{'at':now(),'review_method':'Codex source-only assisted research review, not human/independent performance; consumed material','products':rows})
    return {'products':len(rows),'mentions':sum(len(x['references'])for x in rows)}


def official():
    """Reuse existing no-key transports/parsers, not their operating DB writers."""
    from bct.collectors.federal_register.collector import FederalRegisterTransport,search_url,search_params,parse_response as parse_fr
    from bct.collectors.usaspending.collector import USAspendingTransport,request_body,parse_response as parse_usa,ENDPOINT as USA_URL
    l=Ledger(V/'ledger')
    jobs=[('Federal Register','chemical',search_url(search_params('chemical',3))),('USAspending','chemical',USA_URL)]
    results=[]
    with l.worker():
        previous={json.loads(t)['job_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_OFFICIAL_ATTEMPT'")}
        for name,term,url in jobs:
            key=sha([name,term,'post-ui-1'])
            if key in previous:continue
            with l.db:l.event('POST_UI_OFFICIAL_ATTEMPT',{'job_id':key,'name':name,'url':url,'at':now(),'automatic_retries':0})
            raw=None
            try:
                raw=FederalRegisterTransport(timeout_seconds=20).get(url)if name=='Federal Register'else USAspendingTransport(timeout_seconds=20).post(request_body(term,'keyword',3))
                with l.db:l.db.execute('INSERT OR IGNORE INTO blobs VALUES(?,?)',(sha(raw),raw))
                parsed=parse_fr(raw,3)if name=='Federal Register'else parse_usa(raw,3)
                documents=[]
                for idx,item in enumerate(parsed):
                    body=json.dumps(asdict(item),ensure_ascii=False,sort_keys=True);at=now()
                    published=item.publication_date if name=='Federal Register'else None
                    doc={'document_id':'post-ui-official-'+sha([key,idx,sha(raw)]),'origin_url':item.html_url if name=='Federal Register'else url,'origin_id':item.number if name=='Federal Register'else item.external_id,'origin_publisher':name,'body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),'body_status':'PARTIAL','published_at':published,'publication_basis':'API_RESULTS_PUBLICATION_DATE'if published else'UNKNOWN_LAST_MODIFIED_IS_NOT_PUBLICATION','acquired_at':at,'available_at':at,'provenance':'BLOCKED','provenance_blockers':['OFFICIAL_METADATA_OR_AWARD_ROW_NOT_PHYSICAL_PRODUCT_EVIDENCE'],'source_row':{'json_pointer':f'/results/{idx}','snapshot_url':url},'physical_quantity':'UNKNOWN','evidence_role':'OFFICIAL_METADATA_ONLY'}
                    l.capture(doc,raw);documents.append(doc['document_id'])
                    with l.db:l.event('POST_UI_OFFICIAL_ROW',{'job_id':key,'document_id':doc['document_id'],'source_row':doc['source_row'],'parsed_fields':asdict(item),'physical_quantity':'UNKNOWN','not_supply_fact':True})
                result={'job_id':key,'name':name,'at':now(),'url':url,'status':'CAPTURED','raw_sha256':sha(raw),'records':len(parsed),'documents':documents,'input_query':term,'new_AI_calls':0}
            except Exception as e:
                result={'job_id':key,'name':name,'at':now(),'url':url,'status':'BLOCKED','error_type':type(e).__name__,'http_status':getattr(e,'code',None),'raw_sha256':sha(raw)if raw is not None else None,'reason':'OFFICIAL_METADATA_PARSE_FAILURE'if raw is not None else'OFFICIAL_ACCESS_OR_COMMUNICATION_FAILURE','automatic_retries':0}
            with l.db:l.event('POST_UI_OFFICIAL_RESULT',result)
            results.append(result)
        # A missing real SEC contact is a setting hold, never invented identity.
        sec={'name':'SEC','status':'SETTING_REQUIRED'if not os.environ.get('BCT_SEC_USER_AGENT')else'AVAILABLE_NOT_REQUESTED_NO_CIK_SELECTED','reason':'Real project/contact User-Agent required; no credential invented','network_requests':0}
        if not l.db.execute("SELECT 1 FROM events WHERE kind='POST_UI_SEC_SETTING'").fetchone():
            with l.db:l.event('POST_UI_SEC_SETTING',sec)
    l.close()
    if results:write(R/'official-results.json',{'at':now(),'results':results,'SEC':sec,'amount_policy':'Award amounts are money, never product volume or qualified capacity'})
    return results


def body_views():
    from bct.v4.cross_industry import alternative_body_view
    scope=freeze();urls={r['url']for r in scope['URLs']};l=Ledger(V/'ledger');out=[]
    with l.worker():
        done={json.loads(t)['original_document_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_BODY_REVIEW'")}
        docs=[json.loads(t)for t, in l.db.execute('SELECT payload FROM documents')]
        for doc in docs:
            if doc.get('requested_url')not in urls or doc['body_status']!='UNAVAILABLE'or doc['document_id']in done:continue
            raw=l.db.execute('SELECT data FROM blobs WHERE id=?',(doc['raw_sha256'],)).fetchone()[0]
            result={'original_document_id':doc['document_id'],'url':doc['requested_url'],'at':now(),'new_network_calls':0}
            try:
                if ACCESS.search(raw.decode('utf-8',errors='replace')):raise ValueError('EXPLICIT_ACCESS_RESTRICTION_MARKER')
                view=alternative_body_view(doc,raw)
                if view and SUBSCRIPTION.search(html.unescape(view['body'])):
                    raise ValueError('EXPLICIT_SUBSCRIPTION_TEXT_NOT_USABLE_BODY')
                if view:
                    l.capture(view,raw);result.update(status='DERIVED_PARTIAL',document_id=view['document_id'],body_sha256=view['body_sha256'],body_characters=len(view['body']),publication_basis='ORIGINAL_METADATA_UNCHANGED',provenance='BLOCKED_UNVERIFIED_EXTRACTION_FULLNESS')
                else:result.update(status='EXTRACTION_UNAVAILABLE',reason='Existing baseline and alternative extractors found no usable body; JS shell/format unverified')
            except ValueError as e:result.update(status='ACCESS_RESTRICTED',reason=str(e))
            with l.db:l.event('POST_UI_BODY_REVIEW',result)
            out.append(result)
    l.close()
    if out:write(R/'body-review.json',{'at':now(),'documents':out,'scope':'Offline saved raw originals only; restricted pages excluded, derived versions separate; zero network'})
    return dict(Counter(r['status']for r in out))


def official_text():
    from bct.collectors.federal_register.fulltext import FullTextTransport,full_text_url
    l=Ledger(V/'ledger');out=[]
    with l.worker():
        rows=[json.loads(t)for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_OFFICIAL_ROW'")]
        tried={json.loads(t)['url']for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_FULLTEXT_ATTEMPT'")}
        for r in rows:
            fields=r['parsed_fields']
            if 'trichloroethylene'not in fields.get('title','').lower():continue
            url=full_text_url(fields['number'],fields['publication_date'])
            if url in tried:continue
            with l.db:l.event('POST_UI_FULLTEXT_ATTEMPT',{'url':url,'at':now(),'reason':'Fill chemical regulatory original-text gap using existing indexed full-text path','automatic_retries':0})
            try:
                raw=FullTextTransport(timeout_seconds=20).get(url)
                if not raw or fields['number'].encode()not in raw:raise ValueError('FULLTEXT_IDENTITY_MISMATCH')
                body=raw.decode('utf-8');doc={'document_id':'post-ui-fr-text-'+sha(raw),'body':body,'body_sha256':sha(body.encode()),'raw_sha256':sha(raw),'origin_url':url,'origin_id':fields['number'],'origin_publisher':'Federal Register','published_at':fields['publication_date'],'publication_basis':'INDEXED_API_PUBLICATION_DATE_AND_MATCHED_TEXT_DOCUMENT_NUMBER','acquired_at':now(),'body_status':'FULL','provenance':'BLOCKED','provenance_blockers':['REGULATORY_DOCUMENT_NOT_QUALIFIED_SUPPLY_EVIDENCE'],'source_row':r['source_row']}
                l.capture(doc,raw);result={'url':url,'at':now(),'status':'CAPTURED','document_id':doc['document_id'],'body_sha256':doc['body_sha256'],'raw_sha256':sha(raw),'body_characters':len(body),'legal_edition':'Federal Register site rendition, not separately checked official legal edition','automatic_retries':0}
            except Exception as e:result={'url':url,'at':now(),'status':'BLOCKED','error_type':type(e).__name__,'http_status':getattr(e,'code',None),'automatic_retries':0}
            with l.db:l.event('POST_UI_FULLTEXT_RESULT',result)
            out.append(result)
    l.close()
    if out:write(R/'official-text.json',{'at':now(),'results':out})
    return out


def apply_reviews():
    inputs=[(json.loads((R/filename).read_text())[key],kind)for filename,key,kind in [('product-reviews.json','products','POST_UI_PRODUCT_REVIEW'),('event-reviews.json','events','POST_UI_EVENT_REVIEW')]]
    l=Ledger(V/'ledger');out=Counter()
    with l.worker():
        for rows,kind in inputs:
            old={json.loads(t)['review_id']for t, in l.db.execute('SELECT payload FROM events WHERE kind=?',(kind,))}
            for r in rows:
                if r['review_id']in old:continue
                for ref in r['references']:
                    d=json.loads(l.db.execute('SELECT payload FROM documents WHERE id=?',(ref['document_id'],)).fetchone()[0]);a,b=ref.get('start'),ref.get('end')
                    if a is None:a,b=ref['reference']['start'],ref['reference']['end']
                    quote=ref.get('quote',ref.get('surface'))
                    if sha(d['body'].encode())!=ref['body_sha256']or d['body'][a:b]!=quote:raise ValueError('REVIEW_REFERENCE_MISMATCH')
                with l.db:l.event(kind,r)
                out[kind]+=1
        urls={r['url']for r in freeze()['URLs']}
        held={json.loads(t)['document_id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_ACCESS_HOLD'")}
        for did,t in l.db.execute('SELECT id,payload FROM documents').fetchall():
            d=json.loads(t)
            if d.get('requested_url')not in urls or did in held:continue
            if SUBSCRIPTION.search(html.unescape(d['body'])):
                with l.db:l.event('POST_UI_ACCESS_HOLD',{'document_id':did,'url':d['requested_url'],'reason':'EXPLICIT_SUBSCRIPTION_TEXT_NOT_USABLE_BODY','at':now(),'original_preserved':True,'raw_and_derived_versions_preserved':True,'not_read_by_CPU_or_external_AI':True})
                out['POST_UI_ACCESS_HOLD']+=1
    l.close();return dict(out)


def export():
    """Requery initial outcomes; preserve original snapshot/reports separately."""
    scope=freeze();l=Ledger(V/'ledger')
    with l.worker():
        events=[(k,json.loads(t))for k,t in l.db.execute('SELECT kind,payload FROM events ORDER BY seq')]
        docs={i:json.loads(t)for i,t in l.db.execute('SELECT id,payload FROM documents')}
        results={x['url']:x for k,x in events if k=='CROSS_ARTICLE_RESULT'}
        views={x['url']:x for k,x in events if k=='POST_UI_BODY_REVIEW'and x['status']=='DERIVED_PARTIAL'}
        held={x['document_id']for k,x in events if k=='POST_UI_ACCESS_HOLD'}
        outcomes=[]
        for row in scope['URLs']:
            r=results.get(row['url']);result={**row,'outcome':'UNATTEMPTED'}
            if r:
                if r['status']!='CAPTURED':
                    err=r.get('error')or{};result.update(outcome='SETTING_REQUIRED'if err.get('type')=='SEC_IDENTITY_REQUIRED'else'ACCESS_UNAVAILABLE',error=err)
                else:
                    d=docs[r['document_id']];v=views.get(row['url']);blocked=d.get('access_review')=='RESTRICTED_NO_BODY_PROCESSING'or bool(v and v['document_id']in held)
                    if v and v['document_id']not in held:d=docs[v['document_id']]
                    result.update(outcome='ACCESS_UNAVAILABLE'if blocked else'BODY_CAPTURED'if d['body']else'ORIGINAL_ONLY_EXTRACTION_UNAVAILABLE',document_id=d['document_id'],original_document_id=r['document_id'],raw_sha256=d['raw_sha256'],body_sha256=d['body_sha256'],body_status=d['body_status'],body_characters=0 if blocked else len(d['body']),published_at=d.get('published_at'),publication_basis=d.get('publication_basis')or d.get('publication_precision')or'Original source verifier; UNKNOWN if absent',acquired_at=d.get('acquired_at'),origin_url=d['origin_url'],read_by_new_CPU_or_API=False)
            outcomes.append(result)
        # Separate discoveries from the frozen295. Only one relevant regulatory
        # original was requested; the other API-indexed URLs remain explicit.
        extra=[];text=[x for k,x in events if k=='POST_UI_FULLTEXT_RESULT'and x['status']=='CAPTURED']
        for k,x in events:
            if k!='POST_UI_OFFICIAL_ROW'or'html_url'not in x['parsed_fields']:continue
            f=x['parsed_fields'];resolved=next((r for r in text if f['number']in r['url']),None)
            extra.append({'id':sha(['post-ui-extra',f['html_url']]),'url':f['html_url'],'source_document':x['document_id'],'status':'OFFICIAL_TEXT_CAPTURED'if resolved else'METADATA_ONLY_UNATTEMPTED_BODY','text_document_id':resolved['document_id']if resolved else None,'scope':'Additional official discovery outside frozen295'})
        known={json.loads(t)['id']for t, in l.db.execute("SELECT payload FROM events WHERE kind='POST_UI_ADDITIONAL_QUEUE'")}
        for x in extra:
            if x['id']not in known:
                with l.db:l.event('POST_UI_ADDITIONAL_QUEUE',x)
        product=json.loads((R/'product-reviews.json').read_text())['products'];reviewed=json.loads((R/'event-reviews.json').read_text())['events']
        counts=dict(Counter(r['outcome']for r in outcomes));body=[r for r in outcomes if r['outcome']=='BODY_CAPTURED']
        summary={'at':now(),'initial_URLs':len(outcomes),'initial_outcomes':counts,'initial_body_status':dict(Counter(r['body_status']for r in body)),'raw_originals_acquired':sum('document_id'in r for r in outcomes),'usable_body_hashes':len({r['body_sha256']for r in body}),'initial_existing_reused':0,'initial_unattempted':counts.get('UNATTEMPTED',0),'additional_discovered_URLs':len(extra),'additional_pending_body_URLs':sum(r['status']=='METADATA_ONLY_UNATTEMPTED_BODY'for r in extra),'initial_product_groups':len(product),'initial_product_mentions':sum(len(r['references'])for r in product),'product_exploration_retained':sum(r['active_product_exploration']for r in product),'nonproduct_groups_excluded_with_originals_preserved':sum(not r['active_product_exploration']for r in product),'product_classes':dict(Counter(r['classification']for r in product)),'event_review_outcomes':dict(Counter(r['verdict']for r in reviewed)),'event_reviews':len(reviewed),'new_S_promotions':0,'new_verified_independent_pairs':0,'new_CPU_runs':0,'new_external_AI_calls':0,'AI_tokens':0,'API_cost_KRW':0,'public_data_transport_calls':len(scope['URLs'])+len([x for k,x in events if k in ('POST_UI_OFFICIAL_ATTEMPT','POST_UI_FULLTEXT_ATTEMPT')]),'redirect_subrequests':'UNKNOWN_NOT_SEPARATELY_INSTRUMENTED','platform_usage_and_cost':'UNKNOWN','source_read_scope':'Product111 recorded contexts and14 event passages; newly acquired body ranges available but not whole-document AI analysis','subscription_views_quarantined':len(held)}
        write(R/'initial-outcomes.json',{'at':summary['at'],'initial':outcomes,'additional':extra})
        write(R/'SUMMARY.json',summary)
        inputs=[]
        for row in body:
            d=docs[row['document_id']];inputs.append({'document_id':d['document_id'],'url':d['origin_url'],'raw_sha256':d['raw_sha256'],'body_sha256':d['body_sha256'],'published_at':d.get('published_at'),'acquired_at':d.get('acquired_at'),'available_range':{'start':0,'end':len(d['body'])},'already_AI_read':False,'publication_hold':not bool(d.get('published_at')),'provenance':d.get('provenance'),'usage':'Development preparation, not frozen independent holdout'})
        write(R/'next-inputs.json',{'at':now(),'documents':inputs,'reviewed_product_packet':'product-review-packet.json','event_review_packet':'event-reviews.json','metadata_rows':6,'official_additional_text_documents':[r['document_id']for r in text],'AI_calls':0,'not_gold_or_model_performance':True})
    backup=Path('var/v4/post-ui/research-backup.sqlite3');backup.parent.mkdir(parents=True,exist_ok=True)
    if backup.exists():
        # Never overwrite an earlier backup; new content gets another name.
        backup=backup.with_name('research-backup-'+str(l.db.execute('SELECT MAX(seq) FROM events').fetchone()[0])+'.sqlite3')
    if not backup.exists():l.backup(backup)
    l.close();archive=R/'research-snapshot.sqlite3.gz';archive.write_bytes(gzip.compress(backup.read_bytes(),mtime=0))
    from v4_cross_industry_verify import tables
    current=tables(DB);assert current==tables(backup)
    restored=Path('var/v4/post-ui/restored')/sha(archive.read_bytes())/'v4.sqlite3';restored.parent.mkdir(parents=True,exist_ok=True)
    if not restored.exists():restored.write_bytes(gzip.decompress(archive.read_bytes()))
    check=Ledger(restored.parent);check.close();assert tables(restored)==current
    prefix={}
    with readonly()as c:
        attempts=Counter(json.loads(t)['url']for t, in c.execute("SELECT payload FROM events WHERE kind='CROSS_ARTICLE_ATTEMPT'"))
        assert max(attempts.values())==1,'Duplicate network attempt'
        for table,n in scope['baseline_tables'].items():
            h=hashlib.sha256()
            for row in c.execute('SELECT * FROM '+table+' ORDER BY rowid LIMIT ?',(n,)):
                for x in row:
                    raw=x if isinstance(x,bytes)else json.dumps(x,ensure_ascii=False).encode();h.update(len(raw).to_bytes(8,'big'));h.update(raw)
            prefix[table]={'rows':n,'sha256':h.hexdigest()}
    baseline=json.loads(Path('docs/v4/cross-industry/verification.json').read_text())['SQLite_tables'];assert prefix==baseline,'Original research row prefix changed'
    for name,expected in scope['protected_files'].items():assert sha(Path(name).read_bytes())==expected,name
    assert tables(Path('var/v4/sequential/api-ledger/v4.sqlite3'))==tables(Path('var/v4/path-comparison/shared-API-backup/v4.sqlite3'))
    verification={'at':now(),'snapshot_file_sha256':sha(archive.read_bytes()),'tables':current,'backup_restore_restart':'PASS','original_row_prefix_unchanged':prefix,'protected_files_unchanged':len(scope['protected_files']),'external_AI_ledger_unchanged':True,'initial_URL_attempts_max':max(attempts.values()),'summary':summary,'preserved_original_snapshot':'docs/v4/cross-industry/research-snapshot.sqlite3.gz'}
    write(R/'VERIFICATION.json',verification)
    progress=Path('docs/v4/PROGRESS.json');p=json.loads(progress.read_text());p['post_ui'].update(status='INITIAL_SCOPE_PROCESSED_SOURCE_REVIEWS_STORED',summary=summary,snapshot=str(archive),verification=str(R/'VERIFICATION.json'),next='Initial295 unattempted0; retain2 additional official metadata-only URLs separately. Next step is AI accuracy work using prepared development inputs, not automatic operation.');p['updated_at']=now();p['plan_sha256']=sha(Path('docs/v4/EXECUTION_PLAN.md').read_bytes());progress.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','batch','packet','official','body_views','official_text','apply_reviews','export']);a=p.parse_args()
    result=globals()[a.action]()
    print(json.dumps(result if a.action!='freeze'else{'URLs':len(result['URLs']),'product_groups':len(result['product_groups']),'mentions':sum(len(x['mentions'])for x in result['product_groups']),'event_queue':len(result['event_review_queue'])},ensure_ascii=False),flush=True)
