"""Q1 facts-only checkpoints using the existing Ledger, gzip and private CAS.

Does not pretend a Q1 ledger is a CPU queue. Never writes the CPU state ref.
Native workbooks, article bodies and credentials are not part of this capsule.
"""
import base64
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from urllib.parse import urlsplit,parse_qsl
from . import cpu_operations as op,private_state as private
from .store import file_sha,now
from .quantitative import LIMIT

FORMAT='bct-q1-private-facts-1'
STATE_REF='refs/heads/codex/bct-v4-quantitative-state'
SOURCES={'m3','g17','usaspending','eia','usgs','ted','sec','census_trade'}
HOSTS={'www.census.gov','api.census.gov','www.federalreserve.gov','api.usaspending.gov',
       'www.eia.gov','api.eia.gov','www.usgs.gov','pubs.usgs.gov','d9-wret.s3.us-west-2.amazonaws.com',
       'api.ted.europa.eu','ted.europa.eu','data.sec.gov','www.sec.gov'}
KINDS={'QUANTITATIVE_OBSERVATION','QUANTITATIVE_PAGE_COMMITTED','QUANTITATIVE_VALIDATION',
       'QUANTITATIVE_NOTICE_HELD','QUANTITATIVE_SOURCE_FAILURE','QUANTITATIVE_DOCUMENT','QUANTITATIVE_TARGET_REVIEW','QUANTITATIVE_PRODUCT_FACT','QUANTITATIVE_COUNTERPART_REVIEW'}
ATTRS={'award_id','award_type','PSC','agency','contract_start_not_observation_period','contract_end_not_delivery',
       'last_modified','physical_quantity','modification_number','action_type','contract_type','notice_type',
       'is_actual_order','is_framework_or_option','lot_relationship','Status','Technology','Operating Month',
       'Operating Year','Planned Operation Month','Planned Operation Year','sheet','qualified_supply','actuality',
       'unit_locator','metric_locator','is_total','scope','footnote_pointer','classification_locator',
       'is_country_total','is_product_total','do_not_sum_parent_and_children',
       'trade_direction','commodity_code_year','codebook_state','definition','quantity_flag_original',
       'sec_document_type','sec_section_start','domestic_foreign_code','physical_quantity_role','accession','context_id','ix_name','ix_scale','ix_sign'}

RECORD_FIELDS=set("acquired_at adjustment attributes automatic_promotion backtest_state coverage_scope entity_or_facility_id geography measurement_type metric original_available_for_replay original_version parser_version period_end period_start product_or_classification published_at quality_state raw_or_safe_payload_hash revised_at rights_scope scale sector_hint semantic_validation source_document_id source_id source_lineage_id source_locator source_url stage status stock_or_flow unit_normalized unit_original unknown_reason value_decimal_or_null value_normalized_or_null value_original vintage".split())
from .quantitative_product import FIELDS as PRODUCT_FIELDS
from .quantitative_counterpart import FIELDS as COUNTERPART_FIELDS,validate as validate_counterpart

EVENT_FIELDS={
 'QUANTITATIVE_COUNTERPART_REVIEW':COUNTERPART_FIELDS,
 'QUANTITATIVE_PRODUCT_FACT':PRODUCT_FIELDS,
 'QUANTITATIVE_OBSERVATION':set('key id task change previous_id record'.split()),
 'QUANTITATIVE_PAGE_COMMITTED':set('id task page has_next total raw_hash parser rows added committed_at'.split()),
 'QUANTITATIVE_VALIDATION':set('reason originals_modified quality_state policy record_ids'.split()),
 'QUANTITATIVE_NOTICE_HELD':set('page total held notices task'.split()),
 'QUANTITATIVE_SOURCE_FAILURE':set('task page error retry at'.split()),
 'QUANTITATIVE_DOCUMENT':set('source_id document_id url published_at filing_date accession form cik detail status'.split()),
 'QUANTITATIVE_TARGET_REVIEW':set('id kind product scope observation_ids observations target missing review_state as_of actual_order_quantity qualified_supply_quantity s_stage research_only reported_nameplate_MW_sum reported_status planned_reported_dates_not_supply_guarantees legacy_record_id legacy_s_stage role quantity_literal publication_date'.split())}


def audit(db):
    """Fail closed on source text/unknown fields; facts are not rights to originals."""
    for table in ('blobs','documents','captures','readings','runs','firsts'):
        if db.execute('SELECT count(*) FROM '+table).fetchone()[0]:raise ValueError('Q1_NONFACT_TABLE_NOT_EMPTY')
    if set(r[0]for r in db.execute('SELECT key FROM metadata'))-{'format','objective'}:raise ValueError('Q1_UNREVIEWED_METADATA')
    sources=set();count=0
    for kind,payload in db.execute('SELECT kind,payload FROM events ORDER BY seq'):
        if kind not in KINDS:raise ValueError('Q1_UNKNOWN_EVENT_KIND')
        event=json.loads(payload)
        if set(event)-EVENT_FIELDS[kind]:raise ValueError('Q1_UNREVIEWED_EVENT_FIELD')
        if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+\S+',payload):
            raise ValueError('Q1_CONTACT_OR_CREDENTIAL_NOT_ARCHIVABLE')
        if kind=='QUANTITATIVE_COUNTERPART_REVIEW':validate_counterpart(event)
        if kind=='QUANTITATIVE_PRODUCT_FACT'and(event.get('s_stage')!='UNKNOWN'or event.get('research_only')is not True or event.get('qualified_capacity')is not None):raise ValueError('Q2_PRODUCT_UNREVIEWED_PROMOTION')
        if kind=='QUANTITATIVE_TARGET_REVIEW'and(event.get('s_stage')!='UNKNOWN'or event.get('research_only')is not True):raise ValueError('Q2_AUTOMATIC_STAGE_FORBIDDEN')
        if kind=='QUANTITATIVE_OBSERVATION':
            r=event['record'];sources.add(r['source_id']);count+=1
            if set(r)!=RECORD_FIELDS:raise ValueError('Q1_UNREVIEWED_RECORD_FIELD')
            u=urlsplit(r['source_url'])
            if r['source_id']not in SOURCES or u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password:
                raise ValueError('Q1_UNREVIEWED_OFFICIAL_SOURCE')
            if any(re.search('token|key|auth|session|secret',k,re.I)for k,v in parse_qsl(u.query)):
                raise ValueError('Q1_SECRET_QUERY')
            if r.get('stage')!='UNKNOWN' or r.get('automatic_promotion')is not False:
                raise ValueError('Q1_STAGE_PROMOTION_FORBIDDEN')
            if set(r.get('attributes',{}))-ATTRS:raise ValueError('Q1_UNREVIEWED_ATTRIBUTE')
            if any(k in r for k in ('body','text','quote','raw','excerpt','response')):
                raise ValueError('Q1_SOURCE_BODY_FORBIDDEN')
            if r['measurement_type']not in {'MONEY','PHYSICAL','INDEX','RATIO'}:
                raise ValueError('Q1_NONNUMERIC_RECORD')
    if not count:raise ValueError('Q1_EMPTY_FACTS_CHECKPOINT')
    return {'format':FORMAT,'observation_versions':count,'sources':sorted(sources),
            'article_bodies':0,'native_source_files':0,'original_evidence_recovery':False,
            'rights':'Official numerical facts/identifiers and own processing state only; native source rights not granted.',
            'CPU_queue_restored':False,'automatic_promotion':False}


def checkpoint(ledger,dest):
    audit(ledger.db)
    proof=op.checkpoint(ledger,dest)
    archive=Path(dest)/proof['archive']
    if archive.stat().st_size>LIMIT:raise ValueError('Q1_CHECKPOINT_16MIB_LIMIT')
    proof['format']=FORMAT;proof['storage_review']=audit(ledger.db)
    (Path(dest)/'checkpoint.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def restore(source,root):
    source,root=Path(source),Path(root);p=json.loads((source/'checkpoint.json').read_text())
    if p.get('format')!=FORMAT or p.get('archive')!='checkpoint.sqlite3.gz':raise ValueError('Q1_CHECKPOINT_FORMAT')
    archive=source/p['archive']
    if archive.stat().st_size>LIMIT or file_sha(archive)!=p['archive_sha256']:raise ValueError('Q1_ARCHIVE_HASH_OR_SIZE')
    if (root/'v4.sqlite3').exists():raise ValueError('Q1_REFUSE_RESTORE_OVERWRITE')
    root.mkdir(parents=True,exist_ok=True);dest=root/'v4.sqlite3'
    try:
        with gzip.open(archive,'rb')as src,dest.open('xb')as out:
            size=0
            while block:=src.read(1048576):
                size+=len(block)
                if size>512*1024**2:raise ValueError('Q1_EXPANDED_SQLITE_SIZE')
                out.write(block)
        if file_sha(dest)!=p['sqlite_sha256']:raise ValueError('Q1_SQLITE_HASH')
        with sqlite3.connect(dest.resolve().as_uri()+'?mode=ro',uri=True)as db:
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',)or op.table_digests(db)!=p['tables']:
                raise ValueError('Q1_TABLES_OR_INTEGRITY')
            review=audit(db)
        return {'restored':True,'tables':len(p['tables']),'sqlite_sha256':p['sqlite_sha256'],'review':review}
    except Exception:
        dest.unlink(missing_ok=True)  # Only this incomplete new restore, never a prior DB.
        raise


def publish(repo,source,expected_parent,token,scope,*,verify_remote=True):
    """Reuse trusted scope receipt; actual publication authenticates without probes."""
    if not (scope.get('private_repository')==private.PRIVATE_REPO and scope.get('visibility')=='private'
            and scope.get('private_contents_probe')==201 and scope.get('visible_private_repository_count')==1
            and set(scope.get('operating_ref_create_denials',{}))=={'main','data'}
            and all(c in (403,404)for c in scope['operating_ref_create_denials'].values())
            and scope.get('operating_refs_modified')is False):raise ValueError('Q1_SCOPE_RECEIPT')
    if not token:raise ValueError('Q1_PRIVATE_WRITER_CREDENTIAL_MISSING')
    repo=Path(repo);repo.mkdir(parents=True,exist_ok=True)
    auth=base64.b64encode(('x-access-token:'+token).encode()).decode()
    env={**os.environ,'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader',
         'GIT_CONFIG_VALUE_0':'AUTHORIZATION: basic '+auth,'GIT_CONFIG_KEY_1':'credential.helper',
         'GIT_CONFIG_VALUE_1':'','GIT_TERMINAL_PROMPT':'0'}
    def git(*args):
        p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,env=env,timeout=25)
        if p.returncode:raise ValueError('Q1_PRIVATE_GIT_FAILED')
        return p.stdout
    if not(repo/'.git').exists():git('init');git('remote','add','origin',private.PRIVATE_URL)
    if git('config','--get','remote.origin.url').decode().strip()!=private.PRIVATE_URL:raise ValueError('Q1_PRIVATE_REMOTE_IDENTITY')
    from .quantitative_delta import publish as page_publish
    result=page_publish(repo,source,private._parent(expected_parent),env)
    if not verify_remote:
        result.update(repository=private.PRIVATE_REPO,visibility='private',private_writer_scope_reused=True,remote_restore_verified=False,CPU_state_written=False,seven_day_observation_started=False)
        return result
    git('fetch','--no-tags','origin',STATE_REF)
    if git('rev-parse','FETCH_HEAD').decode().strip()!=result['commit']:raise ValueError('Q1_REMOTE_COMMIT_CHANGED')
    with tempfile.TemporaryDirectory(prefix='bct-q1-remote-')as tmp:
        cp=Path(tmp)/'checkpoint';cp.mkdir()
        from .quantitative_delta import receive
        cp.rmdir();receive(git,result['commit'],cp)
        # A NEW Python process, not the in-memory writer connection.
        cmd=['python','-c','from bct.v4.quantitative_private import restore;import json,sys;print(json.dumps(restore(sys.argv[1],sys.argv[2])))',str(cp),str(Path(tmp)/'restored')]
        child=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if child.returncode:raise ValueError('Q1_REMOTE_NEW_PROCESS_RESTORE_FAILED')
        result['remote_new_process_restore']=json.loads(child.stdout)
    result.update(repository=private.PRIVATE_REPO,visibility='private',private_writer_scope_reused=True,
                  remote_restore_verified=True,CPU_state_written=False,seven_day_observation_started=False)
    return result


def remote_checkpoint(repo,destination,token):
    """Read the existing Q1 ref with its existing dedicated credential; no probes."""
    if not token:raise ValueError('Q1_PRIVATE_READER_CREDENTIAL_MISSING')
    repo=Path(repo);repo.mkdir(parents=True,exist_ok=True)
    auth=base64.b64encode(('x-access-token:'+token).encode()).decode()
    env={**os.environ,'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader',
         'GIT_CONFIG_VALUE_0':'AUTHORIZATION: basic '+auth,'GIT_CONFIG_KEY_1':'credential.helper',
         'GIT_CONFIG_VALUE_1':'','GIT_TERMINAL_PROMPT':'0'}
    def git(*args):
        p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,env=env,timeout=25)
        if p.returncode:raise ValueError('Q1_PRIVATE_READ_FAILED')
        return p.stdout
    git('init');git('remote','add','origin',private.PRIVATE_URL);git('fetch','--no-tags','origin',STATE_REF)
    parent=git('rev-parse','FETCH_HEAD').decode().strip();destination=Path(destination)
    from .quantitative_delta import receive
    verified=receive(git,parent,destination)
    return {'parent':parent,'verified':verified}


def seal(source,destination,passphrase,parent,*,report=None):
    source,destination=Path(source),Path(destination)
    proof=json.loads((source/'checkpoint.json').read_text());archive=(source/'checkpoint.sqlite3.gz').read_bytes()
    if len(archive)>LIMIT or file_sha(source/'checkpoint.sqlite3.gz')!=proof['archive_sha256']:raise ValueError('Q1_SEAL_CHECKPOINT_HASH_OR_SIZE')
    payload={'format':FORMAT,'proof':proof,'archive_base64':base64.b64encode(archive).decode(),
             'parent':private._parent(parent),'report':report,'code_SHA':os.environ.get('GITHUB_SHA')}
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb')as out:out.write(private._gpg(json.dumps(payload).encode(),passphrase))
    return {'encrypted_sha256':file_sha(destination),'encrypted_bytes':destination.stat().st_size}


def unseal(source,destination,passphrase):
    payload=json.loads(private._gpg(Path(source).read_bytes(),passphrase,decrypt=True))
    if payload.get('format')!=FORMAT:raise ValueError('Q1_HANDOFF_FORMAT')
    archive=base64.b64decode(payload['archive_base64'],validate=True)
    if len(archive)>LIMIT:raise ValueError('Q1_HANDOFF_SIZE')
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    (destination/'checkpoint.json').write_text(json.dumps(payload['proof']))
    (destination/'checkpoint.sqlite3.gz').write_bytes(archive)
    with tempfile.TemporaryDirectory(prefix='q1-unseal-')as tmp:verified=restore(destination,Path(tmp)/'verified')
    return {'parent':private._parent(payload['parent']),'report':payload.get('report'),'verified':verified,'code_SHA':payload.get('code_SHA')}
