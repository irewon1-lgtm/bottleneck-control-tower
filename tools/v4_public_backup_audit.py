#!/usr/bin/env python3
"""Read-only public Git backup inventory; reports counts/hashes, never content."""
import argparse,gzip,json,re,sqlite3,subprocess,tempfile
from pathlib import Path
from bct.v4.store import sha,now

def git(*args):return subprocess.check_output(['git',*args])
def audit():
    current=set(git('ls-files').decode().splitlines())
    matches={}
    for line in git('rev-list','--objects','--all').decode().splitlines():
        parts=line.split(' ',1)
        if len(parts)==2 and parts[1].startswith('docs/v4/') and re.search(r'\.(?:sqlite3?|db)(?:\.gz)?$',parts[1]):matches[parts[0]]=parts[1]
    result=[]
    with tempfile.TemporaryDirectory(prefix='bct-public-backup-audit-')as tmp:
        for oid,name in matches.items():
            raw=git('cat-file','blob',oid)
            data=gzip.decompress(raw)if raw[:2]==b'\x1f\x8b'else raw
            if not data.startswith(b'SQLite format 3\0'):continue
            p=Path(tmp)/'audit.sqlite3';p.write_bytes(data)
            with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)as db:
                tables={t for t, in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                documents=[]
                if 'documents'in tables:
                    documents=[json.loads(r[0])for r in db.execute('SELECT payload FROM documents')]
                emails=quotes=possible_credentials=0
                for table,column in [('blobs','data'),('documents','payload'),('readings','payload'),('events','payload'),('runs','payload')]:
                    if table not in tables:continue
                    for value, in db.execute(f'SELECT {column} FROM {table}'):
                        text=value.decode('utf-8',errors='replace')if isinstance(value,bytes)else value
                        emails+=bool(re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',text))
                        quotes+=len(re.findall(r'"quote"\s*:',text))
                        possible_credentials+=bool(re.search(r'\b(?:ghp_|github_pat_|gsk_)[A-Za-z0-9_\-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text))
                result.append({'git_blob':oid,'path':name,'path_currently_tracked':name in current,
                    'archive_sha256':sha(raw),'sqlite_sha256':sha(data),'sqlite_bytes':len(data),
                    'documents':len(documents),'body_characters':sum(len(d.get('body',''))for d in documents),
                    'native_blobs':db.execute('SELECT count(*)FROM blobs').fetchone()[0]if 'blobs'in tables else 0,
                    'quote_fields':quotes,'records_with_email_patterns':emails,'records_with_possible_credential_patterns':possible_credentials,
                    'first_path_addition_commits':git('log','--all','--diff-filter=A','--format=%H','--',name).decode().splitlines(),
                    'public_storage_eligibility':'NOT_ESTABLISHED_REQUIRES_EXACT_VERSION_RIGHTS_PRIVACY_REVIEW'if documents or quotes or ('blobs'in tables and db.execute('SELECT count(*)FROM blobs').fetchone()[0]) else 'NO_ORIGINAL_TEXT_FOUND_NOT_A_FULL_PRIVACY_CERTIFICATE',
                    'contact_patterns_are_not_confirmed_private_people':True})
    return {'at':now(),'scope':'Distinct reachable SQLite backup blobs in locally available public-repository refs/history; not deleted/unreachable Git objects or all GitHub artifacts.',
        'distinct_SQLite_backup_versions':len(result),'current_backup_paths':len({r['path']for r in result if r['path_currently_tracked']}),
        'versions_with_source_bodies':sum(r['body_characters']>0 for r in result),'versions_with_quotes':sum(r['quote_fields']>0 for r in result),
        'versions_with_contact_patterns':sum(r['records_with_email_patterns']>0 for r in result),
        'originals_or_Git_history_changed':False,'no_force_push_or_visibility_change':True,'backups':result}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    r=audit();a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k!='backups'}))
