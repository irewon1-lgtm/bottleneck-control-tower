#!/usr/bin/env python3
"""BCT-STOCKS: independent, append-only SQLite research workspace. stdlib only.
Source Git objects are read, never executed. Imports are not verification/ranking.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, os, re, sqlite3, subprocess, sys, tempfile, zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def now(): return datetime.now(timezone.utc).isoformat()
def canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def sha(b): return hashlib.sha256(b).hexdigest()
def packed(x): return zlib.compress(canon(x).encode('utf-8'), 9)
def unpack(b): return json.loads(zlib.decompress(b))
def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS objective_versions(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, manifest_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_blobs(git_sha TEXT PRIMARY KEY, sha256 TEXT NOT NULL, byte_count INTEGER NOT NULL, encoding TEXT NOT NULL, payload_zlib BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS source_files(id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES imports(id), branch TEXT NOT NULL, commit_sha TEXT NOT NULL, path TEXT NOT NULL, git_sha TEXT NOT NULL, disposition TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_text(git_sha TEXT PRIMARY KEY REFERENCES source_blobs(git_sha), text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imported_records(id TEXT PRIMARY KEY, git_sha TEXT NOT NULL REFERENCES source_blobs(git_sha), locator TEXT NOT NULL, kind TEXT NOT NULL, payload_zlib BLOB NOT NULL, verification TEXT NOT NULL DEFAULT 'BCT_IMPORTED_NOT_REVERIFIED');
CREATE TABLE IF NOT EXISTS target_histories(id TEXT PRIMARY KEY, target_id TEXT NOT NULL, source_history_id TEXT, bct_status TEXT, git_sha TEXT NOT NULL REFERENCES source_blobs(git_sha), locator TEXT NOT NULL, payload_zlib BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS entity_mentions(id TEXT PRIMARY KEY, value TEXT NOT NULL, field TEXT NOT NULL, target_id TEXT, git_sha TEXT NOT NULL REFERENCES source_blobs(git_sha), locator TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'UNRESOLVED_NOT_A_CANDIDATE');
CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, company TEXT NOT NULL, ticker TEXT, exchange TEXT, eligibility TEXT NOT NULL, evidence_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS economic_events(id TEXT PRIMARY KEY, candidate_id TEXT REFERENCES candidates(id), event_type TEXT NOT NULL, benefit_path TEXT NOT NULL, fact_status TEXT NOT NULL, evidence_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS market_snapshots(id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id), observed_at TEXT NOT NULL, price_date TEXT NOT NULL, price REAL CHECK(price>0), shares_date TEXT, shares REAL CHECK(shares>0), evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id), stage INTEGER CHECK(stage BETWEEN 1 AND 4), created_at TEXT NOT NULL, decision TEXT NOT NULL, assumptions_json TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS freezes(id TEXT PRIMARY KEY, frozen_at TEXT NOT NULL, objective_id TEXT NOT NULL REFERENCES objective_versions(id), entry_rule TEXT NOT NULL, universe_json TEXT NOT NULL, decision_ids_json TEXT NOT NULL, controls_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluation_observations(id TEXT PRIMARY KEY, freeze_id TEXT NOT NULL REFERENCES freezes(id), observed_at TEXT NOT NULL, values_json TEXT NOT NULL, source_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, event TEXT NOT NULL, details_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS source_file_lookup ON source_files(branch,path);
CREATE INDEX IF NOT EXISTS entity_value ON entity_mentions(value);
CREATE INDEX IF NOT EXISTS history_target ON target_histories(target_id);
'''
IMMUTABLE = ['objective_versions','imports','source_blobs','source_files','source_text','imported_records','target_histories','entity_mentions','candidates','economic_events','market_snapshots','decisions','freezes','evaluation_observations','audit_events']

def connect(db, policy=None):
    db = Path(db); db.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db, timeout=30)
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=30000')
    c.executescript(SCHEMA)
    for table in IMMUTABLE:
        for action in ('UPDATE','DELETE'):
            c.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only: create a new version'); END")
    if policy is not None:
        text = canon(policy)
        c.execute('INSERT OR IGNORE INTO objective_versions VALUES(?,?,?)', (sha(text.encode()),now(),text))
    c.commit(); return c

EXTENSIONS = {'.json','.jsonl','.ndjson','.md','.txt','.csv','.html','.htm','.pdf','.docx','.xlsx','.sqlite3','.sqlite','.db','.xml','.yaml','.yml'}

def disposition(path):
    parts = Path(path).parts
    if any(p in {'tests','test','fixtures','node_modules','vendor','__pycache__','.venv','venv','alembic','migrations','workflows'} for p in parts):
        return 'SKIPPED', 'code/test/fixture/automation, not research evidence'
    if Path(path).suffix.lower() not in EXTENSIONS:
        return 'SKIPPED', 'non-research/binary format; path inventory retained'
    if any(p in {'src','scripts','script'} for p in parts):
        return 'SKIPPED', 'application source/config; path inventory retained'
    return 'IMPORTED', ''

NAME_FIELDS = {'ticker','symbol','company','company_name','supplier','manufacturer','customer','name','publisher','origin_publisher'}
URL = re.compile(r'https?://[^\s<>"\]\[)]+')

def walk_json(c, blob, value, prefix='$'):
    stack=[(value,prefix,None)]
    while stack:
        obj,loc,target=stack.pop()
        if isinstance(obj,dict):
            ident=obj.get('formal_TARGET_id') or obj.get('target_id')
            if isinstance(ident,str): target=ident
            if isinstance(obj.get('id'),str) and isinstance(obj.get('history'),list): target=obj['id']
            if target and ('status' in obj) and ('.history[' in loc or 'review_id' in obj or 'formal_TARGET_id' in obj):
                ident=obj.get('id') or obj.get('review_id')
                status=obj.get('status')
                key=sha((target+'\0'+canon(obj)).encode())
                c.execute('INSERT OR IGNORE INTO target_histories VALUES(?,?,?,?,?,?,?)',(key,target,str(ident) if ident else None,str(status) if status else None,blob,loc,packed(obj)))
            if any(k in obj for k in ('origin_url','url','document_id','event_type','evidence_kind')):
                key=sha((blob+'\0'+loc).encode())
                c.execute('INSERT OR IGNORE INTO imported_records(id,git_sha,locator,kind,payload_zlib) VALUES(?,?,?,?,?)',(key,blob,loc,'BCT_STRUCTURED',packed(obj)))
            for k,v in obj.items():
                here=loc+'.'+str(k)
                if k in NAME_FIELDS and isinstance(v,str) and 0<len(v.strip())<=200:
                    key=sha((blob+'\0'+here+'\0'+v).encode())
                    c.execute('INSERT OR IGNORE INTO entity_mentions(id,value,field,target_id,git_sha,locator) VALUES(?,?,?,?,?,?)',(key,v,k,target,blob,here))
                if isinstance(v,(dict,list)): stack.append((v,here,target))
        elif isinstance(obj,list):
            stack.extend((v,f'{loc}[{i}]',target) for i,v in enumerate(obj) if isinstance(v,(dict,list)))

def normalize_sqlite(c,blob,raw):
    # Only SELECT from an immutable temporary copy. No source code/views executed.
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'source.sqlite3'; p.write_bytes(raw)
        src=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            src.execute('PRAGMA query_only=ON'); src.execute('PRAGMA trusted_schema=OFF')
            if src.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise ValueError('source sqlite integrity failed')
            for (table,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                quoted='"'+table.replace('"','""')+'"'
                cur=src.execute('SELECT * FROM '+quoted); names=[x[0] for x in cur.description]
                for i,row in enumerate(cur):
                    obj={k:({'_blob_base64':base64.b64encode(v).decode()} if isinstance(v,bytes) else v) for k,v in zip(names,row)}
                    loc=f'sqlite:{table}:row:{i}'
                    key=sha((blob+'\0'+loc).encode())
                    c.execute('INSERT OR IGNORE INTO imported_records(id,git_sha,locator,kind,payload_zlib) VALUES(?,?,?,?,?)',(key,blob,loc,'BCT_SQLITE_ROW',packed(obj)))
                    walk_json(c,blob,obj,loc)
                    for name,v in list(obj.items()):
                        if isinstance(v,str) and v[:1] in ('{','['):
                            try: walk_json(c,blob,json.loads(v),loc+'.'+name)
                            except (ValueError,RecursionError): pass
        finally: src.close()

def import_blob(c,blob,raw,path):
    actual=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if actual!=blob: raise ValueError('Git blob hash mismatch: '+path)
    if c.execute('SELECT 1 FROM source_blobs WHERE git_sha=?',(blob,)).fetchone(): return []
    text=None; errors=[]
    try: text=raw.decode('utf-8')
    except UnicodeDecodeError: pass
    c.execute('INSERT INTO source_blobs VALUES(?,?,?,?,?)',(blob,sha(raw),len(raw),'utf-8' if text is not None else 'binary',zlib.compress(raw,9)))
    if raw.startswith(b'SQLite format 3\0'):
        try: normalize_sqlite(c,blob,raw)
        except (sqlite3.DatabaseError,ValueError) as e:
            errors.append({'path':path,'blob':blob,'error':str(e),'raw_preserved':True,'normalization':'PARTIAL'})
    elif text is not None:
        c.execute('INSERT INTO source_text VALUES(?,?)',(blob,text))
        suffix=Path(path).suffix.lower()
        if suffix in {'.json','.jsonl','.ndjson'}:
            try:
                if suffix=='.json': walk_json(c,blob,json.loads(text))
                else:
                    for i,line in enumerate(text.splitlines()):
                        if line.strip(): walk_json(c,blob,json.loads(line),f'line:{i+1}')
            except (ValueError,RecursionError) as e:
                errors.append({'path':path,'blob':blob,'error':str(e),'raw_preserved':True})
        # Links in prose are source references, NOT newly fetched/verified originals.
        for url in sorted(set(URL.findall(text))):
            key=sha((blob+'\0url\0'+url).encode())
            c.execute('INSERT OR IGNORE INTO imported_records(id,git_sha,locator,kind,payload_zlib) VALUES(?,?,?,?,?)',(key,blob,'url:'+url,'BCT_URL_REFERENCE',packed({'url':url})))
    return errors

def stats(c):
    names=IMMUTABLE
    return {name:c.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in names}

def import_git(c,repo,policy):
    refs={}
    for line in git(repo,'for-each-ref','--format=%(refname) %(objectname)','refs/remotes/bct/').decode().splitlines():
        ref,commit=line.split(); branch=ref[len('refs/remotes/bct/'):]
        if branch in {'HEAD',policy['workspace_branch']} or branch.startswith(policy['workspace_branch']+'/'): continue
        refs[branch]=commit
    if not {'main','future-bottleneck-data','data'}.issubset(refs): raise ValueError('required BCT branches not fetched')
    frozen={'repository':policy['source_repository'],'branch_tips':refs,'selection_policy':'research-extensions-v1','objective_sha256':sha(canon(policy).encode())}
    import_id=sha(canon(frozen).encode())
    if c.execute('SELECT 1 FROM imports WHERE id=?',(import_id,)).fetchone():
        return {'result':'ALREADY_IMPORTED','import_id':import_id,'counts':stats(c)}
    before=stats(c); failures=[]; paths=0
    with c:
        c.execute('INSERT INTO imports VALUES(?,?,?)',(import_id,now(),canon(frozen)))
        for branch,commit in sorted(refs.items()):
            for entry in git(repo,'ls-tree','-rlz',commit).split(b'\0'):
                if not entry: continue
                header,p=entry.split(b'\t',1); mode,kind,blob,size=header.decode().split()
                if kind!='blob': continue
                path=p.decode('utf-8'); state,reason=disposition(path)
                if int(size)>90*1024*1024: state,reason='SKIPPED','over 90MiB safety limit; not claimed complete'
                if state=='IMPORTED':
                    raw=git(repo,'cat-file','blob',blob)
                    if len(raw)!=int(size): raise ValueError('size mismatch')
                    failures.extend(import_blob(c,blob,raw,path))
                key=sha((import_id+'\0'+branch+'\0'+path).encode())
                c.execute('INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?)',(key,import_id,branch,commit,path,blob,state,reason)); paths+=1
        audit={'before':before,'after':stats(c),'parse_failures':failures,'files_in_inventory':paths,'original_BCT_written':False,'external_originals_reverified':False,'investment_decisions_created':0}
        c.execute('INSERT INTO audit_events VALUES(?,?,?,?)',(sha((import_id+'import').encode()),now(),'IMPORT_COMPLETE',canon(audit)))
    result={'result':'IMPORTED','import_id':import_id,'source':frozen,'counts':stats(c),'parse_failures':failures,'scope':'retained research files at visible branch tips; not deleted history or full external originals','stage1_status':'CORPUS_IMPORTED_ENTITY_RESOLUTION_PENDING','stage1_complete':False,'investment_recommendations':0}
    return result

def verify(c):
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    foreign=c.execute('PRAGMA foreign_key_check').fetchall()
    bad=[]
    for g,h,n,p in c.execute('SELECT git_sha,sha256,byte_count,payload_zlib FROM source_blobs'):
        raw=zlib.decompress(p)
        if len(raw)!=n or sha(raw)!=h or hashlib.sha1(b'blob '+str(n).encode()+b'\0'+raw).hexdigest()!=g: bad.append(g)
    if integrity!='ok' or foreign or bad: raise ValueError('database verification failed')
    return {'integrity_check':integrity,'foreign_key_errors':len(foreign),'source_hash_errors':len(bad),'counts':stats(c)}

def export(c,folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    verification=verify(c)
    (folder/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    targets=[dict(zip(('target_id','distinct_history_versions'),r)) for r in c.execute('SELECT target_id,COUNT(*) FROM target_histories GROUP BY target_id ORDER BY target_id')]
    (folder/'targets.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    mentions=[dict(zip(('value','field','mentions','state'),r)) for r in c.execute('SELECT value,field,COUNT(*),MIN(state) FROM entity_mentions GROUP BY value,field ORDER BY value,field')]
    (folder/'entity-mentions.json').write_text(json.dumps(mentions,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (folder/'schema.sql').write_text('\n'.join(r[0]+';' for r in c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")),encoding='utf-8')
    return verification

def main():
    a=argparse.ArgumentParser(); a.add_argument('command',choices=['init','import-git','verify','export']); a.add_argument('--db',default=str(ROOT/'data/bct-stocks.sqlite3')); a.add_argument('--source'); a.add_argument('--output',default=str(ROOT/'exports')); args=a.parse_args()
    policy=json.loads((ROOT/'project.json').read_text(encoding='utf-8'))
    c=connect(args.db,policy)
    try:
        if args.command=='import-git':
            if not args.source: a.error('--source required')
            result=import_git(c,args.source,policy)
            Path(args.output).mkdir(parents=True,exist_ok=True)
            if result['result'] != 'ALREADY_IMPORTED':
                (Path(args.output)/'import-receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            export(c,args.output)
        elif args.command in {'init','export'}: result=export(c,args.output)
        else: result=verify(c)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally: c.close()

if __name__=='__main__': main()
