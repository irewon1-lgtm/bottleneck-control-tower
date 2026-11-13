"""Probe real publisher-proof rates on fresh RSS URLs, no original bytes exported."""
from pathlib import Path
import json, os, sqlite3, subprocess
from urllib.parse import urlsplit
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from bct import future_bottleneck as future
from bct.future_body import extract_document

def cmd(*args):return subprocess.check_output(args)
ref=cmd("git","ls-remote","origin","refs/heads/data").decode().split()[0]
assert len(ref)==40
cmd("git","fetch","--no-tags","--depth=1","origin",ref)
p=Path(os.environ["RUNNER_TEMP"])/"bct-proof-canonical.sqlite3"
p.write_bytes(cmd("git","show",ref+":canonical.sqlite3"))
import hashlib
state=json.loads(cmd("git","show",ref+":state.json"))
assert hashlib.sha256(p.read_bytes()).hexdigest()==state["sha256"]
with sqlite3.connect(p) as db:
    rows=db.execute("SELECT id,url,source,title,collected_at FROM radar_items WHERE status='active' ORDER BY collected_at DESC LIMIT 900").fetchall()
def preferred(row):
    return bool(any(s in row[1].lower() for s in ('energy.gov','eia.gov','nist.gov','semiengineering','breakingdefense','datacenterdynamics','defensenews','power','mining','supplychaindive','freightwaves')))
choices=[];hosts=Counter()
for row in sorted(rows,key=lambda r:0 if preferred(r) else 1):
    host=urlsplit(row[1]).hostname or ""
    if not host or hosts[host]>=2 or any(s in row[1].lower() for s in ('/videos/','/podcast/','/images/')):
        continue
    hosts[host]+=1;choices.append(row)
    if len(choices)>=36:break
def try_one(row):
    docid,url,source,title,at=row
    host=urlsplit(url).hostname or "?"
    try:
        out=future.fetch_html(url)
        body=extract_document(out['html'],http_status=out['status'],content_type=out['content_type'])
        return {'host':host,'source':source,'body_status':body['body_status'],
                'proof':out.get('provenance_verified') is True,'date_proof':out.get('publication_verified') is True,
                'body_chars':body.get('body_chars',0),'error':None}
    except Exception as e:
        return {'host':host,'source':source,'body_status':'UNAVAILABLE',
                'proof':False,'date_proof':False,'body_chars':0,'error':type(e).__name__}
with ThreadPoolExecutor(max_workers=5) as pool:
    results=list(pool.map(try_one,choices))
counts=Counter()
for row in results:
    counts['attempts']+=1
    if row['body_status']=='FULL':counts['full']+=1
    if row['proof']:counts['publisher_original_verified']+=1
    if row['date_proof']:counts['publication_verified']+=1
    if row['error']:counts['network_errors']+=1
report={'status':'REAL_PUBLIC_URL_TRIAL_UNVERIFIED_UNTIL_RECORDED',
        'canonical_data_sha':ref,'rss_records':state['radar_items'],
        'counts':dict(counts),'rows':results,
        'source_bytes_published':False,'database_modified':False,'bottleneck_promotions':0}
dst=Path(os.environ['RUNNER_TEMP'])/'bct-source-proof-rate.json'
dst.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('BCT_REAL_SOURCE_PROOF_TRIAL='+json.dumps(report,ensure_ascii=False),flush=True)
